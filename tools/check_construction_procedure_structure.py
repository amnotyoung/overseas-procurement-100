#!/usr/bin/env python3
"""Guard the 132 public construction workflows against accidental flattening.

Reader-facing wording may change, but node order, actors, edges, decision Gates,
branch states, and direct legal references must stay stable unless the reviewed
fingerprint fixture is intentionally refreshed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "construction-regulations"
FIXTURE = DATA_DIR / "catalog" / "procedure-structure-fingerprints.json"


def canonical_model(data: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    nodes_by_id = {item["id"]: item for item in data["processBoard"]["nodes"]}
    stage_positions = {
        stage: index for index, stage in enumerate(data["processBoard"]["stages"])
    }
    nodes = [nodes_by_id[ident] for ident in spec["nodeIds"]]
    gate_orders = {
        order for node in nodes for order in node.get("gateOrders", [])
    }
    gates = [
        {
            "order": item["order"],
            "dependsOn": item.get("dependsOn", []),
        }
        for item in data.get("permitPath", [])
        if item["order"] in gate_orders
    ]
    return {
        "modelId": spec.get("id"),
        "slug": spec["slug"],
        "procedureStatus": spec.get("procedureStatus"),
        "nodeIds": spec["nodeIds"],
        "requirementIds": spec.get("requirementIds", []),
        "nodes": [
            {
                "id": node["id"],
                "lane": node["lane"],
                "stageIndex": stage_positions[node["stage"]],
                "emphasis": node.get("emphasis"),
                "kind": node.get("kind"),
                "basisScope": node.get("basisScope"),
                "authorityIds": node.get("authorityIds", []),
                "requirementIds": node.get("requirementIds", []),
                "questionIds": node.get("questionIds", []),
                "gateOrders": node.get("gateOrders", []),
                "refs": [
                    {
                        "instrumentId": ref.get("instrumentId"),
                        "provisions": ref.get("provisions", []),
                    }
                    for ref in node.get("refs", [])
                ],
            }
            for node in nodes
        ],
        "edges": [
            {
                "source": edge["source"],
                "target": edge["target"],
                "type": edge["type"],
            }
            for edge in spec.get("edges", [])
        ],
        "gates": gates,
        "branchStates": [
            item.get("state") for item in spec.get("decisionBranches", [])
        ],
    }


def fingerprint(value: dict[str, Any]) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def fingerprints_from_records(records: list[dict[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for data in records:
        for spec in data.get("publicModels", []):
            key = f'{data["slug"]}:{spec["id"]}'
            result[key] = fingerprint(canonical_model(data, spec))
    return dict(sorted(result.items()))


def current_records() -> list[dict[str, Any]]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(DATA_DIR.glob("*.json"))
        if path.name != "manifest.json"
    ]


def records_from_git(ref: str) -> list[dict[str, Any]]:
    names = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", ref, "data/construction-regulations"],
        cwd=ROOT,
        text=True,
    ).splitlines()
    records = []
    for name in names:
        if not name.endswith(".json") or name.endswith("/manifest.json"):
            continue
        if "/catalog/" in name:
            continue
        raw = subprocess.check_output(
            ["git", "show", f"{ref}:{name}"], cwd=ROOT, text=True
        )
        records.append(json.loads(raw))
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--emit-from-git",
        metavar="REF",
        help="print a fingerprint fixture generated from a reviewed git ref",
    )
    args = parser.parse_args()
    if args.emit_from_git:
        print(json.dumps(
            fingerprints_from_records(records_from_git(args.emit_from_git)),
            ensure_ascii=False,
            indent=2,
        ))
        return 0

    if not FIXTURE.exists():
        print(f"ERROR missing fixture: {FIXTURE.relative_to(ROOT)}")
        return 1
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    actual = fingerprints_from_records(current_records())
    errors = []
    for key in sorted(set(expected) | set(actual)):
        if key not in expected:
            errors.append(f"unexpected model {key}")
        elif key not in actual:
            errors.append(f"missing model {key}")
        elif expected[key] != actual[key]:
            errors.append(f"structure changed for {key}")
    if errors:
        for error in errors:
            print(f"ERROR {error}")
        print(f"FAILED: {len(errors)} public workflow structure mismatch(es)")
        return 1
    print(f"OK: {len(actual)} public construction workflow structures match the reviewed baseline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
