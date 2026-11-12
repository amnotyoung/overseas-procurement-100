#!/usr/bin/env python3
"""원천에 명시된 단계별 기관 배정을 반영하고 근거 참조를 검사한다."""
import json
from pathlib import Path

from procurement_evidence import assigned_actor, canvas_projections, node_errors

INST_DIR = Path(__file__).resolve().parent.parent / "data" / "institutions"


def sync(data):
    changed = False
    for node in data.get("process", {}).get("nodes", []):
        actor = assigned_actor(data, node)
        if actor and node.get("actor") != actor:
            node["actor"] = actor
            changed = True
        errors = node_errors(data, node)
        if errors:
            raise ValueError(f"{data['slug']} {node['id']}: {', '.join(errors)}")
    for key, value in canvas_projections(data).items():
        if data["canvas"].get(key) != value:
            data["canvas"][key] = value
            changed = True
    return changed


def main():
    changed = 0
    for path in sorted(INST_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if sync(data):
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            changed += 1
    print(f"단계별 기관·근거 검사 완료. 기관·캔버스 갱신 {changed}건")


if __name__ == "__main__":
    main()
