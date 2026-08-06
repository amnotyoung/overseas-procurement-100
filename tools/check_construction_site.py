#!/usr/bin/env python3
"""Smoke-check generated construction pages and korea100studio SVG boards."""
from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "construction-regulations"
SITE = ROOT / "site"


def main() -> int:
    errors: list[str] = []
    index_path = SITE / "construction" / "index.html"
    index_html = index_path.read_text(encoding="utf-8") if index_path.exists() else ""
    if not index_html:
        errors.append("site/construction/index.html is missing")

    countries = 0
    for path in sorted(DATA_DIR.glob("*.json")):
        if path.name == "manifest.json":
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        slug = data["slug"]
        board = data["processBoard"]
        countries += 1

        svg_rel = f"{slug}-construction.svg"
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

        detail_path = SITE / "construction" / slug / "index.html"
        detail_html = detail_path.read_text(encoding="utf-8") if detail_path.exists() else ""
        if not detail_html:
            errors.append(f"site/construction/{slug}/index.html is missing")
        else:
            for marker in ("id=\"process-board\"", f"../../boards/{svg_rel}", "korea100studio"):
                if marker not in detail_html:
                    errors.append(f"site/construction/{slug}/index.html is missing {marker!r}")
        if f"../boards/{svg_rel}" not in index_html:
            errors.append(f"construction index is missing the {slug} board preview")

    if errors:
        for error in errors:
            print(f"ERROR {error}")
        print(f"FAILED: {len(errors)} construction site error(s)")
        return 1
    print(f"OK: {countries} construction page(s) and korea100studio board(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
