#!/usr/bin/env python3
"""Check Korean-first, once-per-page display for curated construction terms."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from build_site import (
    CONSTRUCTION_KOREAN_FIRST_TERMS,
    CONSTRUCTION_TERMINOLOGY_SKIP_KEYS,
    construction_navigation_label,
    construction_to_models,
)

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "construction-regulations"


def reader_strings(value, parent_key: str = ""):
    if parent_key in CONSTRUCTION_TERMINOLOGY_SKIP_KEYS:
        return
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from reader_strings(item, parent_key)
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from reader_strings(item, key)


def main() -> int:
    errors: list[str] = []
    models = []
    for path in sorted(DATA_DIR.glob("*.json")):
        if path.name == "manifest.json":
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        models.extend(construction_to_models(data))

    for model in models:
        strings = list(reader_strings(model))
        navigation_label = construction_navigation_label(model["name"])
        for pattern, korean in CONSTRUCTION_KOREAN_FIRST_TERMS:
            if re.search(pattern, navigation_label, re.IGNORECASE):
                errors.append(
                    f'{model["slug"]}: compact navigation repeats original term '
                    f'in {navigation_label!r}'
                )
            occurrences: list[tuple[str, re.Match]] = []
            compiled = re.compile(pattern, re.IGNORECASE)
            for text in strings:
                for match in compiled.finditer(text):
                    open_at = text.rfind("(", 0, match.start() + 1)
                    close_before = text.rfind(")", 0, match.start() + 1)
                    close_after = text.find(")", match.end())
                    if open_at > close_before and close_after >= 0:
                        parenthetical = text[open_at + 1:close_after].strip()
                        # EIA Study/EIA Licence처럼 더 긴 공식 원문명의 일부인
                        # 약어는 독립 EIA 병기가 아니므로 이 규칙에서 세지 않는다.
                        if (
                            parenthetical
                            and not re.search(r"[가-힣]", parenthetical)
                            and compiled.fullmatch(parenthetical) is None
                        ):
                            continue
                    occurrences.append((text, match))
            if len(occurrences) > 1:
                errors.append(
                    f'{model["slug"]}: {occurrences[0][1].group(0)!r} appears '
                    f"{len(occurrences)} times"
                )
            for text, match in occurrences:
                open_at = text.rfind("(", 0, match.start() + 1)
                close_before = text.rfind(")", 0, match.start() + 1)
                close_after = text.find(")", match.end())
                if open_at <= close_before or close_after < 0:
                    errors.append(
                        f'{model["slug"]}: original term {match.group(0)!r} is not parenthesized'
                    )
                    continue
                prefix = text[max(0, open_at - 50):open_at]
                # 국가별 법적 의미에 따라 같은 원어도 `환경영향선언(DIA)`,
                # `환경영향평가서(DIA)`처럼 적절한 한국어가 달라질 수 있다.
                # 특정 번역어 하나를 강제하지 않고, 독자가 먼저 읽을 한국어가
                # 실제로 괄호 앞에 있는지를 검사한다.
                if not re.search(r"[가-힣]", prefix):
                    errors.append(
                        f'{model["slug"]}: {match.group(0)!r} is not preceded by Korean'
                    )

    if errors:
        for error in errors:
            print(f"ERROR {error}")
        print(f"FAILED: {len(errors)} Korean-first terminology error(s)")
        return 1
    print(
        f"OK: {len(models)} construction pages use Korean-first terms with "
        "at most one parenthesized original per page"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
