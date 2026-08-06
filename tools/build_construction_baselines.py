#!/usr/bin/env python3
"""Build compact three-axis construction country records from the baseline catalog.

The Senegal pilot remains a hand-maintained, article-verified detailed record.  Other
countries can start as source-linked baselines without copying the same workflow
boilerplate dozens of times.  The catalog contains only country-specific authorities,
official instruments and decision text; this builder expands it into the normal v0.1
country contract consumed by the existing validators and site generators.

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


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def pretty(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def basis_sources(system: dict[str, Any]) -> list[str]:
    return [item["instrumentId"] for item in system["basis"]]


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
    question_number = 1
    checklist_number = 1
    conclusion_number = 1

    node_labels = {
        "site-urban": ("필지·계획자료 제출", "필지별 도시계획·부지조건 확인"),
        "permit-environment": ("사업·시설·환경유형 분류", "환경결정·건축허가 심사"),
        "control-completion": ("자격·검사·보험·품질계획 확정", "준공검사·소방·사용승인"),
    }
    node_lanes = {
        "site-urban": ("사업주·현지조사팀", "도시계획·건축 당국"),
        "permit-environment": ("사업주·현지조사팀", "환경·안전·준공기관"),
        "control-completion": ("현지 설계·시공팀", "환경·안전·준공기관"),
    }
    node_stages = {
        "site-urban": ("G0 부지·계획조건", "G0 부지·계획조건"),
        "permit-environment": ("G1 분류·설계책임", "G2 건축·환경허가"),
        "control-completion": ("G3 시공·품질관리", "G4 준공·사용승인"),
    }

    for system_key in SYSTEM_ORDER:
        system = systems[system_key]
        meta = SYSTEM_META[system_key]
        req_id = f"{prefix}-BLD-REQ-{meta['priority']:03d}"
        conclusion_id = f"{prefix}-BLD-C-{conclusion_number:03d}"
        model_node_ids: list[str] = []
        model_gate_orders: list[int] = []
        model_question_ids: list[str] = []
        model_checklist_ids: list[str] = []

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

        primary_ref = system["basis"][0]
        for index in range(2):
            node_id = f"B{node_number:02d}"
            model_node_ids.append(node_id)
            model_gate_orders.append(gate_number)
            nodes.append({
                "id": node_id,
                "lane": node_lanes[system_key][index],
                "stage": node_stages[system_key][index],
                "label": node_labels[system_key][index],
                "emphasis": "lead" if index == 0 else "bottleneck",
                "note": system["oneLiner"] if index == 0 else system["decisionQuestion"],
                "authorityIds": system["authorityIds"],
                "requirementIds": [req_id],
                "gateOrders": [gate_number],
                "refs": [{
                    "source": system["referenceLabel"],
                    "instrumentId": primary_ref["instrumentId"],
                    "provisions": primary_ref.get("provisions") or ["현행 법체계·공식 대장"],
                }],
            })
            permit_path.append({
                "order": gate_number,
                "gate": node_labels[system_key][index],
                "decision": (
                    system["decisionQuestion"] if index == 1
                    else f"{meta['name']} 판단에 필요한 사업 입력과 공식 증빙을 제출한다."
                ),
                "dependsOn": [] if gate_number == 1 else [gate_number - 1],
                "output": (
                    f"{meta['name']} 입력·증빙 대장" if index == 0
                    else f"{meta['name']} 기관 확인결과와 보고서 반영표"
                ),
            })
            if node_number > 1:
                source_edges.append({
                    "id": f"BE{node_number - 1:02d}",
                    "source": f"B{node_number - 1:02d}",
                    "target": node_id,
                    "type": "sequence",
                })
            node_number += 1
            gate_number += 1

        source_edges.append({
            "id": f"BL{meta['priority']:02d}",
            "source": model_node_ids[1],
            "target": model_node_ids[0],
            "type": "loop",
            "label": "자료·설계 보완",
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

        for phase, check, output in meta["checklist"]:
            checklist_id = f"{prefix}-BLD-F-{checklist_number:03d}"
            model_checklist_ids.append(checklist_id)
            checklist.append({"id": checklist_id, "phase": phase, "check": check, "output": output})
            checklist_number += 1

        conclusions.append({
            "id": conclusion_id,
            "confidence": "conditional",
            "text": system["conclusion"],
            "basis": basis_sources(system),
        })
        conclusion_number += 1

        model_slug = f"{slug}-{meta['slugPart']}-construction-regulations"
        model_edges = [
            {
                "id": f"M{meta['priority']:02d}-E01",
                "source": model_node_ids[0],
                "target": model_node_ids[1],
                "type": "sequence",
            },
            {
                "id": f"M{meta['priority']:02d}-L01",
                "source": model_node_ids[1],
                "target": model_node_ids[0],
                "type": "loop",
                "label": "자료·설계 보완",
            },
        ]
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
    method_sources = "·".join(instrument_titles[item["instrumentId"]] for system in systems.values() for item in system["basis"])
    method_sources = "·".join(dict.fromkeys(method_sources.split("·")))

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
            "lanes": ["사업주·현지조사팀", "현지 설계·시공팀", "도시계획·건축 당국", "환경·안전·준공기관"],
            "stages": ["G0 부지·계획조건", "G1 분류·설계책임", "G2 건축·환경허가", "G3 시공·품질관리", "G4 준공·사용승인"],
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
