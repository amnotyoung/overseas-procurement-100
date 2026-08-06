#!/usr/bin/env python3
"""Validate the ODA construction-regulation sidecar.

Usage:
    python3 tools/validate_construction_regulations.py
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "construction-regulations"
MANIFEST_PATH = DATA_DIR / "manifest.json"

STAGES = {
    "site-and-land",
    "programming",
    "design",
    "environment",
    "permit",
    "pre-construction",
    "construction",
    "completion",
    "operation",
}
INSTRUMENT_STATUSES = {"in_force", "superseded", "pending", "continuity_unverified"}
VERIFICATION_LEVELS = {"article-verified", "law-linked", "source-linked", "needs-review"}
REQUIREMENT_STATUSES = {"confirmed", "conditional", "unresolved"}
OVERLAY_STATUSES = {"confirmed", "conditional", "unresolved"}
CONCLUSION_CONFIDENCE = {"confirmed", "conditional", "unresolved"}
BOARD_EMPHASIS = {"lead", "key", "bottleneck", "loop", "normal"}
BOARD_EDGE_TYPES = {"sequence", "message", "loop"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class Validation:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, where: str, message: str) -> None:
        self.errors.append(f"{where}: {message}")

    def warn(self, where: str, message: str) -> None:
        self.warnings.append(f"{where}: {message}")


def read_json(path: Path, result: Validation) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        result.error(str(path.relative_to(ROOT)), "file not found")
        return None
    except json.JSONDecodeError as exc:
        result.error(str(path.relative_to(ROOT)), f"invalid JSON at line {exc.lineno}: {exc.msg}")
        return None
    if not isinstance(value, dict):
        result.error(str(path.relative_to(ROOT)), "top-level value must be an object")
        return None
    return value


def required(obj: dict[str, Any], keys: tuple[str, ...], where: str, result: Validation) -> None:
    for key in keys:
        if key not in obj:
            result.error(where, f"missing required field {key!r}")
        elif obj[key] in (None, "", []):
            result.error(where, f"required field {key!r} is empty")


def validate_date(value: Any, where: str, result: Validation) -> date | None:
    if not isinstance(value, str) or not DATE_RE.match(value):
        result.error(where, "must be YYYY-MM-DD")
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        result.error(where, "is not a valid calendar date")
        return None


def unique_ids(items: Any, label: str, path: str, result: Validation) -> dict[str, dict[str, Any]]:
    if not isinstance(items, list):
        result.error(path, f"{label} must be an array")
        return {}
    found: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(items):
        where = f"{path}.{label}[{index}]"
        if not isinstance(item, dict):
            result.error(where, "must be an object")
            continue
        ident = item.get("id")
        if not isinstance(ident, str) or not ident:
            result.error(where, "missing non-empty id")
            continue
        if ident in found:
            result.error(where, f"duplicate id {ident!r}")
        found[ident] = item
    return found


def check_url(value: Any, where: str, result: Validation) -> None:
    if not isinstance(value, str) or not value.startswith("https://"):
        result.error(where, "must be an https URL")


def validate_basis(
    basis: Any,
    where: str,
    instruments: dict[str, dict[str, Any]],
    result: Validation,
) -> None:
    if not isinstance(basis, list):
        result.error(where, "must be an array")
        return
    for index, ref in enumerate(basis):
        ref_where = f"{where}[{index}]"
        if not isinstance(ref, dict):
            result.error(ref_where, "must be an object")
            continue
        required(ref, ("instrumentId",), ref_where, result)
        ident = ref.get("instrumentId")
        if ident not in instruments:
            result.error(ref_where, f"unknown instrumentId {ident!r}")
        provisions = ref.get("provisions")
        if not isinstance(provisions, list):
            result.error(ref_where, "provisions must be an array")


def validate_process_board(
    board: Any,
    where: str,
    authorities: dict[str, dict[str, Any]],
    instruments: dict[str, dict[str, Any]],
    requirements: dict[str, dict[str, Any]],
    permit_orders: set[int],
    result: Validation,
) -> dict[str, int]:
    """Validate the embedded korea100studio board-v1 and its trace links."""
    if not isinstance(board, dict):
        result.error(where, "must be an object")
        return {"board_nodes": 0, "board_edges": 0}
    required(
        board,
        ("schema_version", "profile", "title", "subtitle", "lanes", "stages", "nodes", "edges"),
        where,
        result,
    )
    if board.get("schema_version") != 1:
        result.error(f"{where}.schema_version", "must be board-v1 schema version 1")
    if board.get("profile") != "gov":
        result.error(f"{where}.profile", "construction boards must use the gov profile")

    lanes = board.get("lanes")
    stages = board.get("stages")
    lane_set = set(lanes) if isinstance(lanes, list) and all(isinstance(x, str) for x in lanes) else set()
    stage_set = set(stages) if isinstance(stages, list) and all(isinstance(x, str) for x in stages) else set()
    if not lane_set or not isinstance(lanes, list) or len(lane_set) != len(lanes):
        result.error(f"{where}.lanes", "must be a non-empty array of unique strings")
    if not stage_set or not isinstance(stages, list) or len(stage_set) != len(stages):
        result.error(f"{where}.stages", "must be a non-empty array of unique strings")

    nodes = unique_ids(board.get("nodes"), "nodes", where, result)
    used_lanes: set[str] = set()
    used_stages: set[str] = set()
    mapped_gates: set[int] = set()
    for ident, node in nodes.items():
        node_where = f"{where}.nodes[{ident}]"
        required(node, ("lane", "stage", "label", "emphasis", "refs"), node_where, result)
        lane = node.get("lane")
        stage = node.get("stage")
        if lane not in lane_set:
            result.error(node_where, f"unknown lane {lane!r}")
        else:
            used_lanes.add(lane)
        if stage not in stage_set:
            result.error(node_where, f"unknown stage {stage!r}")
        else:
            used_stages.add(stage)
        if node.get("emphasis") not in BOARD_EMPHASIS:
            result.error(node_where, f"unknown emphasis {node.get('emphasis')!r}")
        for authority_id in node.get("authorityIds", []):
            if authority_id not in authorities:
                result.error(node_where, f"authorityIds references unknown authority {authority_id!r}")
        for requirement_id in node.get("requirementIds", []):
            if requirement_id not in requirements:
                result.error(node_where, f"requirementIds references unknown requirement {requirement_id!r}")
        gate_orders = node.get("gateOrders", [])
        if not isinstance(gate_orders, list):
            result.error(node_where, "gateOrders must be an array")
        else:
            for gate_order in gate_orders:
                if gate_order not in permit_orders:
                    result.error(node_where, f"gateOrders references unknown permit order {gate_order!r}")
                elif isinstance(gate_order, int):
                    mapped_gates.add(gate_order)
        refs = node.get("refs")
        if not isinstance(refs, list) or not refs:
            result.error(node_where, "refs must be a non-empty array")
        else:
            for index, ref in enumerate(refs):
                ref_where = f"{node_where}.refs[{index}]"
                if not isinstance(ref, dict):
                    result.error(ref_where, "must be an object")
                    continue
                required(ref, ("source", "instrumentId", "provisions"), ref_where, result)
                if ref.get("instrumentId") not in instruments:
                    result.error(ref_where, f"unknown instrumentId {ref.get('instrumentId')!r}")
                if not isinstance(ref.get("provisions"), list):
                    result.error(ref_where, "provisions must be an array")

    for lane in lane_set - used_lanes:
        result.error(f"{where}.lanes", f"declared lane {lane!r} has no nodes")
    for stage in stage_set - used_stages:
        result.error(f"{where}.stages", f"declared stage {stage!r} has no nodes")
    for order in permit_orders - mapped_gates:
        result.error(f"{where}.nodes", f"permitPath order {order} is not mapped by any board node")

    edges = unique_ids(board.get("edges"), "edges", where, result)
    connected: set[str] = set()
    for ident, edge in edges.items():
        edge_where = f"{where}.edges[{ident}]"
        required(edge, ("source", "target", "type"), edge_where, result)
        source = edge.get("source")
        target = edge.get("target")
        if source not in nodes:
            result.error(edge_where, f"unknown source node {source!r}")
        else:
            connected.add(source)
        if target not in nodes:
            result.error(edge_where, f"unknown target node {target!r}")
        else:
            connected.add(target)
        if source == target:
            result.error(edge_where, "self-referencing edges are not allowed")
        if edge.get("type") not in BOARD_EDGE_TYPES:
            result.error(edge_where, f"unknown edge type {edge.get('type')!r}")
    for ident in set(nodes) - connected:
        result.error(f"{where}.nodes[{ident}]", "isolated node has no incoming or outgoing edge")

    return {"board_nodes": len(nodes), "board_edges": len(edges)}


def validate_country(data: dict[str, Any], path: Path, manifest: dict[str, Any], result: Validation) -> dict[str, int]:
    rel = str(path.relative_to(ROOT))
    required(
        data,
        (
            "schemaVersion",
            "slug",
            "asOfDate",
            "country",
            "purpose",
            "verification",
            "processBoard",
            "authorities",
            "instruments",
            "requirements",
            "permitPath",
            "siteOverlays",
            "openQuestions",
            "fieldworkChecklist",
            "reportReadyConclusions",
        ),
        rel,
        result,
    )
    if data.get("schemaVersion") != manifest.get("schemaVersion"):
        result.error(rel, "schemaVersion does not match manifest")
    slug = data.get("slug")
    if slug != path.stem:
        result.error(rel, f"slug {slug!r} does not match filename")
    as_of = validate_date(data.get("asOfDate"), f"{rel}.asOfDate", result)

    country = data.get("country")
    if not isinstance(country, dict):
        result.error(f"{rel}.country", "must be an object")
    else:
        required(country, ("name", "nameEn", "iso3", "region"), f"{rel}.country", result)
        iso3 = country.get("iso3")
        if not isinstance(iso3, str) or not re.fullmatch(r"[A-Z]{3}", iso3):
            result.error(f"{rel}.country.iso3", "must be three uppercase letters")

    verification = data.get("verification")
    if not isinstance(verification, dict):
        result.error(f"{rel}.verification", "must be an object")
    else:
        required(verification, ("status", "verifiedAt", "method", "scope"), f"{rel}.verification", result)
        if verification.get("status") not in VERIFICATION_LEVELS:
            result.error(f"{rel}.verification.status", "unknown verification level")
        verified_at = validate_date(verification.get("verifiedAt"), f"{rel}.verification.verifiedAt", result)
        if as_of and verified_at and verified_at > as_of:
            result.error(f"{rel}.verification.verifiedAt", "cannot be later than asOfDate")

    authorities = unique_ids(data.get("authorities"), "authorities", rel, result)
    for ident, authority in authorities.items():
        where = f"{rel}.authorities[{ident}]"
        required(authority, ("name", "nameKo", "role", "verificationLevel"), where, result)
        if authority.get("verificationLevel") not in VERIFICATION_LEVELS:
            result.error(where, "unknown verificationLevel")
        if "officialUrl" in authority:
            check_url(authority["officialUrl"], f"{where}.officialUrl", result)

    instruments = unique_ids(data.get("instruments"), "instruments", rel, result)
    for ident, instrument in instruments.items():
        where = f"{rel}.instruments[{ident}]"
        required(
            instrument,
            ("title", "titleKo", "kind", "status", "officialUrl", "verificationLevel"),
            where,
            result,
        )
        status = instrument.get("status")
        level = instrument.get("verificationLevel")
        if status not in INSTRUMENT_STATUSES:
            result.error(where, f"unknown status {status!r}")
        if level not in VERIFICATION_LEVELS:
            result.error(where, f"unknown verificationLevel {level!r}")
        check_url(instrument.get("officialUrl"), f"{where}.officialUrl", result)
        if "officialPdfUrl" in instrument:
            check_url(instrument["officialPdfUrl"], f"{where}.officialPdfUrl", result)
        issued = None
        if "issuedOn" in instrument:
            issued = validate_date(instrument["issuedOn"], f"{where}.issuedOn", result)
        if status == "in_force" and not issued:
            result.error(where, "in_force instrument must have issuedOn")
        if status == "in_force" and issued and as_of and issued > as_of:
            result.error(where, "future instrument cannot be in_force")
        if level == "article-verified" and not instrument.get("articlesChecked"):
            result.error(where, "article-verified instrument needs articlesChecked")
        if status == "superseded" and not instrument.get("replacedBy"):
            result.error(where, "superseded instrument needs replacedBy")
        for field in ("replaces", "replacedBy"):
            for ref in instrument.get(field, []):
                if ref not in instruments:
                    result.error(where, f"{field} references unknown instrument {ref!r}")

    requirements = unique_ids(data.get("requirements"), "requirements", rel, result)
    for ident, item in requirements.items():
        where = f"{rel}.requirements[{ident}]"
        required(
            item,
            (
                "stage",
                "topic",
                "status",
                "applicability",
                "requirement",
                "authorityIds",
                "legalBasis",
                "evidenceToObtain",
                "reportUse",
            ),
            where,
            result,
        )
        if item.get("stage") not in STAGES:
            result.error(where, f"unknown lifecycle stage {item.get('stage')!r}")
        if item.get("status") not in REQUIREMENT_STATUSES:
            result.error(where, f"unknown requirement status {item.get('status')!r}")
        authority_ids = item.get("authorityIds")
        if not isinstance(authority_ids, list):
            result.error(where, "authorityIds must be an array")
        else:
            for authority_id in authority_ids:
                if authority_id not in authorities:
                    result.error(where, f"unknown authorityId {authority_id!r}")
        validate_basis(item.get("legalBasis"), f"{where}.legalBasis", instruments, result)
        if item.get("status") in {"confirmed", "conditional"} and not item.get("legalBasis"):
            result.error(where, "confirmed/conditional requirement needs legalBasis")
        if not isinstance(item.get("evidenceToObtain"), list) or not item.get("evidenceToObtain"):
            result.error(where, "evidenceToObtain must be a non-empty array")

    permit_path = data.get("permitPath")
    permit_orders: set[int] = set()
    if not isinstance(permit_path, list):
        result.error(f"{rel}.permitPath", "must be an array")
    else:
        for index, gate in enumerate(permit_path):
            where = f"{rel}.permitPath[{index}]"
            if not isinstance(gate, dict):
                result.error(where, "must be an object")
                continue
            required(gate, ("order", "gate", "decision", "output"), where, result)
            if "dependsOn" not in gate:
                result.error(where, "missing required field 'dependsOn'")
            elif not isinstance(gate["dependsOn"], list):
                result.error(where, "dependsOn must be an array")
            order = gate.get("order")
            if not isinstance(order, int) or order < 1:
                result.error(where, "order must be a positive integer")
            elif order in permit_orders:
                result.error(where, f"duplicate order {order}")
            else:
                permit_orders.add(order)
            for dependency in gate.get("dependsOn", []):
                if not isinstance(dependency, int) or (isinstance(order, int) and dependency >= order):
                    result.error(where, f"invalid dependency {dependency!r}")
        if permit_orders and permit_orders != set(range(1, max(permit_orders) + 1)):
            result.error(f"{rel}.permitPath", "orders must be contiguous from 1")

    board_counts = validate_process_board(
        data.get("processBoard"),
        f"{rel}.processBoard",
        authorities,
        instruments,
        requirements,
        permit_orders,
        result,
    )

    overlays = unique_ids(data.get("siteOverlays"), "siteOverlays", rel, result)
    for ident, overlay in overlays.items():
        where = f"{rel}.siteOverlays[{ident}]"
        required(
            overlay,
            ("area", "status", "rule", "legalBasis", "missingEvidence", "consequence"),
            where,
            result,
        )
        if overlay.get("status") not in OVERLAY_STATUSES:
            result.error(where, f"unknown status {overlay.get('status')!r}")
        validate_basis(overlay.get("legalBasis"), f"{where}.legalBasis", instruments, result)

    questions = unique_ids(data.get("openQuestions"), "openQuestions", rel, result)
    for ident, question in questions.items():
        where = f"{rel}.openQuestions[{ident}]"
        required(
            question,
            ("blocking", "stage", "question", "whyItMatters", "evidenceNeeded", "confirmWith", "owner"),
            where,
            result,
        )
        if not isinstance(question.get("blocking"), bool):
            result.error(where, "blocking must be boolean")
        if question.get("stage") not in STAGES:
            result.error(where, f"unknown lifecycle stage {question.get('stage')!r}")
        if question.get("blocking") and not question.get("evidenceNeeded"):
            result.error(where, "blocking question needs evidenceNeeded")
        for authority_id in question.get("confirmWith", []):
            if authority_id not in authorities:
                result.error(where, f"confirmWith references unknown authority {authority_id!r}")

    checklist = unique_ids(data.get("fieldworkChecklist"), "fieldworkChecklist", rel, result)
    for ident, item in checklist.items():
        required(item, ("phase", "check", "output"), f"{rel}.fieldworkChecklist[{ident}]", result)

    conclusions = unique_ids(data.get("reportReadyConclusions"), "reportReadyConclusions", rel, result)
    for ident, conclusion in conclusions.items():
        where = f"{rel}.reportReadyConclusions[{ident}]"
        required(conclusion, ("confidence", "text", "basis"), where, result)
        if conclusion.get("confidence") not in CONCLUSION_CONFIDENCE:
            result.error(where, f"unknown confidence {conclusion.get('confidence')!r}")
        for instrument_id in conclusion.get("basis", []):
            if instrument_id not in instruments:
                result.error(where, f"basis references unknown instrument {instrument_id!r}")

    return {
        "authorities": len(authorities),
        "instruments": len(instruments),
        "requirements": len(requirements),
        "questions": len(questions),
        **board_counts,
    }


def main() -> int:
    result = Validation()
    manifest = read_json(MANIFEST_PATH, result)
    if manifest is None:
        for message in result.errors:
            print(f"ERROR {message}")
        return 1

    required(manifest, ("project", "schemaVersion", "updatedAt", "lifecycleStages", "countries"), "manifest", result)
    validate_date(manifest.get("updatedAt"), "manifest.updatedAt", result)
    if set(manifest.get("lifecycleStages", [])) != STAGES:
        result.error("manifest.lifecycleStages", "must match the lifecycle-stage contract")
    if set(manifest.get("verificationLevels", [])) != VERIFICATION_LEVELS:
        result.error("manifest.verificationLevels", "must match the verification-level contract")

    manifest_countries: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(manifest.get("countries", [])):
        where = f"manifest.countries[{index}]"
        if not isinstance(item, dict):
            result.error(where, "must be an object")
            continue
        required(item, ("slug", "name", "nameEn", "iso3", "status", "verification", "asOfDate"), where, result)
        slug = item.get("slug")
        if slug in manifest_countries:
            result.error(where, f"duplicate slug {slug!r}")
        elif isinstance(slug, str):
            manifest_countries[slug] = item
        if item.get("verification") not in VERIFICATION_LEVELS:
            result.error(where, "unknown verification level")
        validate_date(item.get("asOfDate"), f"{where}.asOfDate", result)

    country_paths = sorted(path for path in DATA_DIR.glob("*.json") if path.name != "manifest.json")
    file_slugs = {path.stem for path in country_paths}
    missing_files = set(manifest_countries) - file_slugs
    extra_files = file_slugs - set(manifest_countries)
    for slug in sorted(missing_files):
        result.error("manifest.countries", f"missing data file for {slug!r}")
    for slug in sorted(extra_files):
        result.error("manifest.countries", f"data file {slug!r} is not registered")

    totals = {
        "authorities": 0,
        "instruments": 0,
        "requirements": 0,
        "questions": 0,
        "board_nodes": 0,
        "board_edges": 0,
    }
    for path in country_paths:
        data = read_json(path, result)
        if data is None:
            continue
        counts = validate_country(data, path, manifest, result)
        for key, value in counts.items():
            totals[key] += value
        manifest_item = manifest_countries.get(path.stem)
        if manifest_item:
            for field in ("asOfDate",):
                if data.get(field) != manifest_item.get(field):
                    result.error(str(path.relative_to(ROOT)), f"{field} does not match manifest")
            country = data.get("country", {})
            for field in ("name", "nameEn", "iso3"):
                if country.get(field) != manifest_item.get(field):
                    result.error(str(path.relative_to(ROOT)), f"country.{field} does not match manifest")

    for message in result.warnings:
        print(f"WARN  {message}")
    if result.errors:
        for message in result.errors:
            print(f"ERROR {message}")
        print(f"FAILED: {len(result.errors)} error(s), {len(result.warnings)} warning(s)")
        return 1

    print(
        "OK: "
        f"{len(country_paths)} country file(s), "
        f"{totals['authorities']} authorities, "
        f"{totals['instruments']} instruments, "
        f"{totals['requirements']} requirements, "
        f"{totals['questions']} open questions, "
        f"{totals['board_nodes']} board nodes, "
        f"{totals['board_edges']} board edges"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
