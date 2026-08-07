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
        if len(models) != 3:
            errors.append(f"{slug} must expose three construction models, got {len(models)}")
        for model in models:
            if not model["canvas"].get("applicability"):
                errors.append(f"{model['slug']} has a blank applicability card")
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
            if not refs:
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
            process = model["process"]
            canvas = model["canvas"]
            has_statutory_nodes = any(
                node.get("workflow_kind") == "statutory"
                for node in process["nodes"]
            )
            oda_only_model = not has_statutory_nodes
            oda_only_permit_model = bool(
                oda_only_model and spec and spec.get("id") == "permit-environment"
            )
            representative_two_gate_model = bool(
                oda_only_permit_model
                and model.get("countryKey") in {"pakistan", "fiji"}
            )
            procedure = canvas.get("procedure")
            if not isinstance(procedure, list):
                errors.append(f"{model_slug} canvas procedure must be a list")
            else:
                if len(procedure) != len(process["nodes"]):
                    errors.append(
                        f"{model_slug} canvas procedure count differs from process nodes: "
                        f"expected {len(process['nodes'])}, got {len(procedure)}"
                    )
                if not 7 <= len(procedure) <= 8:
                    errors.append(
                        f"{model_slug} canvas procedure must contain 7-8 steps, "
                        f"got {len(procedure)}"
                    )
                if oda_only_model and len(procedure) != 7:
                    errors.append(
                        f"{model_slug} ODA-only workflow must contain 7 steps, "
                        f"got {len(procedure)}"
                    )

            selected_gate_orders = list(dict.fromkeys(
                order
                for node in process["nodes"]
                for order in node.get("gate_orders", [])
            ))
            official_gates = canvas.get("officialGates")
            if not isinstance(official_gates, list):
                errors.append(f"{model_slug} canvas officialGates must be a list")
            elif any(
                not isinstance(item, dict)
                or not isinstance(item.get("order"), int)
                for item in official_gates
            ):
                errors.append(f"{model_slug} canvas officialGates contains an invalid Gate")
            else:
                actual_gate_orders = [item["order"] for item in official_gates]
                if (
                    len(actual_gate_orders) != len(selected_gate_orders)
                    or set(actual_gate_orders) != set(selected_gate_orders)
                ):
                    errors.append(
                        f"{model_slug} canvas official Gate orders differ: "
                        f"expected unique {selected_gate_orders}, got {actual_gate_orders}"
                    )
                if representative_two_gate_model and len(official_gates) != 2:
                    errors.append(
                        f"{model_slug} representative permit workflow must expose 2 official Gates, "
                        f"got {len(official_gates)}"
                    )

            if oda_only_permit_model:
                gate_named_nodes = [
                    node["id"]
                    for node in process["nodes"]
                    if "gate" in node.get("name", "").casefold()
                ]
                if gate_named_nodes:
                    errors.append(
                        f"{model_slug} ODA-only node names must not claim Gate status: "
                        f"{gate_named_nodes}"
                    )

            if oda_only_model:
                for edge in process["edges"]:
                    if edge.get("type") != "loop":
                        continue
                    label = edge.get("label", "")
                    forbidden_terms = [
                        term for term in ("재접수", "불복") if term in label
                    ]
                    if forbidden_terms:
                        errors.append(
                            f"{model_slug} ODA-only loop edge {edge.get('id')} "
                            f"claims an unverified official path: {forbidden_terms}"
                        )

            decision_branches = canvas.get("decisionBranches")
            if not isinstance(decision_branches, list):
                errors.append(f"{model_slug} canvas decisionBranches must be a list")
            else:
                branch_states = [
                    item.get("state") if isinstance(item, dict) else None
                    for item in decision_branches
                ]
                if len(decision_branches) != 3 or set(branch_states) != {
                    "success", "rework", "reject"
                }:
                    errors.append(
                        f"{model_slug} must expose success/rework/reject decision branches, "
                        f"got {branch_states}"
                    )

            workflow_disclosure = canvas.get("workflowDisclosure")
            if (
                not isinstance(workflow_disclosure, str)
                or not workflow_disclosure.strip()
            ):
                errors.append(f"{model_slug} canvas lacks a workflow disclosure")
            legal_basis = canvas.get("legalBasis")
            reference_basis = canvas.get("referenceBasis")
            if not isinstance(legal_basis, list) or not isinstance(reference_basis, list):
                errors.append(
                    f"{model_slug} must separate legalBasis and referenceBasis lists"
                )
            else:
                if any(item.get("status") != "in_force" for item in legal_basis):
                    errors.append(
                        f"{model_slug} legalBasis contains a non-current instrument"
                    )
                if any(item.get("status") == "in_force" for item in reference_basis):
                    errors.append(
                        f"{model_slug} referenceBasis contains an in-force instrument"
                    )
            if not 7 <= len(process["nodes"]) <= 8:
                errors.append(f"{model_slug} must render 7-8 nodes, got {len(process['nodes'])}")
            if len(process["lanes"]) < 3:
                errors.append(f"{model_slug} must render at least 3 lanes")
            if len(process["stages"]) < 4:
                errors.append(f"{model_slug} must render at least 4 stages")
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
                "근거 상태",
                f'{model["priority"]:02d} · {model["name"]}',
                "업무 구간",
                "ODA 사업팀",
                "<span>업무절차</span>",
                "<span>국가별 공식 결정 Gate</span>",
                "<span>업무 구간</span>",
                'data-state="success"',
                'data-state="rework"',
                'data-state="reject"',
            ):
                if marker not in detail_html:
                    errors.append(f"site/model/{model_slug}/index.html is missing {marker!r}")
            if not re.search(r'class="[^"]*\bdecision-branches\b[^"]*"', detail_html):
                errors.append(
                    f"site/model/{model_slug}/index.html is missing the decision branch panel"
                )
            if not re.search(r'class="[^"]*\bedge-label\b[^"]*"', detail_html):
                errors.append(
                    f"site/model/{model_slug}/index.html is missing edge-label rendering"
                )
            if not re.search(r"if\s*\(\s*ed\.label\s*\)", detail_html):
                errors.append(
                    f"site/model/{model_slug}/index.html does not guard edge-label rendering"
                )
            if not re.search(
                r"loop\s*:\s*cs\.getPropertyValue\(\s*['\"]--back['\"]\s*\)\.trim\(\)",
                detail_html,
            ):
                errors.append(
                    f"site/model/{model_slug}/index.html does not use --back for loop edges"
                )
            if not re.search(
                r"if\s*\(\s*ed\.type\s*===\s*['\"]loop['\"]"
                r"[^)]*ed\.label[^)]*\)\s*\{"
                r".{0,1200}?return\s+loop\s*;",
                detail_html,
                re.DOTALL,
            ):
                errors.append(
                    f"site/model/{model_slug}/index.html lacks fixed loop-route early return"
                )
            if isinstance(official_gates, list):
                gate_count = len(official_gates)
                gate_heading = f"국가별 공식 결정 Gate · {gate_count}개"
                if gate_heading not in detail_html:
                    errors.append(
                        f"site/model/{model_slug}/index.html is missing "
                        f"the official Gate-count heading {gate_heading!r}"
                    )
                for local_order in range(1, gate_count + 1):
                    local_label = f"Gate {local_order}/{gate_count}"
                    if local_label not in detail_html:
                        errors.append(
                            f"site/model/{model_slug}/index.html is missing "
                            f"local Gate label {local_label!r}"
                        )
            if isinstance(reference_basis, list) and reference_basis:
                if "관련 공식자료·현행성 확인대상" not in detail_html:
                    errors.append(
                        f"site/model/{model_slug}/index.html does not separate unverified sources"
                    )
            if has_statutory_nodes and "법정절차" not in detail_html:
                errors.append(
                    f"site/model/{model_slug}/index.html lacks the statutory-procedure badge"
                )
            expected_ids = [node["id"] for node in model["process"]["nodes"]]
            node_buttons = re.findall(r'<button class="node" data-id="([^"]+)"', detail_html)
            if len(node_buttons) != len(expected_ids) or set(node_buttons) != set(expected_ids):
                errors.append(
                    f"site/model/{model_slug}/index.html node buttons differ: "
                    f"expected {expected_ids}, got {node_buttons}"
                )
            serialized = re.search(
                r"var NODES=(\{.*?\});\nvar EDGES=(\[.*?\]);",
                detail_html,
                re.DOTALL,
            )
            if not serialized:
                errors.append(f"site/model/{model_slug}/index.html is missing serialized NODES/EDGES")
            else:
                try:
                    serialized_nodes = json.loads(serialized.group(1))
                    serialized_edges = json.loads(serialized.group(2))
                except json.JSONDecodeError as exc:
                    errors.append(f"site/model/{model_slug}/index.html has invalid board JSON: {exc}")
                else:
                    if list(serialized_nodes) != expected_ids:
                        errors.append(
                            f"site/model/{model_slug}/index.html serialized node order differs: "
                            f"expected {expected_ids}, got {list(serialized_nodes)}"
                        )
                    expected_edge_ids = [edge["id"] for edge in process["edges"]]
                    actual_edge_ids = [edge.get("id") for edge in serialized_edges]
                    if actual_edge_ids != expected_edge_ids:
                        errors.append(
                            f"site/model/{model_slug}/index.html serialized edges differ: "
                            f"expected {expected_edge_ids}, got {actual_edge_ids}"
                        )
                    loop_edges = [
                        edge for edge in serialized_edges if edge.get("type") == "loop"
                    ]
                    if not loop_edges:
                        errors.append(
                            f"site/model/{model_slug}/index.html has no conditional loop edge"
                        )
                    for edge in loop_edges:
                        label = edge.get("label")
                        if oda_only_model and (
                            not isinstance(label, str) or "시" not in label
                        ):
                            errors.append(
                                f"site/model/{model_slug}/index.html loop edge "
                                f"{edge.get('id')} lacks a conditional label: {label!r}"
                            )
                    for node_id, node in serialized_nodes.items():
                        if not node.get("action") or not node.get("output_documents"):
                            errors.append(
                                f"site/model/{model_slug}/index.html node {node_id} lacks action/output detail"
                            )
                        if not node.get("legal_basis"):
                            errors.append(
                                f"site/model/{model_slug}/index.html node {node_id} lacks legal basis"
                            )
                        if "confidence" in node:
                            errors.append(
                                f"site/model/{model_slug}/index.html node {node_id} "
                                "exposes a synthetic numeric legal confidence"
                            )
                        if not node.get("evidence_status"):
                            errors.append(
                                f"site/model/{model_slug}/index.html node {node_id} lacks evidence status"
                            )
                        source_node = next(
                            item for item in board["nodes"] if item["id"] == node_id
                        )
                        expected_scope = source_node.get("basisScope", "node")
                        if node.get("basis_scope") != expected_scope:
                            errors.append(
                                f"site/model/{model_slug}/index.html node {node_id} "
                                f"basis scope differs: expected {expected_scope!r}"
                            )
                    if data.get("generatedFrom") and "축 전체 관련 제도 근거" not in detail_html:
                        errors.append(
                            f"site/model/{model_slug}/index.html does not disclose axis-level basis scope"
                        )
                    if (
                        model["verification"]["status"] != "article-verified"
                        and "세부 조문의 문언 일치나 개별 사업 적용판정을 뜻하지 않습니다" not in detail_html
                    ):
                        errors.append(
                            f"site/model/{model_slug}/index.html overstates non-article verification"
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
