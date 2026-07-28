#!/usr/bin/env python3
"""검증 완료 모델의 절차 노드를 실제 확인 근거와 동기화한다.

초기 일괄 생성값 confidence=0.65를 검증 완료 뒤에도 방치하지 않도록,
요건별 조문 또는 축별 공식 원문을 각 노드에 연결하고 근거 수준을 기록한다.
이미 수작업으로 조문이 연결된 노드는 그 조문과 점수를 보존한다.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INST_DIR = ROOT / "data" / "institutions"

KEYWORDS = {
    "complaints": ("이의", "불복", "분쟁", "상소", "재심", "complaint", "appeal", "review"),
    "performanceSecurity": (
        "계약 체결",
        "계약체결",
        "계약관리",
        "계약 관리",
        "이행보증",
        "이행 보증",
        "검수",
        "인수",
        "performance",
    ),
    "bidSecurity": (
        "입찰보증",
        "제안보증",
        "보증 확보",
        "자격·제안",
        "자격·가격",
        "bid security",
        "proposal security",
    ),
    "deadlines": (
        "공고",
        "게시",
        "제출",
        "전자조달",
        "전자제출",
        "서류 발행",
        "서류 수령",
        "마감",
        "notice",
        "submit",
    ),
    "exceptions": (
        "직접",
        "수의",
        "제한",
        "비경쟁",
        "예외",
        "재원 구분",
        "공여",
        "donor",
        "exception",
    ),
    "thresholds": (
        "금액",
        "한도",
        "가격상한",
        "방식",
        "조달계획",
        "조달 계획",
        "method",
        "threshold",
    ),
}

DEFAULT_REQUIREMENTS = {
    "bidding": {
        "P01": ("thresholds", "exceptions"),
        "P02": ("deadlines",),
        "P03": ("bidSecurity",),
        "P04": ("deadlines", "bidSecurity"),
        "P07": ("performanceSecurity",),
    },
    "governance": {
        "P01": ("thresholds",),
        "P02": ("thresholds", "exceptions"),
        "P03": ("deadlines",),
        "P04": ("deadlines", "bidSecurity"),
        "P06": ("complaints",),
        "P07": ("performanceSecurity",),
    },
}

PIPELINE_TERMS = (
    "oda",
    "loan",
    "aid",
    "grant",
    "development",
    "cooperation",
    "investment",
    "assistance",
    "project",
    "원조",
    "차관",
    "협력",
    "투자",
    "사업",
)


def source_for_url(sources: list[dict], url: str) -> dict | None:
    return next((source for source in sources if source.get("officialUrl") == url), None)


def source_for_existing_basis(sources: list[dict], law: str) -> dict | None:
    lowered = law.lower()
    markers = (
        ("sop", "sop"),
        ("1866", "1866"),
        ("986", "986"),
        ("공공조달법", "public procurement"),
        ("procurement law", "public procurement"),
        ("입찰법", "bidding law"),
    )
    for needle, source_needle in markers:
        if needle in lowered:
            match = next(
                (
                    source
                    for source in sources
                    if source_needle in source.get("law", "").lower()
                    and source.get("officialUrl")
                ),
                None,
            )
            if match:
                return match
    return next(
        (
            source
            for source in sources
            if (
                source.get("law", "").lower() in lowered
                or lowered in source.get("law", "").lower()
            )
            and source.get("officialUrl")
        ),
        None,
    )


def requirement_keys(data: dict, node: dict) -> list[str]:
    text = " ".join(
        str(node.get(key, "")).lower()
        for key in ("name", "action", "blocker", "deadline")
    )
    matches = [
        key
        for key, words in KEYWORDS.items()
        if any(word.lower() in text for word in words)
    ]
    if matches:
        return matches[:2]
    return list(DEFAULT_REQUIREMENTS.get(data["axis"], {}).get(node.get("id"), ()))


def requirement_bases(data: dict, node: dict) -> list[dict]:
    verification = data["verification"]
    requirements = verification["articleAudit"]["requirements"]
    sources = verification.get("sources", [])
    bases: list[dict] = []
    for key in requirement_keys(data, node):
        requirement = requirements.get(key)
        if not requirement:
            continue
        url = requirement.get("evidenceUrl", "")
        source = source_for_url(sources, url)
        law = source.get("law") if source else f"{data['country']['nameEn']} verified procurement instrument"
        basis = {
            "law": law,
            "article": requirement["articles"],
            "url": url,
        }
        if basis not in bases:
            bases.append(basis)
    return bases


def fallback_source(data: dict) -> dict:
    sources = [
        source
        for source in data["verification"].get("sources", [])
        if source.get("articlesChecked") and source.get("officialUrl")
    ]
    non_donor = [source for source in sources if source.get("kind") != "donor-rule"]
    if data["axis"] == "pipeline":
        relevant = [
            source
            for source in non_donor
            if any(
                term in f"{source.get('law', '')} {source.get('articlesChecked', '')}".lower()
                for term in PIPELINE_TERMS
            )
        ]
        if relevant:
            return relevant[0]
    if non_donor:
        return non_donor[0]
    if sources:
        return sources[0]
    raise ValueError(f"{data['slug']}: articlesChecked가 있는 출처가 없음")


def fallback_basis(data: dict) -> tuple[list[dict], float, str]:
    source = fallback_source(data)
    donor = source.get("kind") == "donor-rule"
    return (
        [
            {
                "law": source["law"],
                "article": source["articlesChecked"],
                "url": source["officialUrl"],
            }
        ],
        0.8 if donor else 0.85,
        (
            "공식 공여기관 자료를 현행 법령과 교차확인한 절차"
            if donor
            else "현행 공식 원문의 적용범위·절차 조문과 연결"
        ),
    )


def sync(data: dict) -> bool:
    if data.get("verification", {}).get("status") != "article-verified":
        return False
    changed = False
    for node in data.get("process", {}).get("nodes", []):
        if node.get("confidence_reason") in {
            "강화 검증에서 확인한 해당 요건의 공식 조문과 직접 연결",
            "현행 공식 원문의 적용범위·절차 조문과 연결",
            "공식 공여기관 자료를 현행 법령과 교차확인한 절차",
        }:
            node.pop("legal_basis", None)
            node.pop("confidence_reason", None)
            changed = True
        existing = node.get("legal_basis")
        if existing:
            for basis in existing:
                if not basis.get("url"):
                    matching = source_for_existing_basis(
                        data["verification"].get("sources", []),
                        basis.get("law", ""),
                    )
                    if matching and matching.get("officialUrl"):
                        basis["url"] = matching["officialUrl"]
                        changed = True
                    elif "koica" in basis.get("law", "").lower():
                        basis["url"] = "https://www.koica.go.kr/"
                        node["confidence"] = 0.65
                        node["confidence_reason"] = "공개된 KOICA 내부 심사지침 원문 URL을 확보하지 못해 절차 존재만 보수적으로 평가"
                        changed = True
            if not node.get("confidence_reason"):
                node["confidence_reason"] = "노드별 원문 조문 또는 공식 근거에 직접 연결된 기존 검증값"
                changed = True
            if isinstance(node.get("confidence"), (int, float)) and node["confidence"] < 0.8:
                caveat = node.get("blocker") or "세부 적용·운영 범위에 남은 불확실성"
                reason = f"공식 조문은 연결했으나 {caveat}을 반영한 보수적 점수"
                if node.get("confidence_reason") != reason:
                    node["confidence_reason"] = reason
                    changed = True
            continue

        bases = requirement_bases(data, node)
        if bases:
            node["legal_basis"] = bases
            node["confidence"] = 0.9
            node["confidence_reason"] = "강화 검증에서 확인한 해당 요건의 공식 조문과 직접 연결"
        else:
            bases, confidence, reason = fallback_basis(data)
            node["legal_basis"] = bases
            node["confidence"] = confidence
            node["confidence_reason"] = reason
        changed = True
    return changed


def main() -> None:
    changed = 0
    for path in sorted(INST_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if sync(data):
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            changed += 1
    print(f"노드 근거 동기화 완료 — {changed}개 article-verified 모델")


if __name__ == "__main__":
    main()
