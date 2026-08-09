#!/usr/bin/env python3
"""Build evidence-linked three-axis construction country workflow records.

The Senegal pilot remains a hand-maintained, article-verified detailed record.  Other
countries can start as source-linked baselines without copying the same workflow
boilerplate dozens of times.  The catalog contains country-specific authorities,
official instruments and decision evidence.  When a catalog entry contains a researched
``officialProcedure``, this builder expands it into the applicant/authority procedure shown
on the main board.  Otherwise it publishes a single ``detail-unverified`` entry point instead
of inventing a statutory sequence.  ODA due-diligence questions stay in the fieldwork
checklist and open-question register, separate from the country procedure.

Usage:
    python3 tools/build_construction_baselines.py
    python3 tools/build_construction_baselines.py --check
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "construction-regulations"
CATALOG_PATH = DATA_DIR / "catalog" / "baselines.json"
PROCEDURE_OVERLAY_DIR = DATA_DIR / "catalog" / "official-procedures"
MANIFEST_PATH = DATA_DIR / "manifest.json"
GENERATED_FROM = (
    "data/construction-regulations/catalog/baselines.json + "
    "data/construction-regulations/catalog/official-procedures/"
)

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
    "건축주·신청인",
    "현지 설계·시공 전문가",
    "도시계획·건축 허가기관",
    "환경·소방·검사기관",
]

# Research scaffold for authoring a country ``officialProcedure``.  It is never published
# as a country's procedure by itself: a catalog row must opt in with researched steps.
# ``kind`` remains an epistemic contract, so axis-level sources cannot be promoted to a
# node-to-article ``statutory`` claim.  ODA-only work belongs to checklist/openQuestions.
PROCEDURE_SCAFFOLD_META = {
    "site-urban": {
        "stages": [
            "G0 신청·권원",
            "G1 계획·개발 신청",
            "G2 관계기관 심사",
            "G3 계획·개발 결정",
        ],
        "steps": [
            {
                "lane": "건축주·신청인", "stage": 0,
                "label": "필지·신청인·관할기관 특정", "emphasis": "lead",
                "kind": "field-verification",
                "action": "신청인이 필지 식별정보, 계획용도·규모와 관할 계획·개발기관을 특정한다.",
                "output": "필지·신청인·관할 확인자료", "questionSlots": [0],
            },
            {
                "lane": "건축주·신청인", "stage": 0,
                "label": "권원·토지사용 동의서류 제출", "emphasis": "key",
                "kind": "official-guidance",
                "action": "신청인이 등기·지적·임차·사용권과 소유자 동의 등 계획·개발 신청의 권원서류를 제출한다.",
                "output": "권원·경계·토지사용 동의서류", "questionSlots": [2],
            },
            {
                "lane": "도시계획·건축 허가기관", "stage": 1,
                "label": "{referenceLabel} 적용규제 분류", "emphasis": "normal",
                "kind": "official-guidance",
                "action": "관할기관이 필지와 제안 용도를 기준으로 적용 계획·개발규제, 심사경로와 사전승인 필요 여부를 분류한다.",
                "output": "적용규제·심사경로 안내 또는 사전회신", "questionSlots": [1],
            },
            {
                "lane": "현지 설계·시공 전문가", "stage": 1,
                "label": "계획·개발 신청도서 작성·접수", "emphasis": "bottleneck",
                "kind": "official-guidance",
                "action": "현지 책임전문가가 용도·배치·개발수치와 요구도서를 작성하고 신청인이 관할기관에 접수한다.",
                "output": "계획·개발 신청서와 접수증", "questionSlots": [1],
            },
            {
                "lane": "환경·소방·검사기관", "stage": 2,
                "label": "도로·배수·환경·유틸리티 협의", "emphasis": "normal",
                "kind": "field-verification",
                "action": "관계기관이 도로·배수·재해·환경과 상하수·전력 등 적용조건 및 동의 필요 여부를 심사한다.",
                "output": "관계기관 의견·동의·조건", "questionSlots": [2],
            },
            {
                "lane": "도시계획·건축 허가기관", "stage": 2,
                "label": "완비성·기술심사와 보완요구", "emphasis": "normal",
                "kind": "official-guidance",
                "action": "관할기관이 권원·계획 적합성·관계기관 의견과 신청도서를 심사하고 미비사항이 있으면 보완을 요구한다.",
                "output": "완비확인 또는 공식 보완요구서", "questionSlots": [0],
            },
            {
                "lane": "도시계획·건축 허가기관", "stage": 3,
                "label": "계획·개발 승인·조건·불허 결정", "emphasis": "bottleneck",
                "kind": "official-guidance",
                "action": "관할기관이 심사를 종결하고 승인, 조건부 승인, 비대상 회신 또는 불허를 공식 결정한다.",
                "output": "계획·개발 결정문과 승인조건", "questionSlots": [0],
                "permitGate": {
                    "key": "planning-decision",
                    "gate": "계획·개발규제 공식 적용결정",
                    "decision": (
                        "관할 계획·개발기관이 대상 필지의 계획 적합성, 적용 개발규제와 "
                        "사전승인 필요 여부를 심사해 공식 결정한다."
                    ),
                    "output": "계획·개발 승인·조건·불허 또는 비대상 회신",
                    "dependsOn": [],
                },
            },
        ],
        "loop": (5, 3, "보완요구 시 · 신청도서 수정"),
    },
    "permit-environment": {
        "stages": [
            "G4 신청·환경분류",
            "G5 허가도서 접수",
            "G6 관계기관·기술심사",
            "G7 허가결정",
        ],
        "steps": [
            {
                "lane": "건축주·신청인", "stage": 0,
                "label": "건축주·신청인·허가관할 특정", "emphasis": "lead",
                "kind": "field-verification",
                "action": "건축주 또는 적법한 대리신청인이 대상지의 건축·개발 허가기관과 환경심사기관을 특정한다.",
                "output": "신청권한·토지권원·관할 확인자료", "questionSlots": [0],
            },
            {
                "lane": "현지 설계·시공 전문가", "stage": 0,
                "label": "책임설계자 선임·시설분류", "emphasis": "key",
                "kind": "official-guidance",
                "action": "현지 서명권이 있는 책임설계자가 시설의 용도·점유·규모·위험분류와 적용 설계기준을 정한다.",
                "output": "전문자격 증빙·시설분류·설계기준표", "questionSlots": [1],
            },
            {
                "lane": "환경·소방·검사기관", "stage": 0,
                "label": "환경 스크리닝·평가유형 결정", "emphasis": "bottleneck",
                "kind": "official-guidance",
                "action": "관할 환경기관이 사업정보를 심사해 비대상·면제·간이평가·본평가 등 적용유형과 선행조건을 결정한다.",
                "output": "환경 분류·승인·면제 또는 비대상 결정문", "questionSlots": [0],
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
                "lane": "현지 설계·시공 전문가", "stage": 1,
                "label": "허가도서·환경조건 작성·접수", "emphasis": "normal",
                "kind": "official-guidance",
                "action": "책임설계자가 환경결정과 적용기준을 반영한 건축·개발 허가도서를 작성하고 신청인이 수수료와 함께 접수한다.",
                "output": "건축·개발 허가신청서·도서·접수증", "questionSlots": [1],
                "dependsOnStepIndexes": [1, 2],
            },
            {
                "lane": "환경·소방·검사기관", "stage": 2,
                "label": "소방·안전·도로·유틸리티 협의", "emphasis": "normal",
                "kind": "field-verification",
                "action": "관계기관이 소방·안전·도로·물·전력 등 해당 분야를 심사하고 필요한 동의·NOC 또는 조건을 회신한다.",
                "output": "관계기관 동의·NOC·심사의견", "questionSlots": [2],
                "dependsOnStepIndexes": [3],
            },
            {
                "lane": "도시계획·건축 허가기관", "stage": 2,
                "label": "완비성·기술심사와 보완요구", "emphasis": "normal",
                "kind": "official-guidance",
                "action": "허가기관이 신청도서, 환경조건과 관계기관 의견을 심사하고 미비·부적합 사항이 있으면 공식 보완을 요구한다.",
                "output": "완비확인·기술심사의견 또는 보완요구서", "questionSlots": [2],
            },
            {
                "lane": "도시계획·건축 허가기관", "stage": 3,
                "label": "건축·개발허가 최종결정", "emphasis": "bottleneck",
                "kind": "official-guidance",
                "action": "허가기관이 심사를 종결하고 허가, 조건부 허가 또는 불허를 결정해 승인도서와 조건을 발급한다.",
                "output": "건축·개발 허가결정문과 승인도서·조건", "questionSlots": [0],
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
            (0, 1, "sequence", "전문가 선임"),
            (1, 2, "message", "사업분류 입력"),
            (2, 3, "message", "환경조건"),
            (3, 4, "sequence", "협의요청"),
            (4, 5, "message", "기관의견"),
            (5, 6, "sequence", "심사완료"),
        ],
        "loop": (5, 3, "보완요구 시 · 허가도서·NOC 수정"),
    },
    "control-completion": {
        "stages": [
            "G8 착공 준비",
            "G9 시공·단계검사",
            "G10 시정·준공신청",
            "G11 준공·사용결정",
        ],
        "steps": [
            {
                "lane": "건축주·신청인", "stage": 0,
                "label": "등록 시공·감리자 선임·착공신고", "emphasis": "lead",
                "kind": "field-verification",
                "action": "허가권자가 요구하는 등록 시공자·감리자와 의무보험을 갖추고 착공신고 또는 착공승인을 신청한다.",
                "output": "자격·보험 증빙과 착공신고·승인서", "questionSlots": [0],
            },
            {
                "lane": "현지 설계·시공 전문가", "stage": 0,
                "label": "승인도서·검사 Hold Point 확정", "emphasis": "key",
                "kind": "official-guidance",
                "action": "책임전문가와 시공자가 승인도서·허가조건, 적용 코드와 법정 단계검사 시점을 현장 실행계획에 반영한다.",
                "output": "승인도서·허가조건·검사계획", "questionSlots": [1],
            },
            {
                "lane": "현지 설계·시공 전문가", "stage": 1,
                "label": "승인도서에 따른 시공·기록 작성", "emphasis": "normal",
                "kind": "official-guidance",
                "action": "시공자와 감리자가 승인도서에 따라 시공하고 자재·시험·사진·감리·변경 기록을 작성한다.",
                "output": "시공·품질·시험·감리 기록", "questionSlots": [1],
            },
            {
                "lane": "환경·소방·검사기관", "stage": 1,
                "label": "법정 단계검사·시험 확인", "emphasis": "normal",
                "kind": "field-verification",
                "action": "관할 검사기관이 기초·구조·설비·소방 등 적용되는 단계검사와 시험 결과를 확인한다.",
                "output": "단계검사 기록·시험성적·검사확인", "questionSlots": [2],
            },
            {
                "lane": "현지 설계·시공 전문가", "stage": 2,
                "label": "부적합 시정·변경승인·재검사", "emphasis": "bottleneck",
                "kind": "field-verification",
                "action": "신청인과 책임전문가가 검사 부적합을 시정하고 필요한 설계변경 승인을 받은 뒤 재검사를 요청한다.",
                "output": "시정·변경승인·재검사 종결기록", "questionSlots": [2],
            },
            {
                "lane": "건축주·신청인", "stage": 2,
                "label": "준공도서 제출·최종검사 신청", "emphasis": "normal",
                "kind": "official-guidance",
                "action": "신청인이 준공도면, 시험·감리·소방 등 요구증빙을 제출하고 최종검사와 준공·점유·사용승인을 신청한다.",
                "output": "준공·점유 신청서와 준공도서", "questionSlots": [0],
            },
            {
                "lane": "도시계획·건축 허가기관", "stage": 3,
                "label": "준공·점유·사용 최종결정", "emphasis": "bottleneck",
                "kind": "official-guidance",
                "action": "관할 건축·검사·소방기관이 최종검사와 제출도서를 심사해 준공·점유·사용승인, 보완 또는 불승인을 결정한다.",
                "output": "최종검사 결과와 준공·점유·사용승인서", "questionSlots": [0],
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
        ],
        "loop": (4, 2, "부적합 시 · 시정·재검사"),
    },
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def apply_procedure_overlays(catalog: dict[str, Any]) -> dict[str, Any]:
    """Merge independently reviewable country procedure research into the catalog.

    The base catalog remains the country/instrument inventory. Detailed statutory
    procedures live one country per file so researchers can work in parallel without
    editing the same large JSON document. Overlay authorities and instruments are
    upserted by ID; system fields are shallow patches, normally an
    ``officialProcedure`` plus a more precise verification scope.
    """
    merged = copy.deepcopy(catalog)
    profiles = {item["slug"]: item for item in merged.get("countries", [])}
    if not PROCEDURE_OVERLAY_DIR.exists():
        return merged

    for path in sorted(PROCEDURE_OVERLAY_DIR.glob("*.json")):
        overlay = read_json(path)
        if overlay.get("schemaVersion") != "0.1":
            raise ValueError(f"{path.name}: schemaVersion must be 0.1")
        slug = overlay.get("slug")
        if slug not in profiles:
            raise ValueError(f"{path.name}: unknown country slug {slug!r}")
        if path.stem != slug:
            raise ValueError(f"{path.name}: filename must match slug {slug!r}")
        profile = profiles[slug]

        for collection in ("authorities", "instruments"):
            patches = overlay.get(collection, [])
            if not isinstance(patches, list):
                raise ValueError(f"{path.name}: {collection} must be a list")
            target = profile[collection]
            positions = {item["id"]: index for index, item in enumerate(target)}
            for patch in patches:
                ident = patch.get("id") if isinstance(patch, dict) else None
                if not ident:
                    raise ValueError(f"{path.name}: {collection} patch lacks id")
                if ident in positions:
                    target[positions[ident]] = {**target[positions[ident]], **patch}
                else:
                    positions[ident] = len(target)
                    target.append(patch)

        system_patches = overlay.get("systems", {})
        if not isinstance(system_patches, dict) or not system_patches:
            raise ValueError(f"{path.name}: systems must be a non-empty object")
        unknown_systems = set(system_patches) - set(SYSTEM_ORDER)
        if unknown_systems:
            raise ValueError(f"{path.name}: unknown systems {sorted(unknown_systems)}")
        for system_key, patch in system_patches.items():
            if not isinstance(patch, dict):
                raise ValueError(f"{path.name}: systems.{system_key} must be an object")
            profile["systems"][system_key] = {
                **profile["systems"][system_key],
                **patch,
            }
    return merged


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


def unverified_entry_workflow(system_key: str, system: dict[str, Any]) -> dict[str, Any]:
    """Expose only the country evidence actually present in a baseline catalog row.

    A system summary proves that a regulatory axis and official entry point exist; it
    does not prove a seven-step statutory order.  Until ``officialProcedure`` is
    researched, publish one explicit evidence entry instead of compiling the shared ODA
    checklist into a fictional country procedure.
    """
    stage_code = {"site-urban": "G0", "permit-environment": "G4", "control-completion": "G8"}[system_key]
    return {
        "coverage": "detail-unverified",
        "scope": system["verificationScope"],
        "stages": [f"{stage_code} 공식 절차 진입점"],
        "steps": [{
            "lane": "도시계획·건축 허가기관",
            "stage": 0,
            "label": f"{system['referenceLabel']} · 절차 상세 미확인",
            "emphasis": "bottleneck",
            "kind": "field-verification",
            "action": system["summary"],
            "output": "관할기관의 현행 절차도·신청서·체크리스트 확인 필요",
            "questionSlots": [0, 1, 2],
        }],
        "edges": [],
    }


AXIS_GRADE_ORDER = {
    "detail-unverified": 0,
    "source-linked": 1,
    "official-source-linked": 2,
    "article-linked": 3,
    "article-verified": 4,
}
# 축 등급 5종을 국가 공표 등급 4종(manifest.verificationLevels)으로 옮긴다.
AXIS_TO_COUNTRY_STATUS = {
    "detail-unverified": "source-linked",
    "source-linked": "source-linked",
    "official-source-linked": "law-linked",
    "article-linked": "law-linked",
    "article-verified": "article-verified",
}


def derive_country_verification_status(models: list[dict[str, Any]]) -> str:
    """국가 등급은 가장 약한 축을 따른다.

    세 축 중 하나라도 조문 대조 전이면 "이 국가 자료는 조문 대조를 마쳤다"고
    말할 수 없다. 수기 필드로 관리하면 축 등급과 어긋나 한 페이지 안에서
    배지가 서로 모순되므로 파생값으로 계산한다.
    """
    if not models:
        return "source-linked"
    weakest = min(
        (model.get("procedureStatus", "source-linked") for model in models),
        key=lambda grade: AXIS_GRADE_ORDER.get(grade, 0),
    )
    return AXIS_TO_COUNTRY_STATUS.get(weakest, "law-linked")


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
    all_stages: list[str] = []

    node_number = 1
    gate_number = 1
    gate_orders_by_key: dict[str, int] = {}
    question_number = 1
    checklist_number = 1
    conclusion_number = 1

    for system_key in SYSTEM_ORDER:
        system = systems[system_key]
        meta = SYSTEM_META[system_key]
        workflow = system.get("officialProcedure") or unverified_entry_workflow(
            system_key, system
        )
        all_stages.extend(workflow["stages"])
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
            # 공개된 법정절차와 사업별 ODA 확인질문을 혼합하지 않는다. 상세절차가
            # 아직 확인되지 않은 단일 진입점만 해당 모델의 질문을 연결한다.
            question_ids = (
                []
                if system.get("officialProcedure")
                else [model_question_ids[slot] for slot in step.get("questionSlots", [])]
            )
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
                "basisScope": step.get("basisScope", "axis"),
                "note": action,
                "action": action,
                "outputs": node_outputs,
                "authorityIds": step.get("authorityIds", system["authorityIds"]),
                "requirementIds": [req_id],
                "questionIds": question_ids,
                "refs": step.get("refs", system_basis_refs(system)),
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

        loop = workflow.get("loop")
        if loop:
            loop_source, loop_target, loop_label = loop
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
        if loop:
            loop_source, loop_target, loop_label = loop
            model_edges.append({
                "id": f"M{meta['priority']:02d}-L01",
                "source": model_node_ids[loop_source],
                "target": model_node_ids[loop_target],
                "type": "loop",
                "label": loop_label,
            })
        # 전국에 발행됐어도 주·지방의 채택으로 효력이 완성되는 근거만 있는 축은
        # 통일 제도가 있는 것처럼 읽히면 안 된다. 근거에서 직접 계산해 표시한다.
        instrument_scopes = {
            item["id"]: item.get("scope") for item in profile["instruments"]
        }
        axis_instrument_ids = {
            ref["instrumentId"]
            for node_id in model_node_ids
            for ref in next(
                (node["refs"] for node in nodes if node["id"] == node_id), []
            )
            if ref.get("instrumentId")
        }
        national_framework = (
            "adoption-dependent"
            if any(
                instrument_scopes.get(item) == "adoption-dependent"
                for item in axis_instrument_ids
            )
            else "established"
        )
        models.append({
            "id": system_key,
            "slug": model_slug,
            "priority": meta["priority"],
            "nationalFramework": national_framework,
            # 공개 제목은 조달 3축과 같은 `국가명 + 제도명` 형식으로 고정한다.
            # 국가별 절차명은 지역 창구·사례 이름을 달고 오기 쉬워 제목으로 쓰지 않는다.
            "name": f"{profile['name']} {meta['name']}",
            "oneLiner": system["oneLiner"],
            "purpose": meta["purpose"],
            "verificationScope": system["verificationScope"],
            "procedureStatus": workflow.get("coverage", "source-linked"),
            "procedureScope": workflow.get("scope", system["verificationScope"]),
            "nodeIds": model_node_ids,
            "requirementIds": [req_id],
            "questionIds": model_question_ids,
            "conclusionIds": [conclusion_id],
            "siteOverlayIds": [f"{prefix}-LOCAL-OVERLAY-001"] if system_key == "site-urban" else [],
            "fieldworkChecklistIds": model_checklist_ids,
            "edges": model_edges,
            "decisionBranches": workflow.get("decisionBranches", []),
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
    country_status = derive_country_verification_status(models)

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
            "status": country_status,
            "verifiedAt": as_of,
            "method": f"{method_sources}의 공식 법령·정부 서비스 페이지에서 제도 존재, 담당기관과 적용범위를 확인했다.",
            "scope": "국가 기본판은 핵심 제도 3종과 공식 진입경로를 확인한다. 조문 전수대조와 개별 필지·시설의 최종 적용판정은 상세조사에서 수행한다.",
            "limitations": [
                "비공식 한국어 요약이며 법률자문이나 관할기관의 유권해석을 대신하지 않는다.",
                "자료의 현행·운영 상태는 사이트가 자료별 상태·확인일·판단근거로 관리한다. 최신 개정 추적이 끝나지 않은 자료만 검증 예외로 별도 표시한다.",
                "건폐율·용적률·높이·이격·주차, 환경평가 유형, 수수료·실제 기간과 현지 업체 비용은 필지·시설·관할에 따라 달라 확인 전 수치로 사용하지 않는다.",
            ],
        },
        "processBoard": {
            "schema_version": 1,
            "profile": "gov",
            "title": f"{profile['name']} 건축 법·제도 3축 통합 흐름",
            "subtitle": "필지 적합성 → 건축·환경허가 → 검사·준공·사용승인",
            "lanes": [lane for lane in BOARD_LANES if any(node["lane"] == lane for node in nodes)],
            "stages": list(dict.fromkeys(all_stages)),
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
            procedure = system.get("officialProcedure")
            if procedure is not None:
                if not isinstance(procedure, dict):
                    raise ValueError(f"{slug}.{system_key}: officialProcedure must be an object")
                if procedure.get("coverage") not in {"source-linked", "official-source-linked", "article-linked", "article-verified"}:
                    raise ValueError(f"{slug}.{system_key}: invalid officialProcedure coverage")
                stages = procedure.get("stages")
                steps = procedure.get("steps")
                if not isinstance(stages, list) or not stages or not all(stages):
                    raise ValueError(f"{slug}.{system_key}: officialProcedure needs stages")
                if not isinstance(steps, list) or not steps:
                    raise ValueError(f"{slug}.{system_key}: officialProcedure needs steps")
                gate_keys: set[str] = set()
                for index, step in enumerate(steps):
                    where = f"{slug}.{system_key}.officialProcedure.steps[{index}]"
                    for field in ("lane", "stage", "label", "emphasis", "kind", "action", "output"):
                        if field not in step or step[field] in (None, ""):
                            raise ValueError(f"{where}: missing {field}")
                    if step["lane"] not in BOARD_LANES:
                        raise ValueError(f"{where}: unknown lane {step['lane']!r}")
                    if not isinstance(step["stage"], int) or not 0 <= step["stage"] < len(stages):
                        raise ValueError(f"{where}: invalid stage index")
                    if step["kind"] not in {
                        "statutory", "official-guidance", "local-example", "field-verification"
                    }:
                        raise ValueError(f"{where}: invalid kind {step['kind']!r}")
                    unknown_authorities = set(step.get("authorityIds", [])) - authority_ids
                    if unknown_authorities:
                        raise ValueError(f"{where}: unknown authorities {sorted(unknown_authorities)}")
                    for ref in step.get("refs", []):
                        if ref.get("instrumentId") not in instrument_ids:
                            raise ValueError(f"{where}: unknown instrument {ref.get('instrumentId')!r}")
                    gate = step.get("permitGate")
                    if gate:
                        key = gate.get("key")
                        if not key or key in gate_keys:
                            raise ValueError(f"{where}: missing or duplicate permitGate key")
                        missing = set(gate.get("dependsOn", [])) - gate_keys
                        if missing:
                            raise ValueError(f"{where}: permitGate depends on later/unknown {sorted(missing)}")
                        gate_keys.add(key)
                for edge_index, edge in enumerate(procedure.get("edges", [])):
                    if not isinstance(edge, list) or len(edge) != 4:
                        raise ValueError(f"{slug}.{system_key}: invalid officialProcedure edge {edge_index}")
                    source, target, edge_type, _ = edge
                    if source not in range(len(steps)) or target not in range(len(steps)):
                        raise ValueError(f"{slug}.{system_key}: edge {edge_index} references unknown step")
                    if edge_type not in {"sequence", "message", "loop"}:
                        raise ValueError(f"{slug}.{system_key}: edge {edge_index} has invalid type")
                loop = procedure.get("loop")
                if loop is not None:
                    if (
                        not isinstance(loop, list) or len(loop) != 3
                        or loop[0] not in range(len(steps)) or loop[1] not in range(len(steps))
                        or not loop[2]
                    ):
                        raise ValueError(f"{slug}.{system_key}: invalid officialProcedure loop")
                branches = procedure.get("decisionBranches", [])
                if branches and {
                    item.get("state") for item in branches if isinstance(item, dict)
                } != {"success", "rework", "reject"}:
                    raise ValueError(f"{slug}.{system_key}: decisionBranches need success/rework/reject")
            overrides = system.get("workflowOverrides", {})
            if not isinstance(overrides, dict):
                raise ValueError(f"{slug}.{system_key}: workflowOverrides must be an object")
            known_gate_keys = {
                step["permitGate"]["key"]
                for step in PROCEDURE_SCAFFOLD_META[system_key]["steps"]
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


def expected_manifest(
    catalog: dict[str, Any],
    existing: dict[str, Any],
    statuses: dict[str, str] | None = None,
) -> dict[str, Any]:
    preserved = [
        item for item in existing.get("countries", [])
        if item.get("source") != "baseline-catalog"
    ]
    statuses = statuses or {}
    generated = [
        {
            "slug": item["slug"],
            "name": item["name"],
            "nameEn": item["nameEn"],
            "iso3": item["iso3"],
            "status": "baseline",
            # 국가 파일과 같은 파생값을 쓴다. catalog의 수기 verificationStatus를
            # 그대로 실으면 대장과 국가 파일이 서로 다른 등급을 말하게 된다.
            "verification": statuses.get(
                item["slug"], item.get("verificationStatus", "law-linked")
            ),
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

    catalog = apply_procedure_overlays(read_json(CATALOG_PATH))
    manifest = read_json(MANIFEST_PATH)
    validate_catalog(catalog)

    expected: dict[Path, str] = {}
    statuses: dict[str, str] = {}
    for profile in catalog["countries"]:
        record = build_country(profile, catalog["updatedAt"])
        statuses[profile["slug"]] = record["verification"]["status"]
        expected[DATA_DIR / f"{profile['slug']}.json"] = pretty(record)
    expected[MANIFEST_PATH] = pretty(expected_manifest(catalog, manifest, statuses))

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
