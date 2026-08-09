#!/usr/bin/env python3
"""Fail unless every public construction model exposes a researched legal procedure."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from build_site import construction_to_models

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "construction-regulations"
CATALOG_PATH = DATA_DIR / "catalog" / "baselines.json"
OVERLAY_DIR = DATA_DIR / "catalog" / "official-procedures"
REQUIRED_AXES = {"site-urban", "permit-environment", "control-completion"}
ALLOWED_STATUS = {"official-source-linked", "article-linked", "article-verified"}
PUBLICATION_SCOPES = {"national", "subnational-example"}
REGIONAL_EXAMPLE_MARKERS = (
    "대표 사례",
    "대표사례",
    "지역 사례",
    "주 사례",
    "시 사례",
    "사례기관",
    "대표 경로",
    "대표 관할",
    "공식 예시",
    "집행 예시",
    "치환",
    "전국에 일반화하지",
    "전국 공통으로 일반화할 수 없",
    "다른 지방자치단체",
    "다른 주·연방수도지구",
    "밖에서는 해당",
    "비방콕",
    "비RAJUK",
)
INTERNAL_KINDS = {"local-example", "field-verification", "project-control"}
CURRENT_SOURCE_STATUSES = {"in_force", "current_official"}
CURRENTNESS_EXCEPTION_STATUSES = {"continuity_unverified", "pending", "superseded"}


def nonempty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_overlay_axis(
    *, country_slug: str, axis: str, system: object, errors: list[str]
) -> None:
    """Validate the researched overlay itself, before generated fallbacks can hide gaps."""
    prefix = f"{country_slug}:{axis}"
    if not isinstance(system, dict):
        errors.append(f"{prefix}: axis overlay is not an object")
        return

    procedure = system.get("officialProcedure")
    if not isinstance(procedure, dict):
        errors.append(f"{prefix}: actual officialProcedure object is missing")
        return

    publication_scope = procedure.get("publicationScope")
    if publication_scope not in PUBLICATION_SCOPES:
        errors.append(
            f"{prefix}: publicationScope is {publication_scope!r}; "
            f"expected one of {sorted(PUBLICATION_SCOPES)}"
        )
        return
    if publication_scope == "subnational-example":
        return

    public_disclosure = " ".join(
        str(value or "")
        for value in (
            procedure.get("name"),
            procedure.get("scope"),
            system.get("verificationScope"),
        )
    )
    found_markers = [
        marker for marker in REGIONAL_EXAMPLE_MARKERS if marker in public_disclosure
    ]
    if found_markers:
        errors.append(
            f"{prefix}: national procedure still contains regional-example markers "
            f"{found_markers}"
        )

    if procedure.get("coverage") not in ALLOWED_STATUS:
        errors.append(
            f"{prefix}: officialProcedure coverage is {procedure.get('coverage')!r}"
        )

    steps = procedure.get("steps")
    if not isinstance(steps, list) or len(steps) < 5:
        count = len(steps) if isinstance(steps, list) else 0
        errors.append(f"{prefix}: officialProcedure has only {count} step(s)")
        steps = steps if isinstance(steps, list) else []

    gates = 0
    for index, step in enumerate(steps, 1):
        step_prefix = f"{prefix}:step-{index:02d}"
        if not isinstance(step, dict):
            errors.append(f"{step_prefix}: step is not an object")
            continue
        refs = step.get("refs")
        authority_ids = step.get("authorityIds")
        if (
            not isinstance(authority_ids, list)
            or not authority_ids
            or any(not nonempty_text(item) for item in authority_ids)
        ):
            errors.append(f"{step_prefix}: authorityIds must identify national-flow actors")
        if step.get("kind") in INTERNAL_KINDS:
            errors.append(
                f"{step_prefix}: national procedure cannot publish {step.get('kind')} nodes"
            )
        if not isinstance(refs, list) or not refs:
            errors.append(f"{step_prefix}: lacks direct refs")
        else:
            for ref_index, ref in enumerate(refs, 1):
                if not isinstance(ref, dict):
                    errors.append(
                        f"{step_prefix}:ref-{ref_index}: reference is not an object"
                    )
                    continue
                provisions = ref.get("provisions")
                if not nonempty_text(ref.get("instrumentId")):
                    errors.append(
                        f"{step_prefix}:ref-{ref_index}: instrumentId is missing"
                    )
                if (
                    not isinstance(provisions, list)
                    or not provisions
                    or any(not nonempty_text(item) for item in provisions)
                ):
                    errors.append(
                        f"{step_prefix}:ref-{ref_index}: direct provisions are missing"
                    )

        gate = step.get("permitGate")
        if gate is not None:
            gates += 1
            if not isinstance(gate, dict) or any(
                not nonempty_text(gate.get(field))
                for field in ("key", "gate", "decision", "output")
            ):
                errors.append(
                    f"{step_prefix}: permitGate needs key/gate/decision/output"
                )

    if not gates:
        errors.append(f"{prefix}: officialProcedure lacks an official permitGate")

    branches = procedure.get("decisionBranches")
    branch_states = {
        item.get("state")
        for item in branches or []
        if isinstance(item, dict)
    }
    if (
        not isinstance(branches, list)
        or len(branches) != 3
        or branch_states != {"success", "rework", "reject"}
    ):
        errors.append(
            f"{prefix}: decisionBranches must be exactly success/rework/reject"
        )
    elif any(
        not nonempty_text(item.get("label"))
        or not nonempty_text(item.get("action"))
        for item in branches
    ):
        errors.append(f"{prefix}: every decision branch needs label and action")


def main() -> int:
    errors: list[str] = []

    # A generated fallback can be structurally complete while still describing only
    # a common permit pattern.  Every overlay axis must therefore make an explicit,
    # fail-closed publication-scope decision; only national axes are public.
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    catalog_slugs = {item["slug"] for item in catalog.get("countries", [])}
    overlay_paths = sorted(OVERLAY_DIR.glob("*.json"))
    overlay_slugs = {path.stem for path in overlay_paths}
    for slug in sorted(catalog_slugs - overlay_slugs):
        errors.append(f"{slug}: country-specific official procedure overlay is missing")
    for path in overlay_paths:
        overlay = json.loads(path.read_text(encoding="utf-8"))
        systems = overlay.get("systems")
        if not isinstance(systems, dict):
            errors.append(f"{path.stem}: systems is not an object")
            continue
        axes = set(systems)
        missing_axes = REQUIRED_AXES - axes
        if missing_axes:
            errors.append(
                f"{path.stem}: official procedure overlay lacks axes {sorted(missing_axes)}"
            )
        for axis in sorted(REQUIRED_AXES & axes):
            validate_overlay_axis(
                country_slug=path.stem,
                axis=axis,
                system=systems[axis],
                errors=errors,
            )

    countries = 0
    models = 0
    for path in sorted(DATA_DIR.glob("*.json")):
        if path.name == "manifest.json":
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        countries += 1
        for model in construction_to_models(data):
            models += 1
            slug = model["slug"]
            status = model["canvas"].get("procedureStatus")
            if model.get("publicationScope") != "national":
                errors.append(f"{slug}: publishes a non-national procedure")
            public_payload = json.dumps(
                {
                    "name": model.get("name"),
                    "canvas": model.get("canvas"),
                    "process": model.get("process"),
                },
                ensure_ascii=False,
            )
            payload_markers = [
                marker
                for marker in REGIONAL_EXAMPLE_MARKERS
                if marker in public_payload
            ]
            if payload_markers:
                errors.append(
                    f"{slug}: regional-example markers {payload_markers} remain "
                    "in the rendered public payload"
                )
            nodes = model["process"]["nodes"]
            gates = model["canvas"].get("officialGates", [])
            branches = model["canvas"].get("decisionBranches", [])
            if status not in ALLOWED_STATUS:
                errors.append(f"{slug}: procedureStatus is {status!r}")
            if len(nodes) < 5:
                errors.append(f"{slug}: only {len(nodes)} public procedure node(s)")
            internal = [
                node["id"] for node in nodes
                if node.get("workflow_kind") in INTERNAL_KINDS
            ]
            if internal:
                errors.append(f"{slug}: publishes internal workflow nodes {internal}")
            if any(not node.get("legal_basis") for node in nodes):
                errors.append(f"{slug}: one or more steps lack direct legal/official basis")
            for node in nodes:
                bases = node.get("legal_basis", [])
                has_checked_current = any(
                    basis.get("status") in CURRENT_SOURCE_STATUSES
                    and nonempty_text(basis.get("status_checked_on"))
                    and nonempty_text(basis.get("status_basis"))
                    for basis in bases
                )
                has_documented_exception = any(
                    basis.get("status") == "continuity_unverified"
                    and nonempty_text(basis.get("status_basis"))
                    for basis in bases
                )
                if not (has_checked_current or has_documented_exception):
                    statuses = sorted(
                        {
                            str(basis.get("status") or "missing-status")
                            for basis in bases
                        }
                    )
                    errors.append(
                        f"{slug}:{node.get('id', '?')} {node.get('name', '')!r}: "
                        "needs a checked current source or a documented "
                        f"continuity_unverified exception (statuses={statuses})"
                    )
            # The source registry is public too.  A current source must show when and
            # why it was judged current, while every exception must explain the exact
            # continuity/replacement issue.  Do not let an unused good source mask an
            # unexplained badge elsewhere on the same page.
            for source in model.get("verification", {}).get("sources", []):
                source_id = source.get("id", "?")
                source_status = source.get("status")
                if source.get("jurisdictionScope") in {"local", "subnational"}:
                    errors.append(
                        f"{slug}:source:{source_id}: national model references "
                        f"{source.get('jurisdictionScope')} material"
                    )
                source_disclosure = " ".join(
                    str(source.get(field) or "")
                    for field in (
                        "law",
                        "officialName",
                        "scopeLabel",
                        "statusBasis",
                        "note",
                    )
                )
                source_markers = [
                    marker
                    for marker in REGIONAL_EXAMPLE_MARKERS
                    if marker in source_disclosure
                ]
                if source_markers:
                    errors.append(
                        f"{slug}:source:{source_id}: regional-example markers "
                        f"{source_markers} remain in a public source"
                    )
                if source_status in CURRENT_SOURCE_STATUSES:
                    if not (
                        nonempty_text(source.get("statusCheckedOn"))
                        and nonempty_text(source.get("statusBasis"))
                    ):
                        errors.append(
                            f"{slug}:source:{source_id}: current source needs "
                            "statusCheckedOn and statusBasis"
                        )
                elif source_status in CURRENTNESS_EXCEPTION_STATUSES:
                    if not nonempty_text(source.get("statusBasis")):
                        errors.append(
                            f"{slug}:source:{source_id}: {source_status} source "
                            "needs a concrete statusBasis"
                        )
            if not gates:
                errors.append(f"{slug}: lacks an official decision Gate")
            if {item.get("state") for item in branches} != {"success", "rework", "reject"}:
                errors.append(f"{slug}: lacks success/rework/reject decision branches")

    if countries != 44:
        errors.append(f"coverage country count differs: {countries} countries")
    if errors:
        print("FAILED: researched construction-procedure coverage is incomplete")
        for error in errors:
            print(f"- {error}")
        return 1
    print(
        f"OK: {countries} countries and {models} public national models expose "
        "researched procedures"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
