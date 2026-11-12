"""공개 범위 표와 매니페스트의 검증 수치는 제도 원천 JSON에서 재현한다."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "data" / "manifest.json"
README = ROOT / "README.md"
START = "<!-- procurement-summary:start -->"
END = "<!-- procurement-summary:end -->"


def sync_manifest(manifest, records):
    by_slug = {record["slug"]: record for record in records}
    seen = set()
    for country in manifest["countries"]:
        for axis, item in country["institutions"].items():
            slug = item["slug"]
            record = by_slug.get(slug)
            if record is None or slug in seen or record["axis"] != axis or record["country"]["iso3"] != country["iso3"]:
                raise ValueError(f"매니페스트 국가·제도 연결 오류: {slug}")
            seen.add(slug)
            item["verification"] = record["verification"]["status"]
            item["discrepancies"] = len(record["verification"]["discrepancies"])
    if seen != set(by_slug):
        raise ValueError(f"매니페스트에 없는 제도: {sorted(set(by_slug) - seen)}")


def readme_summary(records):
    partners = {r["country"]["iso3"] for r in records if r["country"]["iso3"] != "KOR"}
    statuses = Counter(r["verification"]["status"] for r in records)
    discrepancies = sum(len(r["verification"]["discrepancies"]) for r in records)
    grades = ", ".join(f"`{key}` {count}개" for key, count in sorted(statuses.items()))
    return (f"{START}\n- 협력국 {len(partners)}개국과 KOICA 발주자 조달 제도 {len(records)}개\n"
            f"- 조달 모델의 검증 상태는 {grades}\n- 조달 현행 기준 확인사항 {discrepancies}건\n{END}")


def updated_readme(text, records):
    before, start, rest = text.partition(START)
    _, end, after = rest.partition(END)
    if not (start and end):
        raise ValueError("README에 조달 집계 구간이 없습니다")
    return before + readme_summary(records) + after


def summary_errors(records):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    original = json.dumps(manifest)
    try:
        sync_manifest(manifest, records)
        readme = README.read_text(encoding="utf-8")
        current = updated_readme(readme, records)
    except ValueError as exc:
        return [str(exc)]
    errors = []
    if json.dumps(manifest) != original:
        errors.append("data/manifest.json의 검증 상태·확인사항 집계 불일치")
    if readme != current:
        errors.append("README의 조달 집계 불일치")
    return errors


def write_summaries(records):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    sync_manifest(manifest, records)
    readme = updated_readme(README.read_text(encoding="utf-8"), records)
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    README.write_text(readme, encoding="utf-8")
