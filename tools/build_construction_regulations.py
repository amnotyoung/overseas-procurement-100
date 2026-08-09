#!/usr/bin/env python3
"""Build expert-facing country briefs from construction-regulation JSON files.

Usage:
    python3 tools/build_construction_regulations.py
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "construction-regulations"
OUTPUT_DIR = ROOT / "docs" / "construction-regulations"

STAGE_LABELS = {
    "site-and-land": "부지·권원",
    "programming": "프로그램",
    "design": "설계",
    "environment": "환경",
    "permit": "건축허가",
    "pre-construction": "착공 전",
    "construction": "시공",
    "completion": "준공·개장",
    "operation": "운영",
}
STAGE_ORDER = list(STAGE_LABELS)
STATUS_LABELS = {
    "confirmed": "확정",
    "conditional": "조건부",
    "unresolved": "미확정",
    "in_force": "현행 확인",
    "current_official": "운영 중 공식 안내",
    "superseded": "폐지·대체",
    "pending": "심의·예고",
    "continuity_unverified": "최신 개정 확인 중",
}
VERIFY_LABELS = {
    "article-verified": "조문 대조",
    "law-linked": "법령 연결",
    "source-linked": "공식자료 연결",
    "needs-review": "추가 확인",
}


def load_country_files() -> list[dict[str, Any]]:
    files = sorted(path for path in DATA_DIR.glob("*.json") if path.name != "manifest.json")
    return [json.loads(path.read_text(encoding="utf-8")) for path in files]


def esc(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def join_items(items: list[str]) -> str:
    return "<br>".join(esc(item) for item in items) if items else "—"


def instrument_link(instrument: dict[str, Any]) -> str:
    return f"[{instrument['titleKo']}]({instrument['officialUrl']})"


def basis_text(refs: list[dict[str, Any]], instruments: dict[str, dict[str, Any]]) -> str:
    parts: list[str] = []
    for ref in refs:
        instrument = instruments[ref["instrumentId"]]
        provisions = ", ".join(ref.get("provisions", []))
        suffix = f" {provisions}" if provisions else ""
        parts.append(f"{instrument_link(instrument)}{suffix}")
    return "<br>".join(parts) if parts else "—"


def build_country(data: dict[str, Any]) -> str:
    country = data["country"]
    instruments = {item["id"]: item for item in data["instruments"]}
    authorities = {item["id"]: item for item in data["authorities"]}
    counts = Counter(item["status"] for item in data["requirements"])
    blocking = [item for item in data["openQuestions"] if item["blocking"]]
    context = data.get("pilotContext")

    lines: list[str] = []
    add = lines.append
    add(f"# {country['name']} 건축 법·제도 브리프")
    add("")
    add("> 이 문서는 `tools/build_construction_regulations.py`가 "
        f"`data/construction-regulations/{data['slug']}.json`에서 생성한다. 직접 고치지 말 것.")
    add("")
    add(f"- 기준일: **{data['asOfDate']}**")
    add(f"- 검증: **{VERIFY_LABELS[data['verification']['status']]}**")
    add(f"- 생애주기 의무: **{len(data['requirements'])}건** — 확정 {counts['confirmed']} / 조건부 {counts['conditional']} / 미확정 {counts['unresolved']}")
    add(f"- Gate 차단 질문: **{len(blocking)}건**")
    add("")
    add(data["purpose"])
    add("")
    add("> 법률자문이나 관할기관의 유권해석이 아니다. 기준일 이후 개정 여부와 개별 사업 적용은 허가권자·현지 등록전문가에게 다시 확인한다.")
    add("")

    if context:
        add("## 파일럿 사업 적용 범위")
        add("")
        add(f"**{context['projectName']}** · {context['location']} · {context['projectType']}")
        add("")
        add(context["sourceNote"])
        add("")
        add("확인된 입력:")
        add("")
        for item in context["known"]:
            add(f"- {item}")
        add("")
        add("아직 받지 못한 핵심 입력:")
        add("")
        for item in context["unknown"]:
            add(f"- {item}")
        add("")

    if data.get("publicModels"):
        questions = {item["id"]: item for item in data["openQuestions"]}
        add(f"## 공개 건축 제도 {len(data['publicModels'])}종")
        add("")
        add("조달 1~3번 뒤에 다음 제도축을 4번부터 분리한다. 각 축은 같은 국가 원천과 법령 대장을 참조한다.")
        add("")
        add("| 번호 | 제도축 | 판단하려는 것 | 핵심 현장질문 |")
        add("|---:|---|---|---|")
        for model in data["publicModels"]:
            model_questions = [questions[ident]["question"] for ident in model["questionIds"]]
            add(
                f"| {model['priority']:02d} | {esc(model['name'])} | "
                f"{esc(model['purpose'])} | {join_items(model_questions)} |"
            )
        add("")

    add("## 보고서에 바로 쓸 수 있는 판단")
    add("")
    for item in data["reportReadyConclusions"]:
        sources = [instrument_link(instruments[ident]) for ident in item["basis"]]
        add(f"- **{STATUS_LABELS[item['confidence']]}** — {item['text']} ({'; '.join(sources)})")
    add("")

    add("## Gate 1 차단 질문")
    add("")
    add("| 단계 | 질문 | 필요한 증빙 | 확인 상대 | 담당 |")
    add("|---|---|---|---|---|")
    for item in blocking:
        confirm = [authorities[ident]["nameKo"] for ident in item["confirmWith"]]
        add(f"| {STAGE_LABELS[item['stage']]} | {esc(item['question'])} | {join_items(item['evidenceNeeded'])} | {join_items(confirm)} | {esc(item['owner'])} |")
    add("")

    add("## 인허가·검사 경로")
    add("")
    add("| 순서 | Gate | 판단 | 선행 | 산출물 |")
    add("|---:|---|---|---|---|")
    for gate in data["permitPath"]:
        depends = ", ".join(str(value) for value in gate["dependsOn"]) or "—"
        add(f"| {gate['order']} | {esc(gate['gate'])} | {esc(gate['decision'])} | {depends} | {esc(gate['output'])} |")
    add("")
    add("> 법정 처리기간은 완비서류 접수 이후의 규정상 기간이다. 환경평가, 사전협의, 보완, 외부기관 의견, 기술검사와 개장승인 기간을 별도로 잡는다.")
    add("")

    add("## 단계별 법·제도 요구사항")
    add("")
    for stage in STAGE_ORDER:
        items = [item for item in data["requirements"] if item["stage"] == stage]
        if not items:
            continue
        add(f"### {STAGE_LABELS[stage]}")
        add("")
        for item in items:
            add(f"#### {item['topic']} · {STATUS_LABELS[item['status']]}")
            add("")
            add(f"- 적용: {item['applicability']}")
            add(f"- 요구: {item['requirement']}")
            add(f"- 근거: {basis_text(item['legalBasis'], instruments)}")
            add(f"- 관할: {', '.join(authorities[ident]['nameKo'] for ident in item['authorityIds'])}")
            add(f"- 확보할 증빙: {'; '.join(item['evidenceToObtain'])}")
            add(f"- 보고서 반영: {item['reportUse']}")
            add("")

    if data["siteOverlays"]:
        add("## 대상 필지별 적용 확인사항")
        add("")
        add("| 구역 | 상태 | 확인된 규칙 | 빠진 증빙 | 보고서 처리 |")
        add("|---|---|---|---|---|")
        for item in data["siteOverlays"]:
            add(f"| {esc(item['area'])} | {STATUS_LABELS[item['status']]} | {esc(item['rule'])} | {join_items(item['missingEvidence'])} | {esc(item['consequence'])} |")
        add("")

    add("## 전체 미확정 질문")
    add("")
    add("| ID | 차단 | 단계 | 질문 | 왜 중요한가 | 증빙 | 담당 |")
    add("|---|---|---|---|---|---|---|")
    for item in data["openQuestions"]:
        add(f"| `{item['id']}` | {'예' if item['blocking'] else '아니오'} | {STAGE_LABELS[item['stage']]} | {esc(item['question'])} | {esc(item['whyItMatters'])} | {join_items(item['evidenceNeeded'])} | {esc(item['owner'])} |")
    add("")

    add("## 현지조사 체크리스트")
    add("")
    add("| 시점 | 확인 | 산출물 |")
    add("|---|---|---|")
    for item in data["fieldworkChecklist"]:
        add(f"| {esc(item['phase'])} | {esc(item['check'])} | {esc(item['output'])} |")
    add("")

    add("## 법령·공식자료 대장")
    add("")
    add("| 자료 | 상태 | 적용 범위 | 확인 깊이 | 상태 확인 | 확인 조문 | 비고 |")
    add("|---|---|---|---|---|---|---|")
    for item in data["instruments"]:
        checked = ", ".join(item.get("articlesChecked", [])) or "—"
        status_checked = item.get("statusCheckedOn", "—")
        if item.get("statusBasis"):
            status_checked += f" · {item['statusBasis']}"
        add(
            f"| {instrument_link(item)} | {STATUS_LABELS[item['status']]} | "
            f"{esc(item.get('scopeLabel', '국가 기본범위'))} | "
            f"{VERIFY_LABELS[item['verificationLevel']]} | {esc(status_checked)} | "
            f"{esc(checked)} | {esc(item.get('note', '—'))} |"
        )
    add("")

    add("## 검증범위와 한계")
    add("")
    add(f"- 방법: {data['verification']['method']}")
    add(f"- 범위: {data['verification']['scope']}")
    for item in data["verification"].get("limitations", []):
        add(f"- 주의: {item}")
    add("")
    add("데이터 구조와 판정 규칙은 [국가별 건축 법·제도 데이터 계약](../construction-regulations-data-contract.md)을 따른다.")
    add("")
    return "\n".join(lines)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    countries = load_country_files()
    for data in countries:
        output = OUTPUT_DIR / f"{data['slug']}.md"
        output.write_text(build_country(data), encoding="utf-8")
        print(f"built {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
