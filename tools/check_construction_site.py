#!/usr/bin/env python3
"""Smoke-check construction models, legacy redirects, and source SVG audits."""
from __future__ import annotations

import copy
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from build_site import build_detail, construction_to_model, construction_to_models

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "construction-regulations"
SITE = ROOT / "site"


def main() -> int:
    errors: list[str] = []
    index_path = SITE / "index.html"
    index_html = index_path.read_text(encoding="utf-8") if index_path.exists() else ""
    if not index_html:
        errors.append("site/index.html is missing")
    if 'href="construction/index.html"' in index_html:
        errors.append("main index still exposes a separate construction page")

    legacy_index_path = SITE / "construction" / "index.html"
    legacy_index_html = (
        legacy_index_path.read_text(encoding="utf-8") if legacy_index_path.exists() else ""
    )
    if "../index.html?axis=construction" not in legacy_index_html:
        errors.append("site/construction/index.html is not a construction-filter redirect")

    countries = 0
    for path in sorted(DATA_DIR.glob("*.json")):
        if path.name == "manifest.json":
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        slug = data["slug"]
        board = data["processBoard"]
        models = construction_to_models(data)
        public_specs = {item["slug"]: item for item in data.get("publicModels", [])}
        countries += 1

        expected_requirement_ids = {item["id"] for item in data["requirements"]}
        actual_requirement_ids = {
            ident
            for model in models
            for node in model["process"]["nodes"]
            for ident in node["requirement_ids"]
        }
        if actual_requirement_ids != expected_requirement_ids:
            errors.append(
                f"{slug} adapter requirement IDs differ: "
                f"expected {sorted(expected_requirement_ids)}, got {sorted(actual_requirement_ids)}"
            )

        expected_question_ids = {item["id"] for item in data["openQuestions"]}
        actual_question_ids = {
            ident
            for model in models
            for node in model["process"]["nodes"]
            for ident in node["question_ids"]
        }
        if actual_question_ids != expected_question_ids:
            errors.append(
                f"{slug} adapter question IDs differ: "
                f"expected {sorted(expected_question_ids)}, got {sorted(actual_question_ids)}"
            )

        expected_gate_orders = {item["order"] for item in data["permitPath"]}
        actual_gate_orders = {
            order
            for model in models
            for node in model["process"]["nodes"]
            for order in node["gate_orders"]
        }
        if actual_gate_orders != expected_gate_orders:
            errors.append(
                f"{slug} adapter gate orders differ: "
                f"expected {sorted(expected_gate_orders)}, got {sorted(actual_gate_orders)}"
            )

        if data.get("publicModels"):
            expected_model_slugs = {item["slug"] for item in data["publicModels"]}
            actual_model_slugs = {item["slug"] for item in models}
            if actual_model_slugs != expected_model_slugs:
                errors.append(f"{slug} public construction model slugs differ")
        if slug == "senegal" and len(models) != 3:
            errors.append(f"senegal must expose three construction models, got {len(models)}")
        conclusion_ids = {item["id"] for item in data["reportReadyConclusions"]}
        model_conclusion_ids = {
            item["id"] for model in models for item in model["canvas"]["keyFindings"]
        }
        if model_conclusion_ids != conclusion_ids:
            errors.append(f"{slug} adapter conclusion IDs differ")
        overlay_ids = {item["id"] for item in data["siteOverlays"]}
        model_overlay_ids = {
            item["id"] for model in models for item in model["canvas"]["siteOverlays"]
        }
        if model_overlay_ids != overlay_ids:
            errors.append(f"{slug} adapter site overlay IDs differ")

        xss_probe = copy.deepcopy(data)
        xss_probe["processBoard"]["nodes"][0]["note"] = "</script><script>globalThis.PWNED=1</script>"
        xss_model = construction_to_models(xss_probe)[0]
        xss_html = build_detail(xss_model, [xss_model])
        if "</script><script>globalThis.PWNED=1</script>" in xss_html:
            errors.append(f"{slug} adapter allows an inline-script breakout")

        if slug == "senegal":
            generic_probe = copy.deepcopy(data)
            generic_probe["slug"] = "adapter-probe"
            stage_names = {
                stage: f"P{index} 테스트 단계 {index}"
                for index, stage in enumerate(generic_probe["processBoard"]["stages"])
            }
            generic_probe["processBoard"]["stages"] = list(stage_names.values())
            for node in generic_probe["processBoard"]["nodes"]:
                node["stage"] = stage_names[node["stage"]]
            generic_model = construction_to_model(generic_probe)
            generic_nodes = {item["id"]: item for item in generic_model["process"]["nodes"]}
            if any(generic_nodes[ident]["deadline"] for ident in ("B10", "B12", "B16")):
                errors.append("generic construction adapter leaked Senegal statutory deadlines")

        model_nodes = {
            item["id"]: item
            for model in models
            for item in model["process"]["nodes"]
        }
        expected_requirements_by_node: dict[str, set[str]] = {}
        if public_specs:
            for spec in public_specs.values():
                allowed = set(spec["requirementIds"])
                for node_id in spec["nodeIds"]:
                    expected_requirements_by_node[node_id] = allowed
        requirements = {item["id"]: item for item in data["requirements"]}
        for source_node in board["nodes"]:
            expected_basis: dict[str, set[str]] = {}
            refs = list(source_node.get("refs", []))
            for requirement_id in source_node.get("requirementIds", []):
                allowed = expected_requirements_by_node.get(source_node["id"])
                if allowed is not None and requirement_id not in allowed:
                    continue
                refs.extend(requirements[requirement_id].get("legalBasis", []))
            for ref in refs:
                expected_basis.setdefault(ref["instrumentId"], set()).update(ref["provisions"])
            actual_basis = {
                item["instrument_id"]: item["article"]
                for item in model_nodes[source_node["id"]]["legal_basis"]
            }
            if set(actual_basis) != set(expected_basis):
                errors.append(f"{slug} adapter legal basis differs for {source_node['id']}")
                continue
            for instrument_id, provisions in expected_basis.items():
                missing = [value for value in provisions if value not in actual_basis[instrument_id]]
                if missing:
                    errors.append(
                        f"{slug} adapter legal provisions missing for {source_node['id']} "
                        f"{instrument_id}: {missing}"
                    )

        svg_rel = f"{slug}-construction.svg"
        if not public_specs:
            svg_path = SITE / "boards" / svg_rel
            if not svg_path.exists():
                errors.append(f"site/boards/{svg_rel} is missing")
                continue
            try:
                root = ET.parse(svg_path).getroot()
            except ET.ParseError as exc:
                errors.append(f"site/boards/{svg_rel} is invalid XML: {exc}")
                continue
            if not root.tag.endswith("svg"):
                errors.append(f"site/boards/{svg_rel} root is not <svg>")

            svg_text = svg_path.read_text(encoding="utf-8")
            if board["title"] not in svg_text:
                errors.append(f"site/boards/{svg_rel} does not contain the board title")
            for node in board["nodes"]:
                if node["id"] not in svg_text:
                    errors.append(f"site/boards/{svg_rel} is missing node {node['id']}")

        for model in models:
            model_slug = model["slug"]
            spec = public_specs.get(model_slug)
            detail_path = SITE / "model" / model_slug / "index.html"
            detail_html = detail_path.read_text(encoding="utf-8") if detail_path.exists() else ""
            if not detail_html:
                errors.append(f"site/model/{model_slug}/index.html is missing")
                continue
            for marker in (
                "건축 법·제도",
                f'NO {model["priority"]:02d}',
                '<dialog class="drawer" id="dlg">',
                "function openNode(id)",
                "b.addEventListener('click'",
                'class="board" id="board" style="min-width:',
                "협의·관할기관",
                "현장 확인질문",
                "보고서 반영",
                "핵심 적용판단",
                f'{model["priority"]:02d} · {model["name"]}',
                "레인 \\ 단계",
            ):
                if marker not in detail_html:
                    errors.append(f"site/model/{model_slug}/index.html is missing {marker!r}")
            expected_ids = [node["id"] for node in model["process"]["nodes"]]
            node_buttons = re.findall(r'<button class="node" data-id="([^"]+)"', detail_html)
            if len(node_buttons) != len(expected_ids) or set(node_buttons) != set(expected_ids):
                errors.append(
                    f"site/model/{model_slug}/index.html node buttons differ: "
                    f"expected {expected_ids}, got {node_buttons}"
                )
            if '<div class="studio-board-view">' in detail_html or f"{svg_rel}" in detail_html:
                errors.append(f"site/model/{model_slug}/index.html still embeds the static SVG")
            if spec and model["verification"]["scope"] != spec["verificationScope"]:
                errors.append(f"site/model/{model_slug} uses the country-wide verification scope")
            if spec and any(not stage.startswith("S") for stage in model["process"]["stages"]):
                errors.append(f"site/model/{model_slug} does not distinguish lifecycle stages as S-series")

            projected_svg_rel = f"{model_slug}.svg"
            projected_svg_path = SITE / "boards" / projected_svg_rel
            if not projected_svg_path.exists():
                errors.append(f"site/boards/{projected_svg_rel} is missing")
            else:
                try:
                    projected_root = ET.parse(projected_svg_path).getroot()
                except ET.ParseError as exc:
                    errors.append(f"site/boards/{projected_svg_rel} is invalid XML: {exc}")
                else:
                    if not projected_root.tag.endswith("svg"):
                        errors.append(f"site/boards/{projected_svg_rel} root is not <svg>")
                    projected_text = projected_svg_path.read_text(encoding="utf-8")
                    if model["name"] not in projected_text:
                        errors.append(f"site/boards/{projected_svg_rel} is missing the model title")
                    for node_id in expected_ids:
                        if node_id not in projected_text:
                            errors.append(f"site/boards/{projected_svg_rel} is missing node {node_id}")
                if projected_svg_rel in detail_html:
                    errors.append(f"site/model/{model_slug}/index.html embeds its audit SVG")
            if f'model/{model_slug}/index.html' not in index_html:
                errors.append(f"main index is missing {model_slug}")

        primary_model = min(models, key=lambda item: item["priority"])
        primary_slug = primary_model["slug"]

        legacy_detail_path = SITE / "construction" / slug / "index.html"
        legacy_detail_html = (
            legacy_detail_path.read_text(encoding="utf-8")
            if legacy_detail_path.exists() else ""
        )
        redirect_target = f"../../model/{primary_slug}/index.html"
        if redirect_target not in legacy_detail_html:
            errors.append(f"site/construction/{slug}/index.html is not a model redirect")

        old_model_path = SITE / "model" / f"{slug}-construction-regulations" / "index.html"
        old_model_html = old_model_path.read_text(encoding="utf-8") if old_model_path.exists() else ""
        if f"../{primary_slug}/index.html" not in old_model_html:
            errors.append(f"legacy model/{slug}-construction-regulations is not redirected")
        if 'data-a="construction"' not in index_html:
            errors.append("main index is missing the construction axis")

        bundle_path = ROOT / "dist" / f"{slug}.html"
        bundle_html = bundle_path.read_text(encoding="utf-8") if bundle_path.exists() else ""
        expected_tab_indexes = range(3, 3 + len(models))
        if any(f'data-i="{index}"' not in bundle_html for index in expected_tab_indexes):
            errors.append(f"dist/{slug}.html does not contain every construction tab")
        for model in models:
            short_name = model["name"].removeprefix(f'{data["country"]["name"]} ')
            if short_name not in bundle_html:
                errors.append(f"dist/{slug}.html is missing construction tab {short_name!r}")

        pipeline_path = SITE / "model" / f"{slug}-oda-project-pipeline" / "index.html"
        pipeline_html = pipeline_path.read_text(encoding="utf-8") if pipeline_path.exists() else ""
        if (
            f'href="../{primary_slug}/index.html"' not in pipeline_html
            or "이 국가의 제도 3/6" not in pipeline_html
        ):
            errors.append(f"{slug} model navigation does not continue from 03 to 04")

    if errors:
        for error in errors:
            print(f"ERROR {error}")
        print(f"FAILED: {len(errors)} construction site error(s)")
        return 1
    print(
        f"OK: {countries} construction country source(s), three-axis interactive boards, "
        "legacy redirects, and korea100studio-audited public board(s)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
