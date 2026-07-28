#!/usr/bin/env python3
"""44개 파트너국 3축 모델의 강화된 조문 검증 완료 여부를 감사한다.

일반 데이터 계약 검증과 달리 이 감사는 작업 진행 중 실패하는 것이 정상이다.
모든 모델이 아래 조건을 충족할 때만 종료코드 0을 반환한다.

* verification.status == "article-verified"
* verification.unresolved가 비어 있음
* 원문별 articlesChecked와 현행성(instrumentStatus) 확인 기록이 있음
* 6개 정량·절차 항목(requirements)을 모두 확인하거나 비적용으로 판정함
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INST_DIR = ROOT / "data" / "institutions"
AXES = {"bidding", "governance", "pipeline"}
REQUIRED_REQUIREMENTS = {
    "thresholds",
    "deadlines",
    "bidSecurity",
    "performanceSecurity",
    "complaints",
    "exceptions",
}
REQUIREMENT_STATUS = {"confirmed", "not-applicable"}
INSTRUMENT_STATUS = {
    "in-force",
    "amended",
    "repealed",
    "superseded",
    "not-applicable",
}


def load_partner_models() -> list[tuple[Path, dict]]:
    models: list[tuple[Path, dict]] = []
    for path in sorted(INST_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        country = data.get("country", {})
        if country.get("iso3") == "KOR" or data.get("slug", "").startswith("koica-"):
            continue
        if data.get("axis") in AXES:
            models.append((path, data))
    return models


def audit(data: dict) -> list[str]:
    problems: list[str] = []
    verification = data.get("verification", {})

    if verification.get("status") != "article-verified":
        problems.append("status")
    if verification.get("unresolved"):
        problems.append("unresolved")

    sources = verification.get("sources", [])
    if not any(source.get("articlesChecked") for source in sources):
        problems.append("articlesChecked")

    article_audit = verification.get("articleAudit")
    if not isinstance(article_audit, dict):
        return problems + ["articleAudit"]

    instruments = article_audit.get("instrumentStatus")
    if not isinstance(instruments, list) or not instruments:
        problems.append("instrumentStatus")
    else:
        for instrument in instruments:
            required = {
                "instrument",
                "status",
                "checkedOn",
                "effectiveDate",
                "evidenceUrl",
                "finding",
            }
            if not required.issubset(instrument):
                problems.append("instrumentStatus-fields")
                break
            if instrument.get("status") not in INSTRUMENT_STATUS:
                problems.append("instrumentStatus-value")
                break

    requirements = article_audit.get("requirements")
    if not isinstance(requirements, dict):
        problems.append("requirements")
    else:
        missing = REQUIRED_REQUIREMENTS - set(requirements)
        if missing:
            problems.append("requirements-missing:" + ",".join(sorted(missing)))
        for key in REQUIRED_REQUIREMENTS & set(requirements):
            item = requirements[key]
            if not isinstance(item, dict):
                problems.append(f"requirements-{key}")
                continue
            required = {"status", "articles", "finding", "evidenceUrl"}
            if not required.issubset(item):
                problems.append(f"requirements-{key}-fields")
            if item.get("status") not in REQUIREMENT_STATUS:
                problems.append(f"requirements-{key}-status")
            if not item.get("articles"):
                problems.append(f"requirements-{key}-articles")
            if not item.get("finding"):
                problems.append(f"requirements-{key}-finding")
            if not str(item.get("evidenceUrl", "")).startswith(("http://", "https://")):
                problems.append(f"requirements-{key}-url")

    return problems


def main() -> int:
    models = load_partner_models()
    failures: list[tuple[str, list[str]]] = []
    axes = Counter()
    countries: set[str] = set()

    for _, data in models:
        countries.add(data["country"]["iso3"])
        problems = audit(data)
        if problems:
            failures.append((data["slug"], problems))
        else:
            axes[data["axis"]] += 1

    expected_models = 44 * 3
    print(
        f"강화 조문검증: {len(models) - len(failures)}/{len(models)} 모델 통과 "
        f"({len(countries)}개국, bidding={axes['bidding']}, "
        f"governance={axes['governance']}, pipeline={axes['pipeline']})"
    )

    if len(countries) != 44 or len(models) != expected_models:
        print(
            f"[ERROR] 대상 집합 오류: 44개국×3축={expected_models}이어야 하나 "
            f"{len(countries)}개국/{len(models)}모델",
            file=sys.stderr,
        )
        return 1

    if failures:
        for slug, problems in failures:
            print(f"[FAIL] {slug}: {', '.join(dict.fromkeys(problems))}")
        return 1

    print("[PASS] 44개국 3축 전부 강화된 article-verified 기준 충족")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
