#!/usr/bin/env python3
"""Build evidence-linked three-axis construction country workflow records.

The Senegal pilot remains a hand-maintained, article-verified detailed record.  Other
countries can start as source-linked baselines without copying the same workflow
boilerplate dozens of times.  The catalog contains country-specific authorities,
official instruments and decision evidence.  This builder expands that evidence into
a seven-node due-diligence workflow per axis.  The generated workflow deliberately
distinguishes official-route checks from field verification and project-control tasks:
catalog evidence is never presented as an invented statutory sequence.

Usage:
    python3 tools/build_construction_baselines.py
    python3 tools/build_construction_baselines.py --check
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "construction-regulations"
CATALOG_PATH = DATA_DIR / "catalog" / "baselines.json"
MANIFEST_PATH = DATA_DIR / "manifest.json"
GENERATED_FROM = "data/construction-regulations/catalog/baselines.json"

SYSTEM_ORDER = ("site-urban", "permit-environment", "control-completion")
SYSTEM_META = {
    "site-urban": {
        "priority": 4,
        "slugPart": "site-urban",
        "name": "도시계획·부지규제",
        "purpose": (
            "대상 필지의 권원과 토지이용 적합성, 용도지역·건폐율·용적률·높이·이격·주차, "
            "재해·지반과 기반시설 인입조건을 개념설계 전에 확인하는 제도축"
        ),
        "stage": "site-and-land",
        "topic": "필지 권원·도시계획·부지조건",
        "reportUse": "부지 적법성 Gate와 규모·배치 상한, 수원국 토지·기반시설 분담조건에 연결한다.",
        "genericQuestion": (
            "대상 필지의 용도지역, 허용용도, 건폐율·용적률·높이·이격·주차와 재해·기반시설 조건은 무엇인가?"
        ),
        "genericWhy": "공간프로그램, 배치, 층수, 공사비와 부지 적합성을 결정한다.",
        "genericEvidence": [
            "필지 권원·지적도·경계측량",
            "현행 토지이용계획·용도지역 확인서",
            "필지별 개발기준표와 기반시설 인입확약",
        ],
        "checklist": [
            ("출국 전", "권원·지적도·계획도·측량·지반·침수·기반시설 자료를 문서번호와 함께 요청한다.", "부지 자료 인벤토리와 결측대장"),
            ("기관협의", "관할 계획기관에 필지별 수치와 특구·재해·문화재 등 중첩규제를 서면 확인한다.", "필지 규제표와 기관 확인공문"),
        ],
    },
    "permit-environment": {
        "priority": 5,
        "slugPart": "permit-environment",
        "name": "건축허가·환경심사",
        "purpose": (
            "건축주·허가권자와 현지 책임설계자, 시설·위험 분류, 환경 스크리닝과 건축허가의 "
            "선후관계·서류·수수료·기간을 확인하는 제도축"
        ),
        "stage": "permit",
        "topic": "사업분류·건축허가·환경심사",
        "reportUse": "인허가 매트릭스, 현지 설계용역 범위, 일정·수수료와 수원기관 역할에 연결한다.",
        "genericQuestion": (
            "본 사업의 건축주·신청인·허가권자, 시설분류와 환경평가 유형, 필수 선행동의는 무엇인가?"
        ),
        "genericWhy": "설계 서명권, 제출도서, 관계기관 협의, 인허가 일정과 비용을 결정한다.",
        "genericEvidence": [
            "관할기관 사전분류 회신",
            "현지 책임건축사·기술자 자격증빙",
            "환경 스크리닝 결정과 최신 허가 체크리스트·수수료표",
        ],
        "checklist": [
            ("출국 전", "사업주체·연면적·층수·용도·재실인원·공공사업 여부를 정리해 사전분류 질문서를 보낸다.", "사업분류표와 기관 질의서"),
            ("기관협의", "건축·환경기관과 최신 접수창구, 선행동의, 수수료, 보완정지와 실제 처리기간을 확인한다.", "인허가 일정·비용 매트릭스"),
        ],
    },
    "control-completion": {
        "priority": 6,
        "slugPart": "control-completion",
        "name": "기술검사·보험·준공제도",
        "purpose": (
            "설계·시공 자격, 기술검사와 공사보험, 착공·중간검사·변경관리, 준공·소방·사용승인과 "
            "운영 인계조건을 확인하는 제도축"
        ),
        "stage": "completion",
        "topic": "기술기준·검사·보험·준공·사용승인",
        "reportUse": "감리·검사·보험·시공계약 패키지와 준공·개장 선행조건에 연결한다.",
        "genericQuestion": (
            "현지 설계자·시공자·검사기관의 자격, 의무보험, 중간검사와 준공·소방·사용승인 절차는 무엇인가?"
        ),
        "genericWhy": "조달 패키지, 품질책임, 보험료, 검사 Hold Point와 개장 가능일을 결정한다.",
        "genericEvidence": [
            "전문가·시공자·검사기관 등록증과 보험증권",
            "검사계획·시험성적서·변경승인 기록",
            "준공·소방·사용승인 체크리스트와 실제 견적",
        ],
        "checklist": [
            ("시장조사", "현지 등록 설계자·시공자·검사기관·보험사의 자격과 유효기간을 감독기관에서 대조한다.", "적격기관·보험 대장"),
            ("기관협의", "착공통지, 중간검사, 준공도서, 소방·사용승인과 개장 조건을 순서대로 확인한다.", "검사·준공·개장 Hold Point 표"),
        ],
    },
}

BOARD_LANES = [
    "사업주·수원기관",
    "현지 설계·조사팀",
    "도시계획·건축 당국",
    "환경·안전·검사기관",
]

# Each public construction model mirrors the procurement boards' information density:
# seven nodes, at least three active lanes and four lifecycle stages.  ``kind`` is the
# epistemic contract.  Generated catalog evidence is axis-level rather than a verified
# node-to-article crosswalk, so these generic nodes never claim ``statutory`` status.
# ``official-guidance`` marks a task that checks an official route; field-verification
# and project-control nodes are ODA-team tasks, not additional local-law steps.
WORKFLOW_META = {
    "site-urban": {
        "stages": [
            "G0 필지·권원",
            "G1 계획·개발규제",
            "G2 현장·기반시설",
            "G3 부지조건 확정",
        ],
        "steps": [
            {
                "lane": "사업주·수원기관", "stage": 0,
                "label": "대상 필지·사업입력 확정", "emphasis": "lead",
                "kind": "project-control",
                "action": "필지 식별정보, 사업용도, 규모와 사업주체를 한 개 기준선으로 고정한다.",
                "output": "사업개요·필지 식별표", "questionSlots": [],
            },
            {
                "lane": "현지 설계·조사팀", "stage": 0,
                "label": "권원·토지사용권 검증", "emphasis": "key",
                "kind": "field-verification",
                "action": "등기·지적·사용권과 소유자 또는 권리자의 사업 동의를 원본으로 대조한다.",
                "output": "권원·경계·사용동의 검증표", "questionSlots": [2],
            },
            {
                "lane": "도시계획·건축 당국", "stage": 1,
                "label": "{referenceLabel} 공식 적용확인", "emphasis": "normal",
                "kind": "official-guidance",
                "action": "필지·사업자료를 기준으로 관할기관 또는 공식 서비스에서 적용 계획·개발규제와 승인·비대상 결정경로를 확인한다.",
                "output": "계획·개발 적용회신·승인·비대상 결정과 경로표", "questionSlots": [1],
                "permitGate": {
                    "key": "planning-decision",
                    "gate": "계획·개발규제 공식 적용확인",
                    "decision": (
                        "관할 계획·개발기관이 대상 필지에 적용되는 계획·개발규제와 "
                        "사전승인 필요 여부를 공식 확인한다."
                    ),
                    "output": "계획·개발 적합확인·승인서 또는 비대상 회신",
                    "dependsOn": [],
                },
            },
            {
                "lane": "현지 설계·조사팀", "stage": 1,
                "label": "용도·개발수치·중첩규제 확인", "emphasis": "bottleneck",
                "kind": "field-verification",
                "action": "필지에 실제 적용되는 허용용도와 개발수치, 도로·주차·특구 등 중첩조건을 서면 확인한다.",
                "output": "필지별 개발규제표", "questionSlots": [1],
            },
            {
                "lane": "현지 설계·조사팀", "stage": 2,
                "label": "지반·재해·유틸리티 조사", "emphasis": "normal",
                "kind": "field-verification",
                "action": "지반, 침수·재해, 접근·배수와 전력·통신·상하수 용량을 현장자료로 검증한다.",
                "output": "현장조건·인입용량 조사서", "questionSlots": [2],
            },
            {
                "lane": "도시계획·건축 당국", "stage": 2,
                "label": "관할기관 조건·결측 서면확정", "emphasis": "normal",
                "kind": "field-verification",
                "action": "공개자료로 확정되지 않는 필지조건과 추가 제출자료를 관할기관 회신으로 잠근다.",
                "output": "기관 회신·조건부사항 대장", "questionSlots": [0],
            },
            {
                "lane": "사업주·수원기관", "stage": 3,
                "label": "부지 적합성 Gate·설계조건 잠금", "emphasis": "bottleneck",
                "kind": "project-control",
                "action": "권원·규제·현장조건의 결측과 위험을 검토해 설계 진행, 조건부 진행 또는 부지 재검토를 결정한다.",
                "output": "부지 Go/Conditional/No-Go 결정서", "questionSlots": [0],
            },
        ],
        "loop": (6, 2, "필지자료·기관확인 보완"),
    },
    "permit-environment": {
        "stages": [
            "G4 신청인·사업분류",
            "G5 환경·전문심사",
            "G6 허가도서·관계협의",
            "G7 접수·허가결정",
        ],
        "steps": [
            {
                "lane": "사업주·수원기관", "stage": 0,
                "label": "건축주·신청인·관할 확정", "emphasis": "lead",
                "kind": "project-control",
                "action": "법적 건축주·토지소유자·신청인과 국가·지방·특구 관할을 확정한다.",
                "output": "신청주체·권한·관할 매트릭스", "questionSlots": [0],
            },
            {
                "lane": "현지 설계·조사팀", "stage": 0,
                "label": "책임설계자·시설·위험분류", "emphasis": "key",
                "kind": "field-verification",
                "action": "현지 서명권자와 시설 용도·점유·규모·위험 분류 및 제출도서 책임을 확인한다.",
                "output": "책임설계·시설분류표", "questionSlots": [1],
            },
            {
                "lane": "환경·안전·검사기관", "stage": 1,
                "label": "환경 스크리닝·평가경로 결정", "emphasis": "bottleneck",
                "kind": "field-verification",
                "action": "환경기관의 공식 분류로 평가유형, 선행조건, 심사기관과 승인 산출물을 결정한다.",
                "output": "환경 스크리닝·평가경로 결정", "questionSlots": [0],
                "dependsOnStepIndexes": [1],
                "permitGate": {
                    "key": "environment-decision",
                    "gate": "환경 스크리닝·평가 공식결정",
                    "decision": (
                        "관할 환경기관이 사업의 평가·허가 유형과 선행조건을 공식 분류하거나 "
                        "비대상 여부를 확인한다."
                    ),
                    "output": "환경 분류·승인·면제 또는 비대상 결정문",
                    "dependsOn": [],
                },
            },
            {
                "lane": "도시계획·건축 당국", "stage": 1,
                "label": "건축·개발허가 공식경로 확인", "emphasis": "normal",
                "kind": "official-guidance",
                "action": "공식 허가 안내와 법령을 대조해 건축·개발허가의 적용경로와 선행관계를 확인한다.",
                "output": "건축·개발허가 경로표", "questionSlots": [1],
                "dependsOnStepIndexes": [1],
            },
            {
                "lane": "현지 설계·조사팀", "stage": 2,
                "label": "허가도서·설계기준 통합", "emphasis": "normal",
                "kind": "project-control",
                "action": "분류결정, 현지 서명요건과 최신 체크리스트를 설계·제출도서 목록에 통합한다.",
                "output": "허가도서·서명·설계기준 대장", "questionSlots": [2],
                "dependsOnStepIndexes": [2, 3],
            },
            {
                "lane": "환경·안전·검사기관", "stage": 2,
                "label": "소방·안전·유틸리티 병렬협의", "emphasis": "normal",
                "kind": "field-verification",
                "action": "소방·안전·도로·물·전력 등 적용 기관과 동의서·NOC의 필요 여부 및 병렬처리 가능성을 확인한다.",
                "output": "관계기관 협의·선행동의 매트릭스", "questionSlots": [2],
            },
            {
                "lane": "도시계획·건축 당국", "stage": 3,
                "label": "완비접수·수수료·허가결정 Gate", "emphasis": "bottleneck",
                "kind": "field-verification",
                "action": "완비 기준, 접수일, 수수료, 보완정지, 실제 처리기간과 건축·개발허가 조건 및 해당 시 별도 환경결정 조건을 기록한다.",
                "output": "완비접수증·결정문·조건·일정대장", "questionSlots": [0],
                "permitGate": {
                    "key": "building-permit-decision",
                    "gate": "관할 건축·개발기관의 허가결정",
                    "decision": (
                        "관할 건축·개발기관이 완비도서와 관계기관 의견을 심사해 허가, "
                        "조건부 허가, 보완 또는 불허를 공식 결정한다."
                    ),
                    "output": "건축·개발 허가결정문과 승인도서·조건",
                    "dependsOn": [],
                },
            },
        ],
        "edges": [
            (0, 1, "sequence", "책임체계"),
            (1, 2, "message", "환경분류"),
            (1, 3, "sequence", "허가경로"),
            (2, 4, "message", "환경조건"),
            (3, 4, "sequence", "허가요건"),
            (4, 5, "sequence", "관계협의"),
            (5, 6, "sequence", "완비접수"),
        ],
        "loop": (6, 4, "도서·기관의견 보완"),
    },
    "control-completion": {
        "stages": [
            "G8 자격·착공준비",
            "G9 시공·품질관리",
            "G10 검사·준공보완",
            "G11 사용승인·인계",
        ],
        "steps": [
            {
                "lane": "사업주·수원기관", "stage": 0,
                "label": "자격·계약·보험 적용판정", "emphasis": "lead",
                "kind": "field-verification",
                "action": "현지 설계·시공·검사 주체의 등록자격과 계약상 책임, 의무보험 적용 여부와 견적을 확인한다.",
                "output": "자격·계약·보험 적용표", "questionSlots": [0],
            },
            {
                "lane": "현지 설계·조사팀", "stage": 0,
                "label": "기술기준·검사계획 확정", "emphasis": "key",
                "kind": "official-guidance",
                "action": "적용 코드·표준, 착공 전 통지 여부, 법정·계약 검사 Hold Point와 책임자를 확정한다.",
                "output": "적용기준·검사시험계획(ITP)", "questionSlots": [1],
            },
            {
                "lane": "도시계획·건축 당국", "stage": 1,
                "label": "{referenceLabel} 적용경로 확인", "emphasis": "normal",
                "kind": "official-guidance",
                "action": "공식 법령·서비스에서 착공, 단계검사, 준공·점유의 적용경로와 관할을 확인한다.",
                "output": "검사·준공·점유 법정경로표", "questionSlots": [1],
            },
            {
                "lane": "현지 설계·조사팀", "stage": 1,
                "label": "시공·시험·품질기록 이행", "emphasis": "normal",
                "kind": "project-control",
                "action": "승인도서와 검사계획에 따라 자재·시험·사진·감리·시공 기록을 누적 관리한다.",
                "output": "품질·시험·시공기록 대장", "questionSlots": [2],
            },
            {
                "lane": "환경·안전·검사기관", "stage": 2,
                "label": "단계검사·변경·재검사 관리", "emphasis": "bottleneck",
                "kind": "field-verification",
                "action": "법정 또는 계약 검사, 변경승인, 부적합 시정과 재검사 완료를 증빙으로 닫는다.",
                "output": "검사·변경·부적합 종결기록", "questionSlots": [2],
            },
            {
                "lane": "환경·안전·검사기관", "stage": 2,
                "label": "최종·소방검사·준공·점유결정", "emphasis": "normal",
                "kind": "field-verification",
                "action": "관할기관과 최종·소방검사를 닫고 as-built·시험성적·인증서를 제출해 준공·점유·사용승인 또는 비대상 회신을 확보한다.",
                "output": "최종·소방검사 결과와 준공·점유·사용승인서·비대상 회신", "questionSlots": [0],
                "permitGate": {
                    "key": "completion-use-decision",
                    "gate": "관할기관의 준공·점유·사용결정",
                    "decision": (
                        "관할 검사·건축·소방기관이 적용되는 최종검사와 준공·점유·사용승인을 "
                        "완료하거나 비대상 여부를 공식 확인한다."
                    ),
                    "output": "최종검사 결과·준공·점유·사용승인서 또는 비대상 회신",
                    "dependsOn": [],
                },
            },
            {
                "lane": "사업주·수원기관", "stage": 3,
                "label": "준공·점유·O&M 인계 Gate", "emphasis": "bottleneck",
                "kind": "project-control",
                "action": "준공·점유·개장에 필요한 증명과 잔여조건을 확인하고 O&M·보증·자산 인계를 승인한다.",
                "output": "점유·개장 승인 및 O&M 인계팩", "questionSlots": [0],
            },
        ],
        "loop": (6, 3, "품질기록·검사 보완"),
    },
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def pretty(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def basis_sources(system: dict[str, Any]) -> list[str]:
    return [item["instrumentId"] for item in system["basis"]]


def render_step_text(value: str, system: dict[str, Any]) -> str:
    return value.format(referenceLabel=system["referenceLabel"])


def step_outputs(
    step: dict[str, Any],
    system: dict[str, Any],
    override: dict[str, Any] | None = None,
) -> list[str]:
    """Return only the workflow template's node-specific deliverable.

    Catalog ``evidence`` arrays belong to the whole regulatory axis and are not a
    normalized positional schema.  They stay attached to requirements/questions;
    treating their indexes as node mappings would create false step-level outputs.
    """
    return [render_step_text((override or {}).get("output", step["output"]), system)]


def system_basis_refs(system: dict[str, Any]) -> list[dict[str, Any]]:
    """Return axis-level sources without inventing a node-to-article mapping.

    The baseline catalog links sources to a system, not to individual workflow tasks.
    Generated nodes therefore expose the complete system basis with ``basisScope=axis``.
    Hand-maintained article-verified records can still attach exact node refs directly.
    """
    return [
        {
            "source": system["referenceLabel"],
            "instrumentId": ref["instrumentId"],
            "provisions": ref.get("provisions", []),
        }
        for ref in system["basis"]
    ]


def build_country(profile: dict[str, Any], as_of: str) -> dict[str, Any]:
    slug = profile["slug"]
    iso3 = profile["iso3"]
    prefix = iso3.upper()
    systems = profile["systems"]

    requirements: list[dict[str, Any]] = []
    questions: list[dict[str, Any]] = []
    checklist: list[dict[str, Any]] = []
    conclusions: list[dict[str, Any]] = []
    models: list[dict[str, Any]] = []
    nodes: list[dict[str, Any]] = []
    permit_path: list[dict[str, Any]] = []
    source_edges: list[dict[str, Any]] = []

    node_number = 1
    gate_number = 1
    gate_orders_by_key: dict[str, int] = {}
    question_number = 1
    checklist_number = 1
    conclusion_number = 1

    for system_key in SYSTEM_ORDER:
        system = systems[system_key]
        meta = SYSTEM_META[system_key]
        workflow = WORKFLOW_META[system_key]
        req_id = f"{prefix}-BLD-REQ-{meta['priority']:03d}"
        conclusion_id = f"{prefix}-BLD-C-{conclusion_number:03d}"
        model_node_ids: list[str] = []
        model_question_ids: list[str] = []
        model_checklist_ids: list[str] = []
        previous_model_node_id = nodes[-1]["id"] if nodes else None

        requirements.append({
            "id": req_id,
            "stage": meta["stage"],
            "topic": meta["topic"],
            "status": "conditional",
            "applicability": system["applicability"],
            "requirement": system["summary"],
            "authorityIds": system["authorityIds"],
            "legalBasis": system["basis"],
            "evidenceToObtain": system["evidence"],
            "reportUse": meta["reportUse"],
        })

        country_question_id = f"{prefix}-BLD-Q-{question_number:03d}"
        model_question_ids.append(country_question_id)
        questions.append({
            "id": country_question_id,
            "blocking": True,
            "stage": meta["stage"],
            "question": system["decisionQuestion"],
            "whyItMatters": meta["genericWhy"],
            "evidenceNeeded": system["evidence"],
            "confirmWith": system["authorityIds"],
            "owner": "수원기관·현지 건축전문가",
        })
        question_number += 1

        generic_question_id = f"{prefix}-BLD-Q-{question_number:03d}"
        model_question_ids.append(generic_question_id)
        questions.append({
            "id": generic_question_id,
            "blocking": True,
            "stage": meta["stage"],
            "question": meta["genericQuestion"],
            "whyItMatters": meta["genericWhy"],
            "evidenceNeeded": meta["genericEvidence"],
            "confirmWith": system["authorityIds"],
            "owner": "수원기관·현지 건축전문가",
        })
        question_number += 1

        evidence_question_id = f"{prefix}-BLD-Q-{question_number:03d}"
        model_question_ids.append(evidence_question_id)
        questions.append({
            "id": evidence_question_id,
            "blocking": False,
            "stage": meta["stage"],
            "question": f"{system['referenceLabel']}의 사업별 적용조건을 어떤 원본·공문·현장기록으로 입증할 것인가?",
            "whyItMatters": "공개된 국가 기본경로와 실제 필지·시설·관할의 적용판정을 분리해 보고서의 과단정을 막는다.",
            "evidenceNeeded": system["evidence"],
            "confirmWith": system["authorityIds"],
            "owner": "현지 건축전문가·조사총괄",
        })
        question_number += 1

        for index, step in enumerate(workflow["steps"]):
            node_id = f"B{node_number:02d}"
            model_node_ids.append(node_id)
            question_ids = [model_question_ids[slot] for slot in step.get("questionSlots", [])]
            step_key = step.get("permitGate", {}).get("key", "")
            step_override = system.get("workflowOverrides", {}).get(step_key, {})
            node_outputs = step_outputs(step, system, step_override)
            label = render_step_text(step_override.get("label", step["label"]), system)
            action = render_step_text(step_override.get("action", step["action"]), system)
            node = {
                "id": node_id,
                "lane": step["lane"],
                "stage": workflow["stages"][step["stage"]],
                "label": label,
                "emphasis": step["emphasis"],
                "kind": step["kind"],
                "basisScope": "axis",
                "note": action,
                "action": action,
                "outputs": node_outputs,
                "authorityIds": system["authorityIds"],
                "requirementIds": [req_id],
                "questionIds": question_ids,
                "refs": system_basis_refs(system),
            }
            permit_gate = None if step_override.get("omitPermitGate") else step.get("permitGate")
            if permit_gate:
                missing_dependencies = [
                    key for key in permit_gate["dependsOn"]
                    if key not in gate_orders_by_key
                ]
                if missing_dependencies:
                    raise ValueError(
                        f"{slug}.{system_key}.{node_id}: permit gate depends on "
                        f"unknown/later gate(s) {missing_dependencies}"
                    )
                node["gateOrders"] = [gate_number]
                permit_path.append({
                    "order": gate_number,
                    "gate": render_step_text(
                        step_override.get("gate", permit_gate["gate"]), system
                    ),
                    "decision": render_step_text(
                        step_override.get("decision", permit_gate["decision"]), system
                    ),
                    "dependsOn": [
                        gate_orders_by_key[key] for key in permit_gate["dependsOn"]
                    ],
                    "output": render_step_text(
                        step_override.get("gateOutput", permit_gate["output"]), system
                    ),
                })
                gate_orders_by_key[permit_gate["key"]] = gate_number
                gate_number += 1
            nodes.append(node)
            node_number += 1

        edge_specs = workflow.get("edges") or [
            (index - 1, index, "sequence", "")
            for index in range(1, len(model_node_ids))
        ]
        if previous_model_node_id:
            source_edges.append({
                "id": f"BX{meta['priority']:02d}",
                "source": previous_model_node_id,
                "target": model_node_ids[0],
                "type": "message",
                "label": "다음 제도축 입력",
            })
        for index, (source_index, target_index, edge_type, edge_label) in enumerate(edge_specs, start=1):
            source_edge = {
                "id": f"BS{meta['priority']:02d}-{index:02d}",
                "source": model_node_ids[source_index],
                "target": model_node_ids[target_index],
                "type": edge_type,
            }
            if edge_label:
                source_edge["label"] = edge_label
            source_edges.append(source_edge)

        loop_source, loop_target, loop_label = workflow["loop"]
        source_edges.append({
            "id": f"BL{meta['priority']:02d}",
            "source": model_node_ids[loop_source],
            "target": model_node_ids[loop_target],
            "type": "loop",
            "label": loop_label,
        })

        for phase, check, output in meta["checklist"]:
            checklist_id = f"{prefix}-BLD-F-{checklist_number:03d}"
            model_checklist_ids.append(checklist_id)
            checklist.append({"id": checklist_id, "phase": phase, "check": check, "output": output})
            checklist_number += 1
        checklist_id = f"{prefix}-BLD-F-{checklist_number:03d}"
        model_checklist_ids.append(checklist_id)
        checklist.append({
            "id": checklist_id,
            "phase": "보고서 반영",
            "check": f"{meta['name']}의 확인·미확인·조건부 항목을 분리하고 근거문서 번호와 설계·일정·예산 영향을 연결한다.",
            "output": f"{meta['name']} 근거대장·보고서 반영표",
        })
        checklist_number += 1

        conclusions.append({
            "id": conclusion_id,
            "confidence": "conditional",
            "text": system["conclusion"],
            "basis": basis_sources(system),
        })
        conclusion_number += 1

        model_slug = f"{slug}-{meta['slugPart']}-construction-regulations"
        model_edges = []
        for index, (source_index, target_index, edge_type, edge_label) in enumerate(edge_specs, start=1):
            edge = {
                "id": f"M{meta['priority']:02d}-E{index:02d}",
                "source": model_node_ids[source_index],
                "target": model_node_ids[target_index],
                "type": edge_type,
            }
            if edge_label:
                edge["label"] = edge_label
            model_edges.append(edge)
        model_edges.append({
            "id": f"M{meta['priority']:02d}-L01",
            "source": model_node_ids[loop_source],
            "target": model_node_ids[loop_target],
            "type": "loop",
            "label": loop_label,
        })
        models.append({
            "id": system_key,
            "slug": model_slug,
            "priority": meta["priority"],
            "name": f"{profile['name']} {meta['name']}",
            "oneLiner": system["oneLiner"],
            "purpose": meta["purpose"],
            "verificationScope": system["verificationScope"],
            "nodeIds": model_node_ids,
            "requirementIds": [req_id],
            "questionIds": model_question_ids,
            "conclusionIds": [conclusion_id],
            "siteOverlayIds": [f"{prefix}-LOCAL-OVERLAY-001"] if system_key == "site-urban" else [],
            "fieldworkChecklistIds": model_checklist_ids,
            "edges": model_edges,
        })

    first_system = systems["site-urban"]
    first_basis = first_system["basis"][0]
    instrument_titles = {item["id"]: item["titleKo"] for item in profile["instruments"]}
    method_source_titles = [
        instrument_titles[item["instrumentId"]]
        for system in systems.values()
        for item in system["basis"]
    ]
    method_sources = "·".join(dict.fromkeys(method_source_titles))

    return {
        "schemaVersion": "0.1",
        "generatedFrom": GENERATED_FROM,
        "slug": slug,
        "asOfDate": as_of,
        "country": {
            "name": profile["name"],
            "nameEn": profile["nameEn"],
            "iso3": iso3,
            "region": profile["region"],
        },
        "purpose": (
            f"{profile['name']} ODA 건축사업의 도시계획·부지, 건축허가·환경심사, "
            "기술검사·보험·준공 핵심 제도 3종을 공식 출처와 현지 확인질문으로 정리한다."
        ),
        "verification": {
            "status": profile.get("verificationStatus", "law-linked"),
            "verifiedAt": as_of,
            "method": f"{method_sources}의 공식 법령·정부 서비스 페이지에서 제도 존재, 담당기관과 적용범위를 확인했다.",
            "scope": "국가 기본판은 핵심 제도 3종과 공식 진입경로를 확인한다. 조문 전수대조와 개별 필지·시설의 최종 적용판정은 상세조사에서 수행한다.",
            "limitations": [
                "비공식 한국어 요약이며 법률자문이나 관할기관의 유권해석을 대신하지 않는다.",
                "국가 기본판은 공식 원문·서비스를 연결한 law-linked 수준이다. 조문·시행규칙·최근 개정은 사업 착수 시 재확인한다.",
                "건폐율·용적률·높이·이격·주차, 환경평가 유형, 수수료·실제 기간과 현지 업체 비용은 필지·시설·관할에 따라 달라 확인 전 수치로 사용하지 않는다.",
            ],
        },
        "processBoard": {
            "schema_version": 1,
            "profile": "gov",
            "title": f"{profile['name']} 건축 법·제도 3축 통합 흐름",
            "subtitle": "필지 적합성 → 건축·환경허가 → 검사·준공·사용승인",
            "lanes": BOARD_LANES,
            "stages": [
                stage
                for system_key in SYSTEM_ORDER
                for stage in WORKFLOW_META[system_key]["stages"]
            ],
            "nodes": nodes,
            "edges": source_edges,
        },
        "publicModels": models,
        "authorities": profile["authorities"],
        "instruments": profile["instruments"],
        "requirements": requirements,
        "permitPath": permit_path,
        "siteOverlays": [{
            "id": f"{prefix}-LOCAL-OVERLAY-001",
            "area": "대상 필지의 관할 지방정부·계획구역·특구",
            "status": "unresolved",
            "rule": (
                "국가 법체계가 계획·허가의 틀을 정하더라도 실제 필지의 허용용도와 수치기준은 "
                "지방계획·조례·특구규정·재해지도에서 확정해야 한다."
            ),
            "legalBasis": [{
                "instrumentId": first_basis["instrumentId"],
                "provisions": first_basis.get("provisions", []),
            }],
            "missingEvidence": ["필지 식별정보", "현행 계획도·조례", "관할기관의 필지별 규제확인서"],
            "consequence": "확인 전에는 건폐율·용적률·높이·이격·주차를 국가 공통 수치로 단정하지 않는다.",
        }],
        "openQuestions": questions,
        "fieldworkChecklist": checklist,
        "reportReadyConclusions": conclusions,
    }


def validate_catalog(catalog: dict[str, Any]) -> None:
    if catalog.get("schemaVersion") != "0.1":
        raise ValueError("catalog schemaVersion must be 0.1")
    slugs: set[str] = set()
    for profile in catalog.get("countries", []):
        slug = profile.get("slug")
        if not slug or slug in slugs:
            raise ValueError(f"missing or duplicate profile slug: {slug!r}")
        slugs.add(slug)
        systems = profile.get("systems", {})
        if tuple(systems) != SYSTEM_ORDER:
            raise ValueError(f"{slug}: systems must be ordered as {SYSTEM_ORDER}")
        authority_ids = {item["id"] for item in profile.get("authorities", [])}
        instrument_ids = {item["id"] for item in profile.get("instruments", [])}
        for system_key, system in systems.items():
            for field in (
                "oneLiner", "summary", "applicability", "authorityIds", "basis", "evidence",
                "decisionQuestion", "conclusion", "verificationScope", "referenceLabel",
            ):
                if not system.get(field):
                    raise ValueError(f"{slug}.{system_key}: missing {field}")
            if set(system["authorityIds"]) - authority_ids:
                raise ValueError(f"{slug}.{system_key}: unknown authorityIds")
            for ref in system["basis"]:
                if ref["instrumentId"] not in instrument_ids:
                    raise ValueError(f"{slug}.{system_key}: unknown instrument {ref['instrumentId']}")
            overrides = system.get("workflowOverrides", {})
            if not isinstance(overrides, dict):
                raise ValueError(f"{slug}.{system_key}: workflowOverrides must be an object")
            known_gate_keys = {
                step["permitGate"]["key"]
                for step in WORKFLOW_META[system_key]["steps"]
                if step.get("permitGate")
            }
            for override_key, override in overrides.items():
                if override_key not in known_gate_keys:
                    raise ValueError(
                        f"{slug}.{system_key}: unknown workflow override {override_key!r}"
                    )
                if not isinstance(override, dict):
                    raise ValueError(
                        f"{slug}.{system_key}.{override_key}: override must be an object"
                    )
                unknown_fields = set(override) - {
                    "label", "action", "output", "gate", "decision", "gateOutput",
                    "omitPermitGate",
                }
                if unknown_fields:
                    raise ValueError(
                        f"{slug}.{system_key}.{override_key}: unknown fields "
                        f"{sorted(unknown_fields)}"
                    )
                for field in ("label", "action", "output", "gate", "decision", "gateOutput"):
                    if field in override and not override[field]:
                        raise ValueError(
                            f"{slug}.{system_key}.{override_key}: empty {field}"
                        )
                if "omitPermitGate" in override and not isinstance(
                    override["omitPermitGate"], bool
                ):
                    raise ValueError(
                        f"{slug}.{system_key}.{override_key}: omitPermitGate must be boolean"
                    )


def expected_manifest(catalog: dict[str, Any], existing: dict[str, Any]) -> dict[str, Any]:
    preserved = [
        item for item in existing.get("countries", [])
        if item.get("source") != "baseline-catalog"
    ]
    generated = [
        {
            "slug": item["slug"],
            "name": item["name"],
            "nameEn": item["nameEn"],
            "iso3": item["iso3"],
            "status": "baseline",
            "verification": item.get("verificationStatus", "law-linked"),
            "asOfDate": catalog["updatedAt"],
            "source": "baseline-catalog",
        }
        for item in catalog["countries"]
    ]
    result = dict(existing)
    result["updatedAt"] = catalog["updatedAt"]
    result["countries"] = preserved + generated
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail instead of writing stale generated files")
    args = parser.parse_args()

    catalog = read_json(CATALOG_PATH)
    manifest = read_json(MANIFEST_PATH)
    validate_catalog(catalog)

    expected: dict[Path, str] = {MANIFEST_PATH: pretty(expected_manifest(catalog, manifest))}
    for profile in catalog["countries"]:
        expected[DATA_DIR / f"{profile['slug']}.json"] = pretty(
            build_country(profile, catalog["updatedAt"])
        )

    stale: list[Path] = []
    for path, content in expected.items():
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            stale.append(path)
            if not args.check:
                path.write_text(content, encoding="utf-8")

    if stale and args.check:
        for path in stale:
            print(f"STALE: {path.relative_to(ROOT)}")
        print(f"FAILED: {len(stale)} generated construction baseline file(s) are stale")
        return 1

    action = "checked" if args.check else "built"
    print(f"OK: {len(catalog['countries'])} construction baseline country file(s) {action}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
