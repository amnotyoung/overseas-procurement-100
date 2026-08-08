#!/usr/bin/env python3
"""Fail when a construction axis claims a higher evidence grade than it has earned.

건축의 근거 등급은 네 층에 흩어져 있다 — 국가 `verification.status`, 축
`publicModels[].procedureStatus`, 문서 `instruments[].verificationLevel`,
노드 `basisScope`/`kind`. 지금까지 이 넷을 잇는 검증이 없어서, 상단에
"조문 대조 절차" 배지가 뜨는 페이지의 노드 상세에 "축 전체 관련 제도 근거"가
뜨고 근거 문서는 "공식자료 연결" 배지를 다는 일이 가능했다.

이 검사는 축마다 **달성 등급을 계산**하고 주장 등급이 그보다 높으면 실패한다.
근거를 검증하는 사이트에서 배지가 거짓말하면 다른 모든 것이 무의미하다.

## 등급 사다리 (공표 단위 = 축)

    detail-unverified / source-linked   작성 중. 배포 대상이 아니다(계약 §5.6)
    official-source-linked              공식 절차를 확인. basisScope: axis 허용
    article-linked                      노드마다 조문을 연결. 축 기둥 법령을 조문 확인
    article-verified                    축의 법령 근거를 전수 조문 확인

`official-guidance` 종류의 자료는 조문 자체가 없으므로(129건 전부
`source-linked`다) 조문 확인 요건에서 제외한다. 안내 페이지에 조문 대조를
요구하면 어느 축도 승격할 수 없다.

## 래칫

등급 분포 하한을 `catalog/evidence-grade-baseline.json`에 고정한다. 하한보다
낮으면 승격이 되돌아간 것이고, 높으면 픽스처를 갱신하라고 실패한다 — 승격
사실이 반드시 리뷰에 노출되게 하려는 것이다. 전 국가가 승격되기 전에도 CI는
초록이면서 회귀와 승격 양쪽을 잡는다. `--update`로 픽스처를 갱신한다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "construction-regulations"
BASELINE_PATH = DATA_DIR / "catalog" / "evidence-grade-baseline.json"

# 조문이 존재하는 자료. official-guidance 같은 안내 자료는 여기 들어가지 않는다.
STATUTORY_KINDS = {
    "act", "regulation", "decree", "code", "order",
    "ordinance", "local-regulation", "standard", "plan", "draft",
}
GRADE_ORDER = {
    "detail-unverified": 0,
    "source-linked": 1,
    "official-source-linked": 2,
    "article-linked": 3,
    "article-verified": 4,
}
PUBLISHED_GRADES = ("article-verified", "article-linked", "official-source-linked")


def axis_evidence(data: dict, model: dict) -> dict:
    """Collect the facts an axis grade is decided on."""
    nodes = {n["id"]: n for n in data["processBoard"]["nodes"]}
    instruments = {i["id"]: i for i in data["instruments"]}
    axis_nodes = [nodes[i] for i in model.get("nodeIds", []) if i in nodes]

    referenced = {
        ref["instrumentId"]
        for node in axis_nodes
        for ref in node.get("refs", [])
        if isinstance(ref, dict) and ref.get("instrumentId")
    }
    laws = [
        instruments[i]
        for i in referenced
        if i in instruments and instruments[i].get("kind") in STATUTORY_KINDS
    ]
    gates = [n for n in axis_nodes if n.get("gateOrders")]
    gates_on_law = sum(
        1
        for n in gates
        if any(
            instruments.get(r.get("instrumentId"), {}).get("status") == "in_force"
            for r in n.get("refs", [])
            if isinstance(r, dict)
        )
    )
    return {
        "nodes": len(axis_nodes),
        "axisScoped": sum(1 for n in axis_nodes if n.get("basisScope", "node") == "axis"),
        "statutoryNodes": sum(1 for n in axis_nodes if n.get("kind") == "statutory"),
        "laws": len(laws),
        "lawsArticleVerified": sum(
            1 for x in laws if x.get("verificationLevel") == "article-verified"
        ),
        "lawsSourceLinked": sum(
            1 for x in laws if x.get("verificationLevel") == "source-linked"
        ),
        "lawsWithArticles": sum(1 for x in laws if x.get("articlesChecked")),
        "gates": len(gates),
        "gatesOnInForceLaw": gates_on_law,
    }


def earned_grade(facts: dict) -> str:
    """The highest grade this axis actually satisfies."""
    # article-linked — 노드마다 조문을 연결했고 축 기둥 법령 하나는 조문을 확인했다.
    linked = (
        facts["axisScoped"] == 0
        and facts["laws"] >= 1
        and facts["lawsArticleVerified"] >= 1
        and facts["lawsSourceLinked"] == 0
        and facts["gates"] >= 1
        and facts["gatesOnInForceLaw"] == facts["gates"]
    )
    if not linked:
        return "official-source-linked"
    # article-verified — 축의 법령 근거를 전수 조문 확인했고, 조문과 직접 대응하는
    # 절차 노드가 실제로 있다.
    verified = (
        facts["lawsArticleVerified"] == facts["laws"]
        and facts["lawsWithArticles"] == facts["laws"]
        and facts["statutoryNodes"] >= 1
    )
    return "article-verified" if verified else "article-linked"


def collect(data_dir: Path = DATA_DIR) -> list[dict]:
    results = []
    for path in sorted(data_dir.glob("*.json")):
        if path.name == "manifest.json":
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for model in data.get("publicModels", []):
            facts = axis_evidence(data, model)
            results.append(
                {
                    "slug": model["slug"],
                    "claimed": model.get("procedureStatus", "detail-unverified"),
                    "earned": earned_grade(facts),
                    "facts": facts,
                }
            )
    return results


def shortfall(row: dict) -> str:
    """Say why the claim is not earned, in the terms the fix would take."""
    f = row["facts"]
    reasons = []
    if f["axisScoped"]:
        reasons.append(
            f"노드 {f['axisScoped']}/{f['nodes']}개가 축 공통근거(basisScope: axis)"
        )
    if f["lawsSourceLinked"]:
        reasons.append(f"법령 {f['lawsSourceLinked']}건이 조문 미연결(source-linked)")
    if not f["laws"]:
        reasons.append("참조하는 법령 자료가 없음")
    elif not f["lawsArticleVerified"]:
        reasons.append("조문 확인된 법령이 없음")
    elif f["lawsArticleVerified"] < f["laws"]:
        reasons.append(
            f"법령 {f['laws'] - f['lawsArticleVerified']}/{f['laws']}건이 조문 미확인"
        )
    if f["lawsWithArticles"] < f["laws"]:
        reasons.append(
            f"법령 {f['laws'] - f['lawsWithArticles']}건에 articlesChecked 없음"
        )
    if f["gates"] and f["gatesOnInForceLaw"] < f["gates"]:
        reasons.append(
            f"공식 Gate {f['gates'] - f['gatesOnInForceLaw']}/{f['gates']}개가 현행 법령 근거 없음"
        )
    if not f["gates"]:
        reasons.append("공식 결정 Gate 없음")
    if not f["statutoryNodes"]:
        reasons.append("조문과 직접 대응하는 노드(kind: statutory)가 없음")
    return "; ".join(reasons) or "요건 미상"


def distribution(rows: list[dict]) -> dict[str, int]:
    return {g: sum(1 for r in rows if r["earned"] == g) for g in PUBLISHED_GRADES}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--update", action="store_true", help="현재 등급 분포로 래칫 픽스처를 갱신한다"
    )
    args = parser.parse_args()

    rows = collect()
    overclaims = [
        r for r in rows if GRADE_ORDER.get(r["claimed"], 0) > GRADE_ORDER[r["earned"]]
    ]
    dist = distribution(rows)

    if args.update:
        BASELINE_PATH.write_text(
            json.dumps(
                {
                    "note": (
                        "축 근거 등급의 하한선이다. 아래로 내려가면 승격이 되돌아간 "
                        "것이고, 위로 올라가면 이 파일을 함께 갱신해 승격 사실을 "
                        "리뷰에 노출시킨다. tools/check_construction_evidence_grade.py --update"
                    ),
                    "floor": dist,
                    "models": {r["slug"]: r["earned"] for r in sorted(rows, key=lambda x: x["slug"])},
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"UPDATED: {BASELINE_PATH.relative_to(ROOT)} — {dist}")
        return 0

    errors: list[str] = []
    for row in overclaims:
        errors.append(
            f"{row['slug']}: claims {row['claimed']!r} but earns {row['earned']!r} — {shortfall(row)}"
        )

    if BASELINE_PATH.exists():
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        floor = baseline.get("floor", {})
        for grade in PUBLISHED_GRADES[:2]:  # 상위 두 등급만 되돌아가는지 본다
            if dist.get(grade, 0) < floor.get(grade, 0):
                errors.append(
                    f"{grade}: {dist.get(grade, 0)} model(s), below the recorded floor "
                    f"of {floor.get(grade, 0)} — 승격이 되돌아갔다"
                )
            elif dist.get(grade, 0) > floor.get(grade, 0):
                errors.append(
                    f"{grade}: {dist.get(grade, 0)} model(s), above the recorded floor "
                    f"of {floor.get(grade, 0)} — 승격했다면 "
                    "`python3 tools/check_construction_evidence_grade.py --update`로 "
                    "픽스처를 갱신하고 그 diff를 리뷰에 포함한다"
                )
    else:
        errors.append(
            f"{BASELINE_PATH.relative_to(ROOT)} is missing — --update로 먼저 생성한다"
        )

    if errors:
        print("FAILED: construction evidence grades do not hold")
        for error in errors:
            print(f"- {error}")
        return 1
    print(
        f"OK: {len(rows)} public models hold their evidence grade "
        f"(article-verified {dist['article-verified']}, "
        f"article-linked {dist['article-linked']}, "
        f"official-source-linked {dist['official-source-linked']})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
