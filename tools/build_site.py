#!/usr/bin/env python3
"""data/institutions/*.json → site/ 정적 HTML 생성.

원본 how-did-they-do-all-that-procurement의 화면 구성을 승계한다.
  /                    제도 대장 (검색·국가/축 필터·비교 선반)
  /model/{slug}/       국가별 제도 한 장 요약 (조달 1~3 + 건축 4~)
  /verification/       현행 기준 확인 대장
  /construction/       이전 주소 호환용 리디렉션
  /construction/{slug}/이전 주소 호환용 리디렉션

의존성 없음. 빌드 후 site/를 그대로 열거나 정적 호스팅에 올리면 된다.

사용법:
    python3 tools/build_site.py
"""
from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INST_DIR = ROOT / "data" / "institutions"
CONSTRUCTION_DIR = ROOT / "data" / "construction-regulations"
SITE = ROOT / "site"

SITE_TITLE = "그 나라, 조달하고 건축하려면?"
SITE_SUB = "협력국 조달·건축 법·제도 안내"


def clean_generated_html(value: str) -> str:
    """생성 HTML의 줄 끝 공백을 제거하고 POSIX 개행으로 끝낸다."""
    return "\n".join(line.rstrip() for line in value.splitlines()) + "\n"


AXIS_LABEL = {
    "bidding": "입찰제도",
    "governance": "조달 거버넌스",
    "pipeline": "ODA 사업형성",
    "construction": "건축 법·제도",
}
AXIS_SUFFIX = {
    "bidding": "-bidding-system",
    "governance": "-procurement-governance",
    "pipeline": "-oda-project-pipeline",
    "construction": "-construction-regulations",
}
VERIF_LABEL = {
    "article-verified": "조문 대조 완료",
    "law-linked": "원문 링크 연결",
    "source-linked": "공식자료 연결",
    "source-document": "자료집 기재",
    "needs-review": "재검토 필요",
}
VERIF_TONE = {
    "article-verified": "ok",
    "law-linked": "info",
    "source-linked": "info",
    "source-document": "muted",
    "needs-review": "bad",
}
SEV_LABEL = {"high": "필수 확인", "medium": "추가 확인", "low": "참고"}
NODE_TONE = {"current": "key", "risk": "warn", "loop": "back"}
KIND_LABEL = {
    "act": "법률",
    "regulation": "시행규칙",
    "ordinance": "명령·조례",
    "directive": "지침·정책",
    "standard-document": "표준문서",
    "treaty-agreement": "양자합의",
    "donor-rule": "공여기관 규정",
    "practice": "현장 관행",
    "decree": "시행령·명령",
    "order": "부령",
    "plan": "도시계획",
    "official-guidance": "공식 안내",
    "draft": "법안",
}


UP_STATE_LABEL = {
    "not-reported": "미제보",
    "reported": "제보함 · 회신 대기",
    "acknowledged": "발행처 확인",
    "fixed": "개정판 반영",
    "declined": "정정 불요 회신",
}
SEV_TONE = {"high": "bad", "medium": "warn", "low": "muted"}

CONSTRUCTION_STAGE_LABEL = {
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
CONSTRUCTION_STAGE_ORDER = list(CONSTRUCTION_STAGE_LABEL)
CONSTRUCTION_STATUS_LABEL = {
    "confirmed": "확정",
    "conditional": "조건부",
    "unresolved": "미확정",
    "in_force": "현행",
    "superseded": "폐지·대체",
    "pending": "심의·예고",
    "continuity_unverified": "현행성 재확인",
}
CONSTRUCTION_STATUS_TONE = {
    "confirmed": "ok",
    "conditional": "warn",
    "unresolved": "bad",
    "in_force": "ok",
    "superseded": "muted",
    "pending": "warn",
    "continuity_unverified": "bad",
}
CONSTRUCTION_VERIFY_LABEL = {
    "article-verified": "조문 대조 완료",
    "law-linked": "법령 원문 연결",
    "source-linked": "공식자료 연결",
    "needs-review": "추가 확인",
}


def e(s) -> str:
    return html.escape(str(s if s is not None else ""))


COUNTRY_SORT_ALIAS = {
    # 내부 데이터 키는 DR콩고를 유지하되 가나다순에서는 정식 국명으로 정렬한다.
    "DR콩고": "콩고민주공화국",
}
COUNTRY_DISPLAY_ALIAS = {
    "DR콩고": "콩고민주공화국(DR콩고)",
}


def country_name_sort_key(name: str) -> str:
    """국가 표시명을 한글 가나다순으로 정렬하기 위한 키."""
    return COUNTRY_SORT_ALIAS.get(name, name)


def country_display_name(name: str) -> str:
    """목록에서는 한글 정식 국명을 우선 표시한다."""
    return COUNTRY_DISPLAY_ALIAS.get(name, name)


def country_slug(d: dict) -> str:
    """제도 slug에서 국가 식별자를 얻는다.

    영문 국명은 ``Viet Nam``/``vietnam``처럼 파일 slug와 다를 수 있으므로
    배포 파일의 키로 사용하지 않는다.
    """
    if d.get("countryKey"):
        return d["countryKey"]
    suffix = AXIS_SUFFIX[d["axis"]]
    if not d["slug"].endswith(suffix):
        raise ValueError(f"제도 slug 접미사 불일치: {d['slug']}")
    return d["slug"][:-len(suffix)]


SENEGAL_CONSTRUCTION_DISPLAY_STAGE = {
    "G0 부지·권원": "G1 부지확정",
    "G1 사업분류·책임체계": "G2 분류·책임",
    "G2 환경·기본설계": "G2 분류·책임",
    "G3 관계기관 사전협의": "G3 설계·사전협의",
    "G4 건축허가": "G4 허가·착공",
    "G5 착공 선행조건": "G4 허가·착공",
    "G6 시공·변경·검사": "G5 시공·변경",
    "G7 준공·적합": "G6 준공·개장·인계",
    "G8 개장·운영인계": "G6 준공·개장·인계",
}
SENEGAL_CONSTRUCTION_DISPLAY_STAGES = [
    "G1 부지확정",
    "G2 분류·책임",
    "G3 설계·사전협의",
    "G4 허가·착공",
    "G5 시공·변경",
    "G6 준공·개장·인계",
]
SENEGAL_CONSTRUCTION_GATE_DISPLAY_STAGE = {
    1: "G1 부지확정",
    2: "G2 분류·책임",
    3: "G2 분류·책임",
    4: "G2 분류·책임",
    5: "G3 설계·사전협의",
    6: "G4 허가·착공",
    7: "G4 허가·착공",
    8: "G5 시공·변경",
    9: "G6 준공·개장·인계",
    10: "G6 준공·개장·인계",
}
CONSTRUCTION_EMPHASIS_TO_STATUS = {
    "lead": "current",
    "key": "current",
    "bottleneck": "risk",
    "normal": "waiting",
}
CONSTRUCTION_STATUS_CONFIDENCE = {
    "confirmed": 0.9,
    "conditional": 0.75,
    "unresolved": 0.55,
}
SENEGAL_CONSTRUCTION_NODE_DEADLINE = {
    "B02": "도시계획확인서(CU)는 완비신청 기준 8일, 유효기간 6개월. PUD 원본 확보와 필지 매칭 기간은 별도다.",
    "B05": "검증된 최종 환경보고서 접수 후 임시 환경적합확인서는 15일. 스크리닝·평가작성·공공참여·기술위원회 검증의 전체기간 상한은 확인되지 않았다.",
    "B10": "완비서류 기준 단순 28근무일·복합 40근무일. 보완기간에는 심사시계가 중단되고 미착공 2년이면 허가가 실효될 수 있다.",
    "B12": "의무 기술검사 대상의 굴착 개시허가는 완비서류 기준 15근무일.",
    "B16": "적합증명서는 완비된 접수 후 법정 18일. 무응답 간주절차는 후속 서면촉구가 필요하다.",
}

SENEGAL_CONSTRUCTION_QUESTION_NODES = {
    "SEN-BLD-Q-001": ["B01"],
    "SEN-BLD-Q-002": ["B02"],
    "SEN-BLD-Q-003": ["B03"],
    "SEN-BLD-Q-004": ["B09", "B10"],
    "SEN-BLD-Q-005": ["B04"],
    "SEN-BLD-Q-006": ["B05"],
    "SEN-BLD-Q-007": ["B01", "B06"],
    "SEN-BLD-Q-008": ["B06"],
    "SEN-BLD-Q-009": ["B11"],
    "SEN-BLD-Q-010": ["B11"],
    "SEN-BLD-Q-011": ["B09"],
    "SEN-BLD-Q-012": ["B18"],
}


def script_json(value) -> str:
    """JSON을 inline script에서 안전하게 쓸 수 있게 직렬화한다."""
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def construction_presentation(d: dict, board: dict, *, segmented: bool = False) -> dict:
    """국가별 표시 보정과 일반 fallback을 분리한다.

    세네갈 법정기한이나 노드 ID가 다음 국가에 새어 나가지 않도록 국가별
    보정은 slug 아래에만 둔다. 새 데이터는 원천 board의 단계·노드 메타를
    그대로 표시하는 fallback으로도 빌드된다.
    """
    stage_map = {}
    for index, stage in enumerate(board["stages"], start=1):
        code, _, label = stage.partition(" ")
        if segmented and re.fullmatch(r"G\d+", code):
            # 공개 보드의 생애주기 단계(S)는 permitPath의 인허가 절차(P)와
            # 별도 체계다. 원래 단계 번호를 보존해 P1~P10과 혼동하지 않는다.
            stage_map[stage] = f"S{code[1:]} {label or stage}"
        else:
            stage_map[stage] = f"G{index} {label or stage}"
    config = {
        "stage_map": stage_map,
        "stages": list(stage_map.values()),
        "gate_stage": {},
        "deadlines": {},
        "question_nodes": {},
    }
    if d["slug"] == "senegal":
        config.update({
            "deadlines": SENEGAL_CONSTRUCTION_NODE_DEADLINE,
            "question_nodes": SENEGAL_CONSTRUCTION_QUESTION_NODES,
        })
        if not segmented:
            config.update({
                "stage_map": SENEGAL_CONSTRUCTION_DISPLAY_STAGE,
                "stages": SENEGAL_CONSTRUCTION_DISPLAY_STAGES,
                "gate_stage": SENEGAL_CONSTRUCTION_GATE_DISPLAY_STAGE,
            })
    return config


def unique_strings(values) -> list[str]:
    """순서를 보존해 빈 문자열과 중복을 제거한다."""
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def construction_model_board(d: dict, model_spec: dict | None) -> dict:
    """전체 생애주기 보드에서 공개 제도축에 필요한 노드만 투영한다."""
    if not model_spec:
        return d["processBoard"]
    source = d["processBoard"]
    node_ids = set(model_spec["nodeIds"])
    nodes = [item for item in source["nodes"] if item["id"] in node_ids]
    used_lanes = {item["lane"] for item in nodes}
    used_stages = {item["stage"] for item in nodes}
    return {
        "schema_version": source["schema_version"],
        "profile": source["profile"],
        "title": model_spec["name"],
        "subtitle": model_spec["oneLiner"],
        "lanes": [item for item in source["lanes"] if item in used_lanes],
        "stages": [item for item in source["stages"] if item in used_stages],
        "nodes": nodes,
        "edges": model_spec["edges"],
    }


def construction_to_model(d: dict, model_spec: dict | None = None) -> dict:
    """건축 sidecar를 공개 사이트의 model view로 변환한다.

    국가 원천 데이터는 하나로 유지하되 ``publicModels``가 있으면 도시계획,
    인허가, 기술검사·준공처럼 독립된 제도축으로 투영한다.
    """
    board = construction_model_board(d, model_spec)
    instruments = {item["id"]: item for item in d["instruments"]}
    authorities = {item["id"]: item for item in d["authorities"]}
    requirements = {item["id"]: item for item in d["requirements"]}
    permit_path = {item["order"]: item for item in d["permitPath"]}
    questions = {item["id"]: item for item in d["openQuestions"]}
    context = d.get("pilotContext") or {}
    presentation = construction_presentation(d, board, segmented=bool(model_spec))

    selected_requirement_ids = set(
        model_spec.get("requirementIds", [])
        if model_spec else requirements
    )
    selected_question_ids = set(
        model_spec.get("questionIds", []) if model_spec else questions
    )
    selected_gate_orders = {
        order for node in board["nodes"] for order in node.get("gateOrders", [])
    }
    selected_conclusion_ids = set(
        model_spec.get("conclusionIds", [])
        if model_spec else (item["id"] for item in d.get("reportReadyConclusions", []))
    )
    selected_overlay_ids = set(
        model_spec.get("siteOverlayIds", [])
        if model_spec else (item["id"] for item in d.get("siteOverlays", []))
    )
    selected_checklist_ids = set(
        model_spec.get("fieldworkChecklistIds", [])
        if model_spec else (item["id"] for item in d.get("fieldworkChecklist", []))
    )

    def law_name(instrument: dict) -> str:
        return instrument.get("titleKo") or instrument["title"]

    process_nodes = []
    for node in board["nodes"]:
        linked_requirements = [
            requirements[ident] for ident in node.get("requirementIds", [])
            if ident in requirements and ident in selected_requirement_ids
        ]
        requirement_stages = {item["stage"] for item in linked_requirements}
        question_ids = list(node.get("questionIds", []))
        if not question_ids:
            question_ids = [
                ident for ident, node_ids in presentation["question_nodes"].items()
                if node["id"] in node_ids
            ]
        if not question_ids and not presentation["question_nodes"]:
            question_ids = [
                item["id"] for item in d["openQuestions"]
                if item["stage"] in requirement_stages and item["id"] in selected_question_ids
            ]
        question_ids = [ident for ident in question_ids if ident in selected_question_ids]
        matching_questions = [questions[ident] for ident in question_ids if ident in questions]
        actor_names = unique_strings(
            authorities[ident]["nameKo"] for ident in node.get("authorityIds", [])
            if ident in authorities
        )
        action_parts = [node.get("note", "")]
        action_parts.extend(
            f'{item["topic"]}: {item["requirement"]}' for item in linked_requirements
        )
        output_documents = []
        for item in linked_requirements:
            output_documents.extend(item.get("evidenceToObtain", []))
        for order in node.get("gateOrders", []):
            if order in permit_path:
                output_documents.append(permit_path[order]["output"])

        basis_refs = list(node.get("refs", []))
        for item in linked_requirements:
            basis_refs.extend(item.get("legalBasis", []))
        basis_by_instrument: dict[str, dict] = {}
        for ref in basis_refs:
            instrument_id = ref.get("instrumentId")
            instrument = instruments.get(instrument_id)
            if not instrument:
                continue
            basis = basis_by_instrument.setdefault(instrument_id, {
                "instrument_id": instrument_id,
                "law": law_name(instrument),
                "provisions": [],
                "sources": [],
                "url": instrument.get("officialUrl", ""),
                "kind": instrument["kind"],
                "status": instrument["status"],
                "verification_level": instrument["verificationLevel"],
                "note": instrument.get("note", ""),
            })
            basis["provisions"].extend(ref.get("provisions", []))
            if ref.get("source"):
                basis["sources"].append(ref["source"])
        legal_basis = []
        for basis in basis_by_instrument.values():
            provisions = unique_strings(basis.pop("provisions"))
            sources = unique_strings(basis.pop("sources"))
            basis["article"] = ", ".join(provisions or sources) or "세부 조문·사업 적용 확인 필요"
            legal_basis.append(basis)

        states = [item["status"] for item in linked_requirements]
        confidence = min(
            (CONSTRUCTION_STATUS_CONFIDENCE.get(state, 0.7) for state in states),
            default=0.8,
        )
        display_stage = next(
            (
                presentation["gate_stage"][order]
                for order in node.get("gateOrders", [])
                if order in presentation["gate_stage"]
            ),
            presentation["stage_map"].get(node["stage"], node["stage"]),
        )
        permit_gates = [permit_path[order] for order in node.get("gateOrders", []) if order in permit_path]
        process_nodes.append({
            "id": node["id"],
            "name": node["label"],
            "lane": node["lane"],
            "stage": display_stage,
            "type": "gateway" if node["emphasis"] == "bottleneck" else "task",
            "status": CONSTRUCTION_EMPHASIS_TO_STATUS.get(node["emphasis"], "waiting"),
            "actor": node["lane"],
            "consulted_authorities": " · ".join(actor_names),
            "action": " ".join(unique_strings(action_parts)),
            "deadline": node.get("deadline") or presentation["deadlines"].get(node["id"], ""),
            "output_documents": unique_strings(output_documents),
            "blocker": " · ".join(
                item["question"] for item in matching_questions if item.get("blocking")
            ),
            "legal_basis": legal_basis,
            "confidence": confidence,
            "confidence_reason": "연결된 법·제도 요구사항 상태: "
            + ", ".join(unique_strings(CONSTRUCTION_STATUS_LABEL.get(x, x) for x in states)),
            "applicability": " · ".join(unique_strings(
                item.get("applicability", "") for item in linked_requirements
            )),
            "report_use": " · ".join(unique_strings(
                item.get("reportUse", "") for item in linked_requirements
            )),
            "open_questions": [
                {
                    "id": item["id"],
                    "blocking": item["blocking"],
                    "question": item["question"],
                    "why": item["whyItMatters"],
                    "evidence": item["evidenceNeeded"],
                    "confirm_with": unique_strings(
                        authorities[ident]["nameKo"] if ident in authorities else ident
                        for ident in item["confirmWith"]
                    ),
                }
                for item in matching_questions
            ],
            "permit_gates": [
                {
                    "order": item["order"],
                    "gate": item["gate"],
                    "decision": item["decision"],
                    "depends_on": item.get("dependsOn", []),
                    "output": item["output"],
                }
                for item in permit_gates
            ],
            "requirement_ids": [item["id"] for item in linked_requirements],
            "question_ids": [item["id"] for item in matching_questions],
            "gate_orders": [item["order"] for item in permit_gates],
        })

    selected_instrument_ids = {
        ref["instrumentId"]
        for node in board["nodes"]
        for ref in node.get("refs", [])
    }
    for ident in selected_requirement_ids:
        selected_instrument_ids.update(
            ref["instrumentId"] for ref in requirements[ident].get("legalBasis", [])
        )
    for item in d.get("reportReadyConclusions", []):
        if item["id"] in selected_conclusion_ids:
            selected_instrument_ids.update(item.get("basis", []))
    for item in d.get("siteOverlays", []):
        if item["id"] in selected_overlay_ids:
            selected_instrument_ids.update(
                ref["instrumentId"] for ref in item.get("legalBasis", [])
            )

    selected_authority_ids = {
        ident for node in board["nodes"] for ident in node.get("authorityIds", [])
    }
    for ident in selected_requirement_ids:
        selected_authority_ids.update(requirements[ident].get("authorityIds", []))
    for ident in selected_question_ids:
        if ident in questions:
            selected_authority_ids.update(questions[ident].get("confirmWith", []))

    verification_sources = []
    legal_basis = []
    for instrument in d["instruments"]:
        if instrument["id"] not in selected_instrument_ids:
            continue
        name = law_name(instrument)
        kind = instrument["kind"]
        if instrument["status"] == "in_force":
            legal_basis.append({
                "law": name,
                "kind": kind,
                "url": instrument.get("officialUrl"),
                "articles": ", ".join(instrument.get("articlesChecked", [])),
            })
        if instrument.get("officialUrl"):
            verification_sources.append({
                "id": instrument["id"],
                "law": name,
                "officialName": instrument["title"],
                "officialUrl": instrument["officialUrl"],
                "kind": kind,
                "articlesChecked": ", ".join(instrument.get("articlesChecked", [])),
                "retrievedOn": d["verification"]["verifiedAt"],
                "status": instrument["status"],
                "verificationLevel": instrument["verificationLevel"],
                "note": instrument.get("note", ""),
            })

    authority_cards = [
        {
            "id": item["id"],
            "name": item["nameKo"],
            "role": item["role"],
            "url": item.get("officialUrl"),
            "verification": item["verificationLevel"],
        }
        for item in d["authorities"]
        if item["id"] in selected_authority_ids
    ]

    submitted_documents = [
        {"actor": f'{item["order"]:02d} {item["gate"]}', "documents": [item["output"]]}
        for item in d["permitPath"]
        if item["order"] in selected_gate_orders
    ]

    blocking_questions = [
        item for item in d["openQuestions"]
        if item.get("blocking") and item["id"] in selected_question_ids
    ]
    bottlenecks = [
        f'{item["question"]} — {item["whyItMatters"]} '
        f'(필요 증빙: {", ".join(item["evidenceNeeded"])})'
        for item in blocking_questions
    ]
    key_findings = [
        {
            "id": item["id"],
            "status": item["confidence"],
            "text": item["text"],
            "basis": [law_name(instruments[ident]) for ident in item.get("basis", []) if ident in instruments],
        }
        for item in d.get("reportReadyConclusions", [])
        if item["id"] in selected_conclusion_ids
    ]
    site_overlays = [
        {
            "id": item["id"],
            "area": item["area"],
            "status": item["status"],
            "rule": item["rule"],
            "missing_evidence": item["missingEvidence"],
            "consequence": item["consequence"],
        }
        for item in d.get("siteOverlays", [])
        if item["id"] in selected_overlay_ids
    ]
    field_verification = [
        f'{item["phase"]}: {item["check"]} → {item["output"]}'
        for item in d["fieldworkChecklist"]
        if item["id"] in selected_checklist_ids
    ]
    field_verification.extend(
        f'{item["id"]} {item["question"]} — 영향: {item["whyItMatters"]}; '
        f'담당 {item["owner"]}; 확인기관 {", ".join(authorities[x]["nameKo"] if x in authorities else x for x in item["confirmWith"])}; '
        f'필요 증빙 {", ".join(item["evidenceNeeded"])}'
        for item in d["openQuestions"]
        if item["id"] in selected_question_ids
    )

    unresolved = []
    for item in d["requirements"]:
        if item["id"] not in selected_requirement_ids:
            continue
        if item["status"] != "unresolved":
            continue
        first_basis = item.get("legalBasis", [{}])[0]
        instrument = instruments.get(first_basis.get("instrumentId"), {})
        unresolved.append({
            "law": law_name(instrument) if instrument else item["topic"],
            "url": instrument.get("officialUrl") if instrument else None,
            "reasonCode": "no-public-text",
            "reason": item["requirement"],
            "nextStep": item["reportUse"] + " 필요 증빙: "
            + ", ".join(item.get("evidenceToObtain", [])),
        })

    notes = list(d["verification"].get("limitations", []))
    if context.get("sourceNote"):
        notes.append(context["sourceNote"])
    application_context = unique_strings([
        context.get("projectName", ""),
        context.get("location", ""),
        context.get("projectType", ""),
        *context.get("known", []),
    ])

    country_key = d["slug"]
    model_slug = (
        model_spec["slug"] if model_spec
        else f"{country_key}-construction-regulations"
    )
    related_construction = [
        item["slug"] for item in d.get("publicModels", [])
        if item["slug"] != model_slug
    ]
    return {
        "schemaVersion": 1,
        "slug": model_slug,
        "countryKey": country_key,
        "name": model_spec["name"] if model_spec else f'{d["country"]["name"]} ODA 건축 인허가·검사·개장',
        "priority": model_spec["priority"] if model_spec else 4,
        "axis": "construction",
        "country": d["country"],
        "asOfDate": d["asOfDate"],
        "oneLiner": model_spec["oneLiner"] if model_spec else board.get("subtitle") or d["purpose"],
        "process": {
            "lanes": board["lanes"],
            "stages": presentation["stages"],
            "nodes": process_nodes,
            "edges": board["edges"],
            "warnings": d["verification"].get("limitations", []),
        },
        "canvas": {
            "purpose": model_spec["purpose"] if model_spec else d["purpose"],
            "stakeholders": ", ".join(
                item["nameKo"] for item in d["authorities"]
                if item["id"] in selected_authority_ids
            ),
            "legalBasis": legal_basis,
            "authorities": authority_cards,
            "procedure": [
                f'{item["order"]}. {item["gate"]} — {item["decision"]} / 산출물: {item["output"]}'
                for item in d["permitPath"]
                if item["order"] in selected_gate_orders
            ],
            "applicability": " · ".join(application_context),
            "submittedDocuments": submitted_documents,
            "bottlenecks": bottlenecks,
            "entryBarriers": [],
            "keyFindings": key_findings,
            "siteOverlays": site_overlays,
        },
        "fieldVerification": unique_strings(field_verification),
        "related": [
            f"{country_key}-bidding-system",
            f"{country_key}-procurement-governance",
            f"{country_key}-oda-project-pipeline",
            *related_construction,
        ],
        "sourceQuotes": [],
        "verification": {
            "status": d["verification"]["status"],
            "verifiedAt": d["verification"]["verifiedAt"],
            "method": d["verification"]["method"],
            "scope": model_spec.get("verificationScope", d["verification"]["scope"])
            if model_spec else d["verification"]["scope"],
            "sources": verification_sources,
            "notes": notes,
            "unresolved": unresolved,
            "discrepancies": [],
        },
    }


def construction_to_models(d: dict) -> list[dict]:
    """국가 원천 하나를 공개 제도축 1개 이상으로 변환한다."""
    specs = d.get("publicModels")
    if not specs:
        return [construction_to_model(d)]
    return [construction_to_model(d, spec) for spec in specs]


# 본문에 그대로 적힌 주소(포털·기관 사이트)도 눌러서 열 수 있어야 한다.
# 슬래시나 스킴이 붙은 것만 잡아 조문 표기·약어를 주소로 오인하지 않는다.
_URL_RE = re.compile(
    r'(https?://[^\s<>&,)]+|(?<![\w.])(?:[a-z0-9-]+\.)+(?:gov|go|org|com)\.(?:np|kr)(?:/[^\s<>&,)]*)?)'
)


def _href(u: str) -> str:
    return u if u.startswith("http") else "https://" + u


def el(s) -> str:
    """escape + 본문 URL 자동 링크."""
    return _URL_RE.sub(
        lambda m: f'<a class="ref" href="{_href(m.group(0))}" target="_blank" rel="noopener">{m.group(0)}</a>',
        e(s),
    )


def link(label: str, url: str | None, *, cls: str = "ref") -> str:
    """url이 있을 때만 링크로, 없으면 평문으로. 근거 없는 링크를 만들지 않기 위한 관문."""
    if not url:
        return label
    return f'<a class="{cls}" href="{e(url)}" target="_blank" rel="noopener">{label}</a>'


def source_urls(d: dict) -> dict:
    """verification.sources를 법령명 → 원문 URL 사전으로. 링크의 단일 출처."""
    m = {}
    for s in d["verification"].get("sources", []):
        m[s["law"]] = s["officialUrl"]
        if s.get("officialName"):
            m.setdefault(s["officialName"], s["officialUrl"])
    return m


def cite_link(d: dict, text: str) -> str:
    """근거 표기 안의 법령명을 원문 URL로 건다. 긴 이름부터 치환해 부분 겹침을 피한다."""
    esc = e(text)
    holders = {}
    for i, (law, url) in enumerate(sorted(source_urls(d).items(), key=lambda kv: -len(kv[0]))):
        lw = e(law)
        if lw in esc:
            key = f"\x00{i}\x00"
            holders[key] = f'<a class="ref" href="{e(url)}" target="_blank" rel="noopener">{lw}</a>'
            esc = esc.replace(lw, key, 1)
    for k, val in holders.items():
        esc = esc.replace(k, val)
    return esc


FIELDCHECK_LABEL = {
    "confirmed": ("사무소 확인됨", "ok"),
    "refuted": ("사무소 반증 — 우리 판단 오류", "bad"),
    "partial": ("사무소 부분 확인", "warn"),
    "pending": ("사무소 확인 중", "muted"),
}


def _fieldcheck_html(fc: dict | None) -> str:
    """사무소 검증 결과 — 회신이 반영되면 카드에 표시된다."""
    if not fc:
        return ""
    label, tone = FIELDCHECK_LABEL.get(fc["status"], (fc["status"], "muted"))
    ev = (f' · <a class="ref" href="{e(fc["evidenceUrl"])}" target="_blank" rel="noopener">근거</a>'
          if fc.get("evidenceUrl") else "")
    return f"""<div class="fieldcheck">
  <div class="fc-hd"><span class="badge {tone}">{e(label)}</span>
    <span class="badge plain muted">{e(fc['checkedBy'])} · {e(fc['checkedOn'])}</span></div>
  <p class="fc-find">{el(fc['finding'])}{ev}</p>
</div>"""


def _review_html(rv: dict | None) -> str:
    """현행 기준 카드 안의 현지 직원용 영어 확인 접기."""
    if not rv:
        return ""
    return f"""<details class="review">
  <summary>Field verification (English)</summary>
  <div class="rv">
    <p><b>Current legal basis</b> — {e(rv['lawSays'])}</p>
    <p class="rv-verify"><b>✔ Verify</b> — {e(rv['verify'])}</p>
  </div>
</details>"""


def disc_card(d: dict, x: dict, *, link: str = "") -> str:
    """현행 기준 반영 카드 하나. 상세·검증대장에서 공통으로 쓴다."""
    head_link = (f'<a class="badge plain muted" style="text-decoration:none" href="{link}">'
                 f'{e(d["name"])} →</a>' if link else
                 f'<span class="badge plain muted">{e(x["id"].rsplit("-", 1)[-1])}</span>')

    return f"""<div class="disc" data-sev="{e(x['severity'])}">
  <div class="top">
    <span class="badge {SEV_TONE[x['severity']]}">{e(SEV_LABEL[x['severity']])}</span>
    <span class="badge plain muted">{e(d['country']['name'])}</span>
    {head_link}
  </div>
  <h3>{e(x['field'])}</h3>
  <div class="quote act"><b>현행 기준</b>{el(x['actualText'])}</div>
  <p class="cite">확인 출처 · {cite_link(d, x['citation'])}</p>
  <div class="todo"><b>실무 확인</b>{el(x['userAction'])}</div>
  {_review_html(x.get('review'))}
  {_fieldcheck_html(x.get('fieldCheck'))}
  <p class="act-row">산출물 반영 — {el(x['action'])}</p>
</div>"""


# ─────────────────────────────────────────────────────────── CSS

CSS = """
*,*::before,*::after{box-sizing:border-box}
html,body{overflow-x:hidden}
:root{
  --bg:#fff; --fg:#16181d; --muted:#6b7280; --line:#e5e7eb; --soft:#f7f8fa;
  --key:#157f3d; --key-bg:#eaf5ee; --warn:#b45309; --warn-bg:#fdf5e7;
  --back:#1d4ed8; --back-bg:#eef2ff; --bad:#b91c1c; --bad-bg:#fdeced;
  --info:#0369a1; --info-bg:#e8f4fb;
  --font:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Pretendard","Noto Sans KR",sans-serif;
}
@media (prefers-color-scheme:dark){
  :root{
    --bg:#0f1115; --fg:#e8eaed; --muted:#9aa3af; --line:#272c36; --soft:#161a21;
    --key:#4ade80; --key-bg:#12261a; --warn:#fbbf24; --warn-bg:#2a2113;
    --back:#93b4fd; --back-bg:#161d33; --bad:#fca5a5; --bad-bg:#2b1618;
    --info:#7dd3fc; --info-bg:#10222e;
  }
}
:root[data-theme="dark"]{
  --bg:#0f1115; --fg:#e8eaed; --muted:#9aa3af; --line:#272c36; --soft:#161a21;
  --key:#4ade80; --key-bg:#12261a; --warn:#fbbf24; --warn-bg:#2a2113;
  --back:#93b4fd; --back-bg:#161d33; --bad:#fca5a5; --bad-bg:#2b1618;
  --info:#7dd3fc; --info-bg:#10222e;
}
:root[data-theme="light"]{
  --bg:#fff; --fg:#16181d; --muted:#6b7280; --line:#e5e7eb; --soft:#f7f8fa;
  --key:#157f3d; --key-bg:#eaf5ee; --warn:#b45309; --warn-bg:#fdf5e7;
  --back:#1d4ed8; --back-bg:#eef2ff; --bad:#b91c1c; --bad-bg:#fdeced;
  --info:#0369a1; --info-bg:#e8f4fb;
}
body{margin:0;background:var(--bg);color:var(--fg);font-family:var(--font);
  font-size:15px;line-height:1.65;-webkit-font-smoothing:antialiased}
a{color:inherit}
/* 원문·공식 사이트로 나가는 링크. 화살표로 외부 이동임을 알린다. */
a.ref{color:var(--info);text-decoration:none;border-bottom:1px solid transparent}
a.ref:hover{border-bottom-color:currentColor}
a.ref::after{content:"↗";font-size:.78em;margin-left:2px;opacity:.65;vertical-align:1px}
.wrap{max-width:1180px;margin:0 auto;padding:0 24px}

header.site{border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--bg);z-index:50}
header.site .wrap{display:flex;align-items:center;gap:14px;height:58px}
.brand{font-weight:800;letter-spacing:-.02em;text-decoration:none;font-size:16px}
.brand-sub{color:var(--muted);font-size:12.5px}
header.site nav{margin-left:auto;display:flex;align-items:center;gap:18px;font-size:13.5px}
header.site nav a{color:var(--muted);text-decoration:none}
header.site nav a:hover,header.site nav a[aria-current]{color:var(--fg)}
.asof{color:var(--muted);font-size:12px}
@media (max-width:760px){
  header.site .wrap{height:auto;min-height:58px;flex-wrap:wrap;padding-block:10px;gap:5px 12px}
  .brand-sub{display:none}
  header.site nav{width:100%;margin-left:0;gap:14px;overflow-x:auto;padding:2px 0 4px}
  header.site nav a{white-space:nowrap}
}
.hero{padding:44px 0 30px}
.eyebrow{display:flex;align-items:center;gap:10px;color:var(--key);font-weight:700;font-size:12.5px;letter-spacing:.02em}
.eyebrow::before{content:"";width:26px;height:2px;background:var(--key)}
h1{font-size:clamp(28px,4.2vw,44px);letter-spacing:-.035em;margin:14px 0 12px;font-weight:800}
.lede{font-size:clamp(15px,1.7vw,18px);color:var(--fg);max-width:70ch;margin:0;font-weight:600;letter-spacing:-.01em}
.lede + .lede{margin-top:4px}
.meta{color:var(--muted);font-size:13px;margin-top:14px}

.statbar{border-top:1px solid var(--line);border-bottom:1px solid var(--line);background:var(--soft)}
.statbar .wrap{display:flex;gap:16px;align-items:center;padding-block:16px;flex-wrap:wrap}
.stats{display:flex;gap:26px;margin-left:auto;flex-wrap:wrap}
.stat b{display:block;font-size:22px;font-weight:800;letter-spacing:-.02em;line-height:1.2}
.stat span{font-size:11.5px;color:var(--muted)}
.stat.ok b{color:var(--key)} .stat.bad b{color:var(--bad)}
.search{flex:1;min-width:260px;display:flex;align-items:center;gap:10px;background:var(--bg);
  border:1px solid var(--line);border-radius:8px;padding:8px 12px}
.search label{font-size:12px;color:var(--muted);white-space:nowrap;padding-right:10px;border-right:1px solid var(--line)}
.search input{flex:1;border:0;background:transparent;color:inherit;font:inherit;outline:none}
.search .count{font-size:12px;color:var(--muted);white-space:nowrap}

.cols{display:grid;grid-template-columns:220px 1fr;gap:28px;padding:26px 0 60px;align-items:start}
@media (max-width:820px){.cols{grid-template-columns:1fr}}
.side h3{font-size:12px;color:var(--muted);margin:0 0 10px;font-weight:700;letter-spacing:.02em}
.side button{display:flex;width:100%;align-items:center;gap:9px;background:none;border:0;color:inherit;
  font:inherit;padding:7px 10px;border-radius:7px;cursor:pointer;text-align:left}
.side button:hover{background:var(--soft)}
.side button[aria-pressed="true"]{background:var(--key-bg);font-weight:700}
.side .dot{width:8px;height:8px;border-radius:50%;background:var(--muted);flex:none}
.side .n{margin-left:auto;color:var(--muted);font-size:12.5px}
.side .grp{margin-bottom:22px}

.panel{border:1px solid var(--line);border-radius:12px;overflow:hidden}
.panel-hd{padding:14px 18px;border-bottom:1px solid var(--line);font-weight:700;font-size:14px}
.panel-hd span{color:var(--muted);font-weight:500}
table{width:100%;border-collapse:collapse;font-size:14px}
th{text-align:left;font-size:11.5px;color:var(--muted);font-weight:600;padding:10px 14px;border-bottom:1px solid var(--line)}
td{padding:13px 14px;border-bottom:1px solid var(--line);vertical-align:top}
tbody tr:last-child td{border-bottom:0}
tbody tr:hover{background:var(--soft)}
td.no{color:var(--muted);font-size:12px;font-variant-numeric:tabular-nums;width:44px}
td.name a{font-weight:700;text-decoration:none;letter-spacing:-.01em}
td.name a:hover{text-decoration:underline}
td.name p{margin:3px 0 0;color:var(--muted);font-size:12.5px;line-height:1.5;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.empty{padding:40px 16px;text-align:center;color:var(--muted);font-size:14px}

.badge{display:inline-flex;align-items:center;gap:5px;font-size:11.5px;font-weight:700;
  padding:3px 9px;border-radius:999px;background:var(--soft);color:var(--muted);white-space:nowrap}
.badge::before{content:"";width:6px;height:6px;border-radius:50%;background:currentColor}
.badge.plain::before{display:none}
.badge.ok{background:var(--key-bg);color:var(--key)}
.badge.info{background:var(--info-bg);color:var(--info)}
.badge.warn{background:var(--warn-bg);color:var(--warn)}
.badge.bad{background:var(--bad-bg);color:var(--bad)}
.badge.muted{background:var(--soft);color:var(--muted)}

.subnav{border-bottom:1px solid var(--line);background:var(--soft)}
.subnav .wrap{display:flex;align-items:center;gap:12px;padding-block:12px;flex-wrap:wrap}
.subnav label{font-size:12px;color:var(--muted)}
select,.btn{font:inherit;font-size:13.5px;color:inherit;background:var(--bg);
  border:1px solid var(--line);border-radius:8px;padding:7px 12px;cursor:pointer}
.btn:hover{background:var(--soft)}
.btn[disabled]{opacity:.4;cursor:default}
.pos{color:var(--muted);font-size:12.5px;font-variant-numeric:tabular-nums}

.dtl-hd{padding:26px 0 20px}
.dtl-hd .row{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.dtl-hd h1{font-size:clamp(24px,3.4vw,36px);margin:12px 0 8px}
.dtl-hd .one{color:var(--muted);font-size:15.5px;max-width:78ch;margin:0}
.tiles{display:flex;gap:0;border:1px solid var(--line);border-radius:12px;overflow:hidden;
  margin-top:22px;width:fit-content;max-width:100%;flex-wrap:wrap}
.tile{padding:14px 22px;border-right:1px solid var(--line);min-width:104px}
.tile:last-child{border-right:0}
.tile b{display:block;font-size:21px;font-weight:800;letter-spacing:-.02em;line-height:1.25}
.tile span{font-size:11.5px;color:var(--muted)}
.tile.ok b{color:var(--key)} .tile.warn b{color:var(--warn)} .tile.bad b{color:var(--bad)}

section.blk{padding:34px 0;border-top:1px solid var(--line)}
section.blk > h2{font-size:21px;letter-spacing:-.02em;margin:0 0 6px;font-weight:800}
section.blk > .desc{color:var(--muted);font-size:13.5px;margin:0 0 20px}
.legend{display:flex;gap:16px;font-size:12px;color:var(--muted);flex-wrap:wrap}
.legend i{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px;vertical-align:-1px}
.hd-row{display:flex;align-items:flex-end;gap:16px;flex-wrap:wrap;margin-bottom:18px}
.hd-row .legend{margin-left:auto}

.boardwrap{position:relative;border:1px solid var(--line);border-radius:12px;overflow:auto;
  -webkit-overflow-scrolling:touch;overscroll-behavior-inline:contain}
.board{position:relative;min-width:940px}
.board svg.edges{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:1}
.brow{display:grid;border-bottom:1px solid var(--line)}
.brow:last-child{border-bottom:0}
.brow.head{background:var(--soft);position:sticky;top:0;z-index:3}
/* gap은 같은 셀에 세로로 쌓인 노드 사이로 화살표가 지나갈 통로다. 좁히면 화살촉이 뭉갠다. */
.bcell{padding:14px 12px;border-right:1px solid var(--line);min-height:64px;
  display:flex;flex-direction:column;gap:26px;justify-content:center}
.bcell:last-child{border-right:0}
.brow .bcell:first-child{position:sticky;left:0;z-index:3;background:var(--bg);box-shadow:1px 0 0 var(--line)}
.brow.head .bcell:first-child{z-index:5;background:var(--soft)}
.brow.head .bcell{min-height:0;padding:11px 12px;justify-content:flex-start}
.stage-k{font-weight:800;font-size:12px;color:var(--key);letter-spacing:.02em}
.stage-t{font-size:13px;font-weight:700}
.lane-t{font-size:13px;font-weight:700;color:var(--muted)}
.node{position:relative;z-index:2;background:var(--bg);border:1px solid var(--line);
  border-radius:9px;padding:10px 12px;cursor:pointer;text-align:left;font:inherit;color:inherit;
  width:100%;display:block;transition:box-shadow .12s,border-color .12s}
.node:hover{border-color:var(--muted);box-shadow:0 2px 10px rgba(0,0,0,.07)}
.node:focus-visible{outline:3px solid color-mix(in srgb,var(--key) 35%,transparent);outline-offset:2px}
.node .id{font-size:10.5px;color:var(--muted);font-weight:700;letter-spacing:.04em;
  display:flex;justify-content:space-between;align-items:center;gap:8px}
.node .nm{font-size:13px;font-weight:700;margin-top:3px;letter-spacing:-.01em;line-height:1.4}
.node .tag{font-size:10px;font-weight:700;padding:1px 6px;border-radius:999px}
.node[data-tone="key"]{border-color:var(--key);background:var(--key-bg)}
.node[data-tone="key"] .tag{background:var(--key);color:var(--bg)}
.node[data-tone="warn"]{border-color:var(--warn);background:var(--warn-bg)}
.node[data-tone="warn"] .tag{background:var(--warn);color:var(--bg)}
.node[data-tone="back"]{border-color:var(--back);background:var(--back-bg)}
.node[data-tone="back"] .tag{background:var(--back);color:var(--bg)}
.node.dim{opacity:.34}

.drawer{position:fixed;inset:0;z-index:100;display:none;width:100vw;height:100vh;
  max-width:100vw;max-height:100vh;margin:0;padding:0;border:0;background:transparent;overflow:hidden}
.drawer[open]{display:block}
.drawer::backdrop{background:rgba(0,0,0,.34)}
.drawer .pane{position:absolute;right:0;top:0;bottom:0;width:min(440px,92vw);background:var(--bg);
  border-left:1px solid var(--line);padding:24px;overflow:auto}
.drawer h3{margin:10px 0 4px;font-size:19px;letter-spacing:-.02em}
.drawer .close{position:absolute;right:18px;top:18px;background:none;border:0;color:var(--muted);
  font-size:22px;cursor:pointer;line-height:1;padding:4px}
.kv{margin:18px 0 0;font-size:13.5px}
.kv dt{font-size:11.5px;color:var(--muted);font-weight:700;margin-top:14px}
.kv dd{margin:3px 0 0}
.kv code{font-size:12.5px;background:var(--soft);padding:1px 6px;border-radius:4px}

.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:16px}
.card{border:1px solid var(--line);border-radius:11px;padding:17px 19px}
.card h3{margin:0 0 11px;font-size:13.5px;letter-spacing:.01em}
.card.span2{grid-column:span 2}
@media (max-width:820px){.card.span2{grid-column:span 1}}
ol.steps{margin:0;padding-left:20px;font-size:13.5px;line-height:1.75}
ol.steps li{margin-bottom:5px}
ul.plain{margin:0;padding-left:18px;font-size:13.5px;line-height:1.7}
ul.plain li{margin-bottom:6px}
.law{display:flex;gap:9px;align-items:baseline;padding:8px 0;border-bottom:1px dashed var(--line);font-size:13.5px}
.law:last-child{border-bottom:0}
.law .nm{font-weight:600}
.law .ar{color:var(--muted);font-size:12.5px}
.docset{margin-bottom:13px}
.docset b{font-size:12.5px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
.chip{font-size:12px;background:var(--soft);border:1px solid var(--line);border-radius:6px;padding:3px 8px}
.auth{display:flex;gap:10px;padding:9px 0;border-bottom:1px dashed var(--line);font-size:13.5px}
.auth:last-child{border-bottom:0}
.auth b{flex:none;max-width:42%;font-size:13px}
.auth span{color:var(--muted);font-size:12.5px}

.disc{border:1px solid var(--line);border-left-width:4px;border-radius:10px;padding:17px 19px;margin-bottom:15px}
.disc[data-sev="high"]{border-left-color:var(--bad)}
.disc[data-sev="medium"]{border-left-color:var(--warn)}
.disc[data-sev="low"]{border-left-color:var(--muted)}
.disc .top{display:flex;gap:9px;align-items:center;flex-wrap:wrap;margin-bottom:9px}
.disc .top .badge{white-space:normal;max-width:100%;overflow-wrap:anywhere}
.disc h3{margin:0;font-size:14.5px;letter-spacing:-.01em}
.disc .quote{font-size:13px;margin:9px 0;padding:10px 13px;border-radius:8px;background:var(--soft);line-height:1.65}
.disc .quote b{display:block;font-size:11px;color:var(--muted);margin-bottom:4px;letter-spacing:.02em}
.disc .quote.src{border-left:2px solid var(--muted)}
.disc .quote.act{border-left:2px solid var(--key)}
.disc .cite{font-size:12px;color:var(--muted);margin:8px 0 0}
.disc .impact{font-size:13.5px;margin:11px 0 0;line-height:1.7}
.disc .act-row{font-size:13px;margin:11px 0 0;padding-top:11px;border-top:1px dashed var(--line);color:var(--muted)}
.review{margin:11px 0 0;border:1px solid var(--info);border-radius:8px;background:var(--info-bg)}
.review summary{cursor:pointer;padding:9px 13px;font-size:12px;font-weight:700;color:var(--info);list-style:none}
.review summary::-webkit-details-marker{display:none}
.review summary::before{content:"▸ ";font-size:10px}
.review[open] summary::before{content:"▾ "}
.review .rv{padding:2px 13px 13px}
.review .rv p{font-size:13px;line-height:1.65;margin:8px 0 0}
.review .rv-topic{font-weight:700;font-size:13.5px}
.review .rv-verify{padding:9px 11px;border-radius:6px;background:var(--bg);border:1px dashed var(--info)}
.fieldcheck{margin:11px 0 0;padding:11px 13px;border-radius:8px;background:var(--soft);border:1px solid var(--line)}
.fieldcheck .fc-hd{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:6px}
.fieldcheck .fc-find{font-size:13px;line-height:1.7;margin:0}
.todo{margin:13px 0 0;padding:12px 14px;border-radius:9px;background:var(--key-bg);
  border:1px solid var(--key);font-size:13.5px;line-height:1.7}
.todo b{display:block;font-size:11px;color:var(--key);letter-spacing:.03em;margin-bottom:4px}
.up{margin:11px 0 0;padding:12px 14px;border-radius:9px;background:var(--soft);border:1px solid var(--line)}
.up .hd{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin-bottom:7px}
.up .hd b{font-size:11px;color:var(--muted);letter-spacing:.03em}
.up .txt{font-size:13px;line-height:1.7;padding:9px 12px;border-radius:7px;background:var(--bg);
  border:1px dashed var(--line)}
.up .txt i{display:block;font-style:normal;font-size:10.5px;color:var(--muted);margin-bottom:3px}

.quotes{display:flex;flex-direction:column;gap:14px}
.qc{border:1px solid var(--line);border-left:3px solid var(--info);border-radius:9px;padding:15px 17px}
.qc .qhd{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:9px}
.qc .qart{font-weight:700;font-size:13px}
.qc .qtext{font-family:ui-monospace,"SF Mono",Menlo,monospace;font-size:12.5px;line-height:1.7;
  background:var(--soft);border-radius:7px;padding:11px 13px;white-space:pre-wrap;word-break:break-word}
.qc .qgist{font-size:13.5px;line-height:1.7;margin:10px 0 0}
.qc details{margin:8px 0 0}
.qc summary{font-size:12px;color:var(--muted);cursor:pointer;list-style:none}
.qc summary::-webkit-details-marker{display:none}
.qc summary::before{content:"▸ ";font-size:10px}
.qc details[open] summary::before{content:"▾ "}
.qc .qko{font-size:13px;line-height:1.7;color:var(--muted);margin:7px 0 0;padding-left:12px;border-left:1px solid var(--line)}
.srcs{font-size:13.5px}
.srcs li{margin-bottom:9px}
.srcs a{color:var(--info)}
.srcs .ar{display:block;color:var(--muted);font-size:12px;margin-top:1px}
.note{font-size:13.5px;line-height:1.7;color:var(--muted);margin:0 0 8px;padding-left:15px;position:relative}
.note::before{content:"·";position:absolute;left:4px}

.feature-callout{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:16px;align-items:center;
  margin:0 0 24px;padding:20px 22px;border:1px solid var(--key);border-radius:12px;
  background:var(--key-bg);text-decoration:none}
.feature-callout:hover{box-shadow:0 4px 18px rgba(0,0,0,.08)}
.feature-callout b{display:block;font-size:17px;letter-spacing:-.02em;margin-bottom:3px}
.feature-callout p{margin:0;color:var(--muted);font-size:13.5px}
.feature-callout .go{color:var(--key);font-weight:800;font-size:13px;white-space:nowrap}
@media (max-width:620px){.feature-callout{grid-template-columns:1fr}.feature-callout .go{margin-top:2px}}

.country-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}
.country-card{border:1px solid var(--line);border-radius:13px;padding:21px;background:var(--bg)}
.country-card .top{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.country-card h2{font-size:20px;margin:13px 0 5px;letter-spacing:-.02em}
.country-card p{font-size:13.5px;color:var(--muted);line-height:1.7;margin:0}
.country-card .metrics{display:flex;gap:16px;flex-wrap:wrap;margin:17px 0}
.country-card .metrics b{display:block;font-size:18px;line-height:1.2}
.country-card .metrics span{font-size:11px;color:var(--muted)}
.country-card .btn{display:inline-flex;text-decoration:none;color:var(--key);font-weight:700}
.studio-preview{margin:18px 0;border:1px solid var(--line);border-radius:10px;overflow:hidden;background:#fff}
.studio-preview .viewport{height:330px;overflow:hidden;position:relative}
.studio-preview .viewport::after{content:"";position:absolute;inset:auto 0 0;height:80px;
  background:linear-gradient(transparent,#fff);pointer-events:none}
.studio-preview img{display:block;width:100%;min-width:720px;height:auto}
.studio-preview .caption{display:flex;justify-content:space-between;gap:12px;align-items:center;
  padding:10px 12px;border-top:1px solid var(--line);color:#3d4048;font-size:11.5px}
.studio-preview .caption b{font-size:12px;color:#191b20}
.studio-board-shell{border:1px solid var(--line);border-radius:12px;overflow:hidden;background:#fff}
.studio-board-view{overflow:auto;background:#fff}
.studio-board-view img{display:block;width:100%;min-width:1120px;height:auto}
.studio-board-shell figcaption{display:flex;justify-content:space-between;gap:12px;align-items:center;
  flex-wrap:wrap;margin:0;padding:11px 14px;border-top:1px solid #d9dbe1;color:#51545d;font-size:12px}
.studio-board-shell figcaption a{color:#3157a4}
@media (max-width:760px){
  .studio-preview .viewport{height:280px}.studio-preview img{min-width:660px}
  .studio-board-view img{min-width:980px}
}

.decision-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:13px}
.decision{border:1px solid var(--line);border-left-width:4px;border-radius:10px;padding:16px 17px}
.decision[data-state="confirmed"]{border-left-color:var(--key)}
.decision[data-state="conditional"]{border-left-color:var(--warn)}
.decision[data-state="unresolved"]{border-left-color:var(--bad)}
.decision p{font-size:13.5px;line-height:1.72;margin:9px 0 0}
.decision .sources{font-size:11.5px;color:var(--muted);margin-top:10px}

.gateflow{counter-reset:gate;display:grid;gap:0;border:1px solid var(--line);border-radius:12px;overflow:hidden}
.gate-step{display:grid;grid-template-columns:42px minmax(150px,.55fr) minmax(260px,1fr) minmax(150px,.55fr);
  gap:14px;align-items:start;padding:15px 17px;border-bottom:1px solid var(--line)}
.gate-step:last-child{border-bottom:0}
.gate-step::before{counter-increment:gate;content:counter(gate);width:28px;height:28px;border-radius:50%;
  display:grid;place-items:center;background:var(--key-bg);color:var(--key);font-weight:800;font-size:12px}
.gate-step b{font-size:13.5px}.gate-step p{font-size:13px;margin:0;color:var(--muted);line-height:1.65}
.gate-step .out{font-size:12px;color:var(--fg);padding-left:12px;border-left:1px solid var(--line)}
@media (max-width:760px){
  .gate-step{grid-template-columns:34px 1fr;gap:6px 10px}
  .gate-step p,.gate-step .out{grid-column:2}.gate-step .out{padding:7px 0 0;border-left:0;border-top:1px dashed var(--line)}
}

.blocker-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:13px}
.blocker{border:1px solid var(--bad);border-radius:10px;padding:16px 17px;background:var(--bad-bg)}
.blocker .stage{color:var(--bad);font-size:11px;font-weight:800;letter-spacing:.03em}
.blocker h3{font-size:14.5px;line-height:1.55;margin:7px 0 10px}
.blocker p{font-size:12.5px;color:var(--muted);line-height:1.65;margin:0}
.blocker ul{font-size:12.5px;margin:9px 0 0;padding-left:18px}

.req-groups{display:flex;flex-direction:column;gap:11px}
.req-group{border:1px solid var(--line);border-radius:10px;overflow:hidden;background:var(--bg)}
.req-group summary{cursor:pointer;list-style:none;padding:14px 17px;font-weight:800;font-size:14px;background:var(--soft)}
.req-group summary::-webkit-details-marker{display:none}
.req-group summary::after{content:"＋";float:right;color:var(--muted)}
.req-group[open] summary::after{content:"－"}
.req-items{padding:4px 17px}
.req-item{padding:16px 0;border-bottom:1px dashed var(--line)}
.req-item:last-child{border-bottom:0}
.req-item .top{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:8px}
.req-item h3{font-size:14px;margin:0}
.req-item p{font-size:13px;line-height:1.7;margin:5px 0}
.req-item .minor{color:var(--muted);font-size:12.5px}

.overlay-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:13px}
.overlay{border:1px solid var(--line);border-radius:10px;padding:16px 17px}
.overlay h3{font-size:14px;margin:10px 0 7px}.overlay p{font-size:13px;line-height:1.7;margin:5px 0}
.overlay .missing{color:var(--bad)}

.anchor-row{display:flex;gap:7px;flex-wrap:wrap;margin:18px 0 0}
.anchor-row a{font-size:12px;text-decoration:none;border:1px solid var(--line);border-radius:999px;padding:5px 10px;background:var(--bg)}
.anchor-row a:hover{border-color:var(--key);color:var(--key)}
.data-table-wrap{overflow-x:auto;border:1px solid var(--line);border-radius:12px}
.data-table-wrap table{min-width:780px}

@media (max-width:360px){
  .wrap{padding-inline:16px}
  .cards,.decision-list,.overlay-grid,.blocker-grid,.country-cards{grid-template-columns:minmax(0,1fr)}
  .card,.decision,.overlay,.blocker,.country-card{min-width:0}
  .subnav select{max-width:100%}
}

footer.site{border-top:1px solid var(--line);padding:28px 0 46px;color:var(--muted);font-size:12.5px;line-height:1.8}
footer.site a{color:var(--muted)}
"""

JS_THEME = """
(function(){
  var t=localStorage.getItem('theme');
  if(t) document.documentElement.setAttribute('data-theme',t);
  window.__toggleTheme=function(){
    var cur=document.documentElement.getAttribute('data-theme');
    if(!cur) cur=matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light';
    var nx=cur==='dark'?'light':'dark';
    document.documentElement.setAttribute('data-theme',nx);
    localStorage.setItem('theme',nx);
  };
})();
"""


def page(title: str, body: str, *, depth: int = 0, nav: str = "", extra_js: str = "",
         standalone: bool = False) -> str:
    up = "../" * depth if depth else ""
    # standalone(배포용 단독 파일)은 사이트 내부로 나가는 메뉴를 없앤다 — 받는 사람에게
    # 다른 파일이 없으므로 깨질 링크를 애초에 두지 않는다. 테마 토글만 남긴다.
    header = f"""<header class="site"><div class="wrap" style="justify-content:flex-end;min-height:0;height:auto;padding-block:6px">
  <button class="btn" style="padding:4px 10px;font-size:12px" onclick="__toggleTheme()">테마</button>
</div></header>""" if standalone else f"""<header class="site"><div class="wrap">
  <a class="brand" href="{up}index.html">{e(SITE_TITLE)}</a>
  <span class="brand-sub">{e(SITE_SUB)}</span>
  <nav>
    <a href="{up}index.html"{' aria-current="page"' if nav == "list" else ''}>제도 대장</a>
    <a href="{up}verification/index.html"{' aria-current="page"' if nav == "verify" else ''}>검증 대장</a>
    <a href="{up}errata/index.html"{' aria-current="page"' if nav == "errata" else ''}>반영 출처</a>
    <button class="btn" style="padding:4px 10px;font-size:12px" onclick="__toggleTheme()">테마</button>
  </nav>
</div></header>"""
    return f"""<!doctype html>
<html lang="ko"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title>
<style>{CSS}</style>
<script>{JS_THEME}</script>
</head><body>
{header}
{body}
<footer class="site"><div class="wrap">
  국가별 조달·ODA 건축 법제의 기준일 현재 참고자료입니다. 법률 자문이나 해당국 정부·KOICA의 공식 해석이 아닙니다.<br>
  실제 입찰·설계·인허가 전에는 발주처 공고문, 관할기관 판단과 현행 법령을 다시 확인해야 합니다.<br>
  1차 출처 KOICA 2026 국가별 개발협력사업 참여전략 자료집 및 각국 정부 공식 법령·관보<br>
  제도 추가·정정 제안 · Threads <a href="https://www.threads.net/@amnotyoung.k" target="_blank" rel="me noopener noreferrer">@amnotyoung.k</a>
</div></footer>
{f'<script>{extra_js}</script>' if extra_js else ''}
</body></html>"""


def redirect_page(target: str, title: str) -> str:
    """과거 공개 URL을 통합 model 경로로 보내는 작은 호환 페이지."""
    target_js = script_json(target)
    return f"""<!doctype html>
<html lang="ko"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="0;url={e(target)}">
<link rel="canonical" href="{e(target)}">
<title>{e(title)}</title>
</head><body>
<p>국가별 통합 제도 페이지로 이동했습니다. <a href="{e(target)}">계속하기</a></p>
<script>location.replace({target_js}+location.hash);</script>
</body></html>"""


# ─────────────────────────────────────────────────────────── 목록

def build_index(items: list[dict]) -> str:
    countries: dict[str, int] = {}
    axes: dict[str, int] = {}
    for d in items:
        countries[d["country"]["name"]] = countries.get(d["country"]["name"], 0) + 1
        axes[d["axis"]] = axes.get(d["axis"], 0) + 1

    nodes = sum(len(d.get("process", {}).get("nodes", [])) for d in items)
    discs = sum(len(d["verification"].get("discrepancies", [])) for d in items)
    verified = sum(1 for d in items if d["verification"]["status"] == "article-verified")
    asof = max(d["asOfDate"] for d in items)
    procurement_count = sum(1 for d in items if d["axis"] != "construction")
    construction_count = sum(1 for d in items if d["axis"] == "construction")

    rows = []
    for d in items:
        v = d["verification"]["status"]
        nd = len(d["verification"].get("discrepancies", []))
        hi = sum(1 for x in d["verification"].get("discrepancies", []) if x["severity"] == "high")
        disc_badge = (
            f'<span class="badge {"bad" if hi else "warn"}">확인사항 {nd}</span>' if nd else
            '<span class="badge muted plain">—</span>'
        )
        rows.append(f"""<tr data-c="{e(d['country']['name'])}" data-a="{e(d['axis'])}"
  data-s="{e((d['name'] + ' ' + d['oneLiner'] + ' ' + d['country']['nameEn']).lower())}">
  <td class="no">{d['priority']:02d}</td>
  <td class="name"><a href="model/{e(d['slug'])}/index.html">{e(d['name'])}</a>
    <p>{e(d['oneLiner'])}</p></td>
  <td><span class="badge plain muted">{e(d['country']['name'])}</span></td>
  <td style="font-size:13px;color:var(--muted)">{e(AXIS_LABEL[d['axis']])}</td>
  <td><span class="badge {VERIF_TONE[v]}">{e(VERIF_LABEL[v])}</span></td>
  <td>{disc_badge}</td>
</tr>""")

    side_c = "".join(
        f'<button aria-pressed="false" data-f="c" data-v="{e(k)}"><i class="dot"></i>{e(country_display_name(k))}<span class="n">{n}</span></button>'
        for k, n in sorted(countries.items(), key=lambda x: country_name_sort_key(x[0]))
    )
    side_a = "".join(
        f'<button aria-pressed="false" data-f="a" data-v="{e(k)}"><i class="dot"></i>{e(AXIS_LABEL[k])}<span class="n">{n}</span></button>'
        for k, n in axes.items())

    body = f"""
<div class="wrap hero">
  <div class="eyebrow">조달 절차와 건축 법·제도</div>
  <h1>{e(SITE_TITLE)}</h1>
  <p class="lede">협력국에서 처음 조달하거나 건축사업을 준비할 때, 어디서부터 확인해야 할까요?</p>
  <p class="lede">입찰·사업형성 절차와 건축 법·제도를 담당기관·서류·기한·인허가가 보이는 실행 경로로 정리하고, 근거는 각국 공식 원문까지 대조했습니다.</p>
  <p class="meta">조달 제도 {procurement_count}개 · 건축 제도 {construction_count}개 · 전체 {len(items)}개 제도 · 조문 대조 완료 {verified}개 · 기준일 {e(asof)}</p>
</div>

<div class="statbar"><div class="wrap">
  <div class="search">
    <label for="q">검 색</label>
    <input id="q" placeholder="제도 · 국가 · 키워드" autocomplete="off">
    <span class="count" id="cnt">전체 {len(items)}건</span>
  </div>
  <div class="stats">
    <div class="stat"><b>{len(items)}</b><span>제도</span></div>
    <div class="stat"><b>{len(countries)}</b><span>국가</span></div>
    <div class="stat"><b>{nodes}</b><span>절차 노드</span></div>
    <div class="stat ok"><b>{verified}</b><span>조문 대조 완료</span></div>
    <div class="stat bad"><b>{discs}</b><span>현행 기준 반영</span></div>
  </div>
</div></div>

<div class="wrap cols">
  <aside class="side">
    <div class="grp">
      <h3>국가별 바로가기</h3>
      <button aria-pressed="true" data-f="c" data-v=""><i class="dot" style="background:var(--fg)"></i>전체<span class="n">{len(items)}</span></button>
      {side_c}
    </div>
    <div class="grp">
      <h3>제도 축</h3>
      <button aria-pressed="true" data-f="a" data-v=""><i class="dot" style="background:var(--fg)"></i>전체<span class="n">{len(items)}</span></button>
      {side_a}
    </div>
  </aside>

  <main class="panel">
    <div class="panel-hd">제도 대장 <span>· <span id="hcnt">{len(items)}</span>개 결과</span></div>
    <table>
      <thead><tr><th>NO</th><th>제도</th><th>국가</th><th>축</th><th>검증</th><th>대조 결과</th></tr></thead>
      <tbody id="tb">{''.join(rows)}</tbody>
    </table>
    <div class="empty" id="none" hidden>조건에 맞는 제도가 없습니다.</div>
  </main>
</div>"""

    js = """
var q=document.getElementById('q'),tb=document.getElementById('tb'),
    cnt=document.getElementById('cnt'),hcnt=document.getElementById('hcnt'),
    none=document.getElementById('none'),F={c:'',a:''};
function apply(){
  var t=q.value.trim().toLowerCase(),n=0;
  Array.prototype.forEach.call(tb.rows,function(r){
    var ok=(!F.c||r.dataset.c===F.c)&&(!F.a||r.dataset.a===F.a)&&(!t||r.dataset.s.indexOf(t)>=0);
    r.hidden=!ok; if(ok)n++;
  });
  cnt.textContent=(t||F.c||F.a)?(n+'건 표시'):('전체 '+n+'건');
  hcnt.textContent=n; none.hidden=n>0;
}
q.addEventListener('input',apply);
document.querySelectorAll('.side button').forEach(function(b){
  b.addEventListener('click',function(){
    var f=b.dataset.f;F[f]=b.dataset.v;
    document.querySelectorAll('.side button[data-f="'+f+'"]').forEach(function(x){
      x.setAttribute('aria-pressed',String(x===b));});
    apply();
  });
});
var initialAxis=new URLSearchParams(location.search).get('axis');
if(initialAxis){
  var initialButton=document.querySelector('.side button[data-f="a"][data-v="'+initialAxis+'"]');
  if(initialButton) initialButton.click();
}
"""
    return page(SITE_TITLE, body, nav="list", extra_js=js)


# ─────────────────────────────────────────────────────────── 상세

def build_detail(d: dict, items: list[dict], *, standalone: bool = False) -> str:
    same_country = [item for item in items if country_slug(item) == country_slug(d)]
    same_country.sort(key=lambda item: item["priority"])
    idx = same_country.index(d)
    prev = same_country[idx - 1] if idx > 0 else None
    nxt = same_country[idx + 1] if idx < len(same_country) - 1 else None
    c, v, p = d["canvas"], d["verification"], d.get("process") or {}
    lanes, stages = p.get("lanes", []), p.get("stages", [])
    nodes, edges = p.get("nodes", []), p.get("edges", [])
    discs = v.get("discrepancies", [])
    hi = sum(1 for x in discs if x["severity"] == "high")

    # 조문 대조 수
    checked = sum(len([a for a in (s.get("articlesChecked") or "").split(",") if a.strip()])
                  for s in v.get("sources", []))

    opts = "".join(
        f'<option value="{e(x["slug"])}"{" selected" if x is d else ""}>'
        f'{x["priority"]:02d} · {e(x["name"] if x["axis"] == "construction" else country_display_name(x["country"]["name"]) + " " + AXIS_LABEL[x["axis"]])}</option>'
        for x in same_country)

    # 업무구조도 그리드
    board_width = 180 + 190 * len(stages)
    grid_cols = f"180px repeat({len(stages)},minmax(190px,1fr))"
    stage_heading = "레인 \\ 단계" if d["axis"] == "construction" else "레인 \\ 게이트"
    head = f'<div class="brow head" style="grid-template-columns:{grid_cols}">' \
           f'<div class="bcell"><span class="lane-t">{e(stage_heading)}</span></div>'
    for s in stages:
        k, _, t = s.partition(" ")
        head += f'<div class="bcell"><span class="stage-k">{e(k)}</span><span class="stage-t">{e(t or s)}</span></div>'
    head += "</div>"

    rows = ""
    for lane in lanes:
        rows += f'<div class="brow" style="grid-template-columns:{grid_cols}">' \
                f'<div class="bcell"><span class="lane-t">{e(lane)}</span></div>'
        for st in stages:
            cell = ""
            for n in nodes:
                if n["lane"] != lane or n["stage"] != st:
                    continue
                tone = NODE_TONE.get(n["status"], "")
                tag = {"key": "핵심", "warn": "유의", "back": "회귀"}.get(tone, "")
                cell += f"""<button class="node" data-id="{e(n['id'])}"{f' data-tone="{tone}"' if tone else ''}>
  <span class="id">{e(n['id'])}{f'<span class="tag">{tag}</span>' if tag else ''}</span>
  <span class="nm">{e(n['name'])}</span></button>"""
            rows += f'<div class="bcell" data-lane="{e(lane)}" data-stage="{e(st)}">{cell}</div>'
        rows += "</div>"

    # 캔버스 — 법령명은 verification.sources의 원문 URL과 자동으로 이어 붙인다
    surl = source_urls(d)
    laws = "".join(
        f'<div class="law"><span class="nm">{link(e(l["law"]), l.get("url") or surl.get(l["law"]))}</span>'
        f'<span class="ar">{e(l.get("articles") or "")}</span>'
        f'<span class="badge plain muted" style="margin-left:auto">{e(KIND_LABEL.get(l["kind"], l["kind"]))}</span></div>'
        for l in c["legalBasis"])
    auths = "".join(
        f'<div class="auth"><b>{link(e(a["name"]), a.get("url"))}</b>'
        f'<span>{el(a["role"])}'
        + (f' <span class="badge {VERIF_TONE.get(a["verification"], "muted")}">'
           f'{e(VERIF_LABEL.get(a["verification"], a["verification"]))}</span>'
           if a.get("verification") else "")
        + '</span></div>'
        for a in c["authorities"])
    steps = "".join(f"<li>{el(s.split('. ', 1)[-1] if s[:2].rstrip('.').isdigit() else s)}</li>"
                    for s in c["procedure"])
    docs = "".join(
        f'<div class="docset"><b>{e(x["actor"])}</b><div class="chips">'
        + "".join(f'<span class="chip">{e(t)}</span>' for t in x["documents"]) + "</div></div>"
        for x in c["submittedDocuments"])
    bott = "".join(f"<li>{el(x)}</li>" for x in c["bottlenecks"])
    barr = "".join(f"<li>{el(x)}</li>" for x in c.get("entryBarriers", []))
    fv = "".join(f"<li>{el(x)}</li>" for x in d["fieldVerification"])
    findings = "".join(
        f'<div class="decision" data-state="{e(x["status"])}">'
        f'<span class="badge {CONSTRUCTION_STATUS_TONE.get(x["status"], "muted")}">'
        f'{e(CONSTRUCTION_STATUS_LABEL.get(x["status"], x["status"]))}</span>'
        f'<span class="badge plain muted" style="margin-left:6px">{e(x["id"])}</span>'
        f'<p>{el(x["text"])}</p>'
        f'<div class="sources">근거 · {e(" · ".join(x.get("basis", [])))}</div></div>'
        for x in c.get("keyFindings", []))
    overlays = "".join(
        f'<div class="overlay"><span class="badge {CONSTRUCTION_STATUS_TONE.get(x["status"], "muted")}">'
        f'{e(CONSTRUCTION_STATUS_LABEL.get(x["status"], x["status"]))}</span>'
        f'<span class="badge plain muted" style="margin-left:6px">{e(x["id"])}</span>'
        f'<h3>{e(x["area"])}</h3><p>{el(x["rule"])}</p>'
        f'<p class="missing"><b>결측 증빙</b> · {e(" · ".join(x.get("missing_evidence", [])))}</p>'
        f'<p><b>사업 영향</b> · {el(x["consequence"])}</p></div>'
        for x in c.get("siteOverlays", []))
    # 관련 제도 — standalone(단독 파일)에서는 그 파일이 없으므로 링크 대신 이름만.
    related_slugs = list(d["related"])
    related_slugs.extend(
        item["slug"] for item in same_country
        if item["slug"] != d["slug"] and item["slug"] not in related_slugs
    )
    rel = "".join(
        (f'<span class="chip">{e(next((y["name"] for y in items if y["slug"] == r), r))}</span>'
         if standalone else
         f'<a class="chip" style="text-decoration:none" href="../{e(r)}/index.html">{e(next((y["name"] for y in items if y["slug"] == r), r))}</a>')
        for r in related_slugs)

    # 검증
    srcs = "".join(
        f'<li><a class="ref" href="{e(s["officialUrl"])}" target="_blank" rel="noopener">{e(s.get("officialName") or s["law"])}</a>'
        f'<span class="badge plain muted" style="margin-left:6px">{e(KIND_LABEL.get(s["kind"], s["kind"]))}</span>'
        + (f'<span class="badge {CONSTRUCTION_STATUS_TONE.get(s["status"], "muted")}" style="margin-left:6px">'
           f'{e(CONSTRUCTION_STATUS_LABEL.get(s["status"], s["status"]))}</span>'
           if s.get("status") else "")
        + (f'<span class="badge {VERIF_TONE.get(s["verificationLevel"], "muted")}" style="margin-left:6px">'
           f'{e(VERIF_LABEL.get(s["verificationLevel"], s["verificationLevel"]))}</span>'
           if s.get("verificationLevel") else "")
        + (f'<span class="ar">대조 조문 {e(s["articlesChecked"])}</span>' if s.get("articlesChecked") else "")
        + f'<span class="ar">확인 {e(s["retrievedOn"])}{" · " + e(s["publisher"]) if s.get("publisher") else ""}</span>'
        + (f'<span class="ar">{el(s["note"])}</span>' if s.get("note") else "")
        + '</li>'
        for s in v.get("sources", []))
    notes = "".join(f'<p class="note">{el(x)}</p>' for x in v.get("notes", []))
    unres = "".join(
        f'<div class="card" style="margin-bottom:12px"><h3>{link(e(u["law"]), u.get("url"))} '
        f'<span class="badge plain muted">{e(u["reasonCode"])}</span></h3>'
        f'<p style="margin:0 0 8px;font-size:13.5px">{el(u["reason"])}</p>'
        f'<p style="margin:0;font-size:13px;color:var(--muted)">다음 조치 — {e(u["nextStep"])}</p></div>'
        for u in v.get("unresolved", []))

    disc_html = "".join(disc_card(d, x) for x in discs)
    n_up = sum(1 for x in discs if x.get("upstream"))

    # 원문 근거 — 현장에서 그대로 인용할 조문 verbatim
    quotes = d.get("sourceQuotes", [])
    quotes_html = "".join(
        f"""<div class="qc">
  <div class="qhd">
    <span class="qart">{link(e(q["article"]), surl.get(q["law"]))}</span>
    <span class="badge plain muted">{e(q["law"])}</span>
  </div>
  <div class="qtext">{e(q["quote"])}</div>
  <p class="qgist">{el(q["gist"])}</p>
  {f'<details><summary>한국어 직역(참고 — 공식 번역 아님)</summary><p class="qko">{e(q["ko"])}</p></details>' if q.get("ko") else ''}
</div>"""
        for q in quotes)

    subnav = "" if standalone else f"""
<div class="subnav"><div class="wrap">
  <label for="sel">제도 선택</label>
  <select id="sel" style="min-width:280px">{opts}</select>
  <a class="btn" {'href="../' + e(prev["slug"]) + '/index.html"' if prev else 'disabled'} style="text-decoration:none">← 이전</a>
  <a class="btn" {'href="../' + e(nxt["slug"]) + '/index.html"' if nxt else 'disabled'} style="text-decoration:none">다음 →</a>
  <span class="pos">이 국가의 제도 {idx + 1}/{len(same_country)}</span>
</div></div>"""

    body = f"""
{subnav}

<div class="wrap dtl-hd">
  <div class="row">
    <span class="badge plain muted">NO {d['priority']:02d}</span>
    <span class="badge plain muted">{e(d['country']['name'])} · {e(d['country']['nameEn'])}</span>
    <span class="badge plain muted">{e(AXIS_LABEL[d['axis']])}</span>
    <span class="badge {VERIF_TONE[v['status']]}">{e(VERIF_LABEL[v['status']])}</span>
    {f'<span class="badge bad">확인사항 {len(discs)}건</span>' if discs else ''}
  </div>
  <h1>{e(d['name'])}</h1>
  <p class="one">{e(d['oneLiner'])}</p>
  <div class="tiles">
    <div class="tile"><b>{len(nodes)}</b><span>절차 노드</span></div>
    <div class="tile"><b>{len(lanes)}</b><span>행위 레인</span></div>
    <div class="tile"><b>{len(stages)}</b><span>게이트</span></div>
    <div class="tile ok"><b>{checked}</b><span>대조 조문</span></div>
    <div class="tile bad"><b>{len(discs)}</b><span>현행 기준{f' (필수 확인 {hi})' if hi else ''}</span></div>
    <div class="tile warn"><b>{len(d['fieldVerification'])}</b><span>현장 검증</span></div>
  </div>
</div>

<div class="wrap">
<section class="blk">
  <div class="hd-row">
    <div>
      <h2>업무구조도</h2>
      <p class="desc">제도의 결정적 단계와 유의사항·회귀 구간을 강조해 표시합니다. 노드를 누르면 근거 조문과 기한이 열립니다.</p>
    </div>
    <div class="legend">
      <span><i style="background:var(--key)"></i>핵심 단계</span>
      <span><i style="background:var(--warn)"></i>유의</span>
      <span><i style="background:var(--back)"></i>보완 회귀</span>
    </div>
  </div>
  <div class="boardwrap"><div class="board" id="board" style="min-width:{board_width}px">
    <svg class="edges" id="edges"></svg>
    {head}{rows}
  </div></div>
</section>

<section class="blk">
  <h2>한 장 캔버스</h2>
  <p class="desc">{e(c['purpose'])}</p>
  <div class="cards">
    <div class="card span2"><h3>절차</h3><ol class="steps">{steps}</ol></div>
    <div class="card"><h3>적용 대상</h3><p style="margin:0;font-size:13.5px;line-height:1.7">{e(c['applicability'])}</p></div>
    <div class="card"><h3>법적 근거</h3>{laws}</div>
    <div class="card"><h3>권한 기관</h3>{auths}</div>
    <div class="card"><h3>이해관계자</h3><p style="margin:0;font-size:13.5px;line-height:1.7">{e(c['stakeholders'])}</p></div>
    <div class="card"><h3>제출서류</h3>{docs}</div>
    <div class="card"><h3>유의사항 · 병목</h3><ul class="plain">{bott}</ul></div>
    {f'<div class="card"><h3>진입장벽</h3><ul class="plain">{barr}</ul></div>' if barr else ''}
    <div class="card"><h3>현장 검증 필요</h3><ul class="plain">{fv}</ul></div>
    <div class="card"><h3>관련 제도</h3><div class="chips">{rel}</div></div>
  </div>
</section>

{f'''<section class="blk">
  <h2>핵심 적용판단</h2>
  <p class="desc">확인된 법령 사실과 사업별 조건부·미확정 판단을 분리해 표시합니다.</p>
  <div class="decision-list">{findings}</div>
</section>''' if findings else ''}

{f'''<section class="blk">
  <h2>부지·특구 적용조건</h2>
  <p class="desc">공개 법령만으로 확정할 수 없는 필지별 규칙과 필요한 원자료입니다.</p>
  <div class="overlay-grid">{overlays}</div>
</section>''' if overlays else ''}

{f'''<section class="blk">
  <h2>법령 원문</h2>
  <p class="desc">현장에서 발주처에 그대로 제시할 수 있는 조문 원문입니다. 우리 요약이 아니라 verbatim이며,
    조문 번호를 누르면 원문 문서로 이동합니다. 한국어 요지 아래로 직역(참고용)을 펼칠 수 있습니다.</p>
  <div class="quotes">{quotes_html}</div>
</section>''' if quotes else ''}

{f'''<section class="blk">
  <h2>현행 기준 반영 {len(discs)}건</h2>
  <p class="desc">공식 법령·기관 원문으로 확인한 현행 기준과 실무 확인사항입니다.
    출처는 각 항목에 연결했으며{"" if standalone else ' <a href="../../errata/index.html">반영 출처</a>에서 한 번에 볼 수 있습니다'}.</p>
  {disc_html}
</section>''' if discs else ''}

<section class="blk">
  <h2>검증</h2>
  <p class="desc">{e(v['method'])}</p>
  <div class="cards">
    <div class="card span2"><h3>검증 범위</h3>
      <p style="margin:0;font-size:13.5px;line-height:1.7">{e(v['scope'])}</p>
      <p style="margin:12px 0 0;font-size:12.5px;color:var(--muted)">확인일 {e(v['verifiedAt'])} · 자료집 기준일 {e(d['asOfDate'])}</p>
    </div>
    <div class="card"><h3>대조에 쓴 원문</h3><ul class="srcs" style="padding-left:16px;margin:0">{srcs}</ul></div>
    {f'<div class="card span2"><h3>주의</h3>{notes}</div>' if notes else ''}
  </div>
  {f'<h3 style="font-size:14px;margin:26px 0 12px">확인하지 못한 것</h3>{unres}' if unres else ''}
  <p style="margin:22px 0 0;font-size:12.5px;color:var(--muted)">
    {e(VERIF_LABEL[v['status']])} — 조문의 존재와 문언 일치만 뜻합니다. 법적 해석·적용 타당성·개정 반영 여부는 별도 검토 대상입니다.
  </p>
</section>
</div>

<dialog class="drawer" id="dlg"><div class="pane">
  <button class="close" aria-label="상세 닫기" onclick="document.getElementById('dlg').close()">×</button>
  <div id="dbody"></div>
</div></dialog>"""

    # drawer는 innerHTML로 그리므로 텍스트를 미리 escape하고, 조문에는 원문 URL을 붙여 넘긴다
    node_view = {}
    for n in nodes:
        nv = dict(n)
        nv["id"] = e(nv["id"])
        for k in (
            "name", "actor", "action", "deadline", "blocker", "lane", "stage",
            "applicability", "report_use", "consulted_authorities", "confidence_reason",
        ):
            if nv.get(k):
                nv[k] = el(nv[k])
        if nv.get("output_documents"):
            nv["output_documents"] = [e(x) for x in nv["output_documents"]]
        if nv.get("legal_basis"):
            nv["legal_basis"] = [
                {
                    "law": e(lb["law"]),
                    "article": e(lb["article"]),
                    "url": e(lb.get("url") or surl.get(lb["law"], "")),
                    "kind": e(KIND_LABEL.get(lb.get("kind"), lb.get("kind", ""))),
                    "status": e(CONSTRUCTION_STATUS_LABEL.get(lb.get("status"), lb.get("status", ""))),
                    "status_tone": e(CONSTRUCTION_STATUS_TONE.get(lb.get("status"), "muted")),
                    "verification": e(VERIF_LABEL.get(
                        lb.get("verification_level"), lb.get("verification_level", "")
                    )),
                    "verification_tone": e(VERIF_TONE.get(lb.get("verification_level"), "muted")),
                    "note": el(lb.get("note", "")),
                }
                for lb in nv["legal_basis"]
            ]
        if nv.get("open_questions"):
            nv["open_questions"] = [
                {
                    "id": e(item["id"]),
                    "blocking": bool(item["blocking"]),
                    "question": el(item["question"]),
                    "why": el(item["why"]),
                    "evidence": [e(value) for value in item["evidence"]],
                    "confirm_with": [e(value) for value in item["confirm_with"]],
                }
                for item in nv["open_questions"]
            ]
        if nv.get("permit_gates"):
            nv["permit_gates"] = [
                {
                    "order": item["order"],
                    "gate": e(item["gate"]),
                    "decision": el(item["decision"]),
                    "depends_on": item["depends_on"],
                    "output": e(item["output"]),
                }
                for item in nv["permit_gates"]
            ]
        node_view[n["id"]] = nv

    edge_view = []
    for edge in edges:
        ev = dict(edge)
        if ev.get("label"):
            ev["label"] = e(ev["label"])
        edge_view.append(ev)

    permit_prefix = "P" if d["axis"] == "construction" else "G"
    permit_label = "연결 인허가 절차" if d["axis"] == "construction" else "연결 Gate"
    prerequisite_label = "선행 절차" if d["axis"] == "construction" else "선행 Gate"
    js = f"""
var NODES={script_json(node_view)};
var EDGES={script_json(edge_view)};

var _sel=document.getElementById('sel');
if(_sel) _sel.addEventListener('change',function(){{ location.href='../'+this.value+'/index.html'; }});

/* 엣지 그리기 — 노드 DOM 위치를 재서 SVG로 연결 */
function draw(){{
  var board=document.getElementById('board'),svg=document.getElementById('edges');
  if(!board||!svg)return;
  var bb=board.getBoundingClientRect();
  svg.setAttribute('viewBox','0 0 '+board.scrollWidth+' '+board.scrollHeight);
  svg.setAttribute('width',board.scrollWidth); svg.setAttribute('height',board.scrollHeight);
  var cs=getComputedStyle(document.documentElement);
  var C={{sequence:cs.getPropertyValue('--muted').trim(),
         message:cs.getPropertyValue('--back').trim(),
         loop:cs.getPropertyValue('--warn').trim()}};
  var d='<defs>';
  ['sequence','message','loop'].forEach(function(t){{
    d+='<marker id="m-'+t+'" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto">'
      +'<path d="M0 0 L8 4 L0 8 z" fill="'+C[t]+'"/></marker>';
  }});
  d+='</defs>';
  var GAP=5;
  function rel(rc){{return {{x:rc.left-bb.left+board.scrollLeft, y:rc.top-bb.top+board.scrollTop,
                            r:rc.right-bb.left+board.scrollLeft, b:rc.bottom-bb.top+board.scrollTop,
                            w:rc.width, h:rc.height}};}}
  function box(id){{
    var el=Array.prototype.find.call(
      board.querySelectorAll('.node'),function(node){{return node.dataset.id===id;}}
    );
    if(!el)return null; return rel(el.getBoundingClientRect());
  }}

  /* 라우팅은 korea100studio의 거터 라우팅을 우리 그리드에 이식한 것이다.
     핵심: 카드를 지나야 하는 선은 카드가 없는 거터(행 하단·열 측면)로 우회한다.
     DOM에서 노드·행·열을 실측할 수 있어, 여러 직교 경로 후보를 만들고
     무관한 카드를 가장 적게 관통하는(동수면 가장 짧은) 것을 고른다. */

  // 장애물(모든 노드)과 거터(노드 없는 띠) 실측
  var OB=[];
  board.querySelectorAll('.node').forEach(function(el){{ var r=box(el.dataset.id); r.id=el.dataset.id; OB.push(r); }});
  var rowGut=[], colGut=[];
  board.querySelectorAll('.brow:not(.head)').forEach(function(el){{ var r=rel(el.getBoundingClientRect());
    rowGut.push(r.y+9); rowGut.push(r.b-9); }});
  var hc=board.querySelectorAll('.brow.head .bcell');
  for(var i=1;i<hc.length;i++){{ var r=rel(hc[i].getBoundingClientRect()); colGut.push(r.x+11); colGut.push(r.r-11); }}

  function segHit(ax,ay,bx,by,e1,e2){{
    var n=0, M=3;
    for(var i=0;i<OB.length;i++){{ var o=OB[i]; if(o.id===e1||o.id===e2) continue;
      var L=o.x+M,R=o.r-M,T=o.y+M,B=o.b-M;
      if(Math.abs(ay-by)<0.5){{ if(ay>T&&ay<B && Math.max(ax,bx)>L && Math.min(ax,bx)<R) n++; }}
      else {{ if(ax>L&&ax<R && Math.max(ay,by)>T && Math.min(ay,by)<B) n++; }}
    }} return n;
  }}
  function uniq(pts){{ return pts.filter(function(p,i){{ return i===0 || Math.abs(p.x-pts[i-1].x)>0.5 || Math.abs(p.y-pts[i-1].y)>0.5; }}); }}
  function score(pts,e1,e2){{ pts=uniq(pts); var p=0,l=0;
    for(var i=0;i<pts.length-1;i++){{ p+=segHit(pts[i].x,pts[i].y,pts[i+1].x,pts[i+1].y,e1,e2);
      l+=Math.abs(pts[i].x-pts[i+1].x)+Math.abs(pts[i].y-pts[i+1].y); }}
    return {{pts:pts,p:p,l:l}}; }}

  function route(a,b,ed){{
    var acx=a.x+a.w/2,acy=a.y+a.h/2,bcx=b.x+b.w/2,bcy=b.y+b.h/2, e1=ed.source,e2=ed.target, cs=[];
    // 세로 계열 — a의 위/아래 변에서 나가 b의 위/아래 변으로
    var below=bcy>acy, sp={{x:acx,y:below?a.b:a.y}}, tp={{x:bcx,y:below?b.y:b.b}}, tg={{x:tp.x,y:tp.y+(below?-GAP:GAP)}};
    cs.push(score([sp,{{x:sp.x,y:tg.y}},tg,tp],e1,e2));                                   // 직선/L
    rowGut.forEach(function(my){{ if(my>Math.min(sp.y,tp.y)+6&&my<Math.max(sp.y,tp.y)-6)   // 행 거터 크로스
      cs.push(score([sp,{{x:sp.x,y:my}},{{x:tp.x,y:my}},tg,tp],e1,e2)); }});
    colGut.forEach(function(gx){{                                                          // 열 측면 탈출
      var as={{x:gx>acx?a.r:a.x,y:acy}};
      cs.push(score([as,{{x:gx,y:acy}},{{x:gx,y:tg.y}},tg,tp],e1,e2)); }});
    // 가로 계열 — a의 좌/우 변에서 나가 b의 좌/우 변으로
    var right=bcx>acx, sp2={{x:right?a.r:a.x,y:acy}}, tp2={{x:right?b.x:b.r,y:bcy}}, tg2={{x:tp2.x+(right?-GAP:GAP),y:tp2.y}};
    cs.push(score([sp2,{{x:tg2.x,y:sp2.y}},tg2,tp2],e1,e2));
    colGut.forEach(function(mx){{ if(mx>Math.min(sp2.x,tp2.x)+6&&mx<Math.max(sp2.x,tp2.x)-6)
      cs.push(score([sp2,{{x:mx,y:sp2.y}},{{x:mx,y:tp2.y}},tg2,tp2],e1,e2)); }});
    rowGut.forEach(function(gy){{                                                          // 행 거터 우회
      var as={{x:acx,y:gy>acy?a.b:a.y}};
      cs.push(score([as,{{x:acx,y:gy}},{{x:tp2.x,y:gy}},tg2,tp2],e1,e2)); }});
    // 회귀선 — 아래로 크게 우회 (되돌아가는 흐름을 시각적으로 구분)
    if(ed.type==='loop'){{ var gy=Math.max(a.b,b.b)+26;
      cs.push(score([{{x:acx,y:a.b}},{{x:acx,y:gy}},{{x:bcx,y:gy}},{{x:bcx,y:b.b+GAP}},{{x:bcx,y:b.b}}],e1,e2)); }}
    cs=cs.filter(function(c){{return c.pts.length>=2;}});
    cs.sort(function(x,y){{ return x.p-y.p || x.l-y.l; }});
    return cs[0];
  }}

  function rnd(v){{return Math.round(v*10)/10;}}
  function orthPath(pts){{                    // 직교 경로 + 모서리 라운딩
    pts=uniq(pts); if(pts.length<2)return '';
    var d='M'+rnd(pts[0].x)+' '+rnd(pts[0].y);
    for(var i=1;i<pts.length-1;i++){{
      var p=pts[i-1],c=pts[i],n=pts[i+1];
      var d1=Math.hypot(c.x-p.x,c.y-p.y)||1, d2=Math.hypot(n.x-c.x,n.y-c.y)||1, r=Math.min(7,d1/2,d2/2);
      d+=' L'+rnd(c.x-(c.x-p.x)/d1*r)+' '+rnd(c.y-(c.y-p.y)/d1*r);
      d+=' Q'+rnd(c.x)+' '+rnd(c.y)+' '+rnd(c.x+(n.x-c.x)/d2*r)+' '+rnd(c.y+(n.y-c.y)/d2*r);
    }}
    var e=pts[pts.length-1]; return d+' L'+rnd(e.x)+' '+rnd(e.y);
  }}

  EDGES.forEach(function(ed){{
    var a=box(ed.source),b=box(ed.target); if(!a||!b)return;
    var t=ed.type||'sequence', rt=route(a,b,ed);
    d+='<path d="'+orthPath(rt.pts)+'" fill="none" stroke="'+C[t]+'" stroke-width="1.5" opacity="'
      +(t==='sequence'?'.55':'.8')+'"'+(t!=='sequence'?' stroke-dasharray="4 3"':'')
      +' marker-end="url(#m-'+t+')"/>';
  }});
  svg.innerHTML=d;
}}

function openNode(id){{
  var n=NODES[id]; if(!n)return;
  var h='<span class="badge plain muted">'+n.id+'</span> '
       +'<span class="badge plain muted">'+n.lane+'</span> '
       +'<span class="badge plain muted">'+n.stage+'</span>';
  h+='<h3>'+n.name+'</h3>';
  h+='<dl class="kv">';
  h+='<dt>담당</dt><dd>'+n.actor+'</dd>';
  if(n.consulted_authorities) h+='<dt>협의·관할기관</dt><dd>'+n.consulted_authorities+'</dd>';
  if(n.action) h+='<dt>내용</dt><dd>'+n.action+'</dd>';
  if(n.applicability) h+='<dt>적용 조건</dt><dd>'+n.applicability+'</dd>';
  if(n.deadline) h+='<dt>기한</dt><dd>'+n.deadline+'</dd>';
  if(n.output_documents&&n.output_documents.length)
    h+='<dt>산출 문서</dt><dd>'+n.output_documents.join(' · ')+'</dd>';
  if(n.blocker) h+='<dt>병목</dt><dd style="color:var(--warn)">'+n.blocker+'</dd>';
  if(n.legal_basis&&n.legal_basis.length){{
    h+='<dt>근거 조문</dt><dd>'+n.legal_basis.map(function(l){{
      var nm=l.url?'<a class="ref" href="'+l.url+'" target="_blank" rel="noopener">'+l.law+'</a>':l.law;
      var meta=(l.kind?' <span class="badge plain muted">'+l.kind+'</span>':'')
        +(l.status?' <span class="badge '+l.status_tone+'">'+l.status+'</span>':'')
        +(l.verification?' <span class="badge '+l.verification_tone+'">'+l.verification+'</span>':'');
      return '<div style="margin-bottom:9px">'+nm+' <code>'+l.article+'</code>'+meta
        +(l.note?'<div style="margin-top:3px;color:var(--muted)">'+l.note+'</div>':'')+'</div>';}}).join('')+'</dd>';
  }}
  if(typeof n.confidence==='number'){{
    h+='<dt>법령 근거 확신도</dt><dd>'+n.confidence.toFixed(2)
      +(n.confidence<0.8?' <span class="badge warn">현장 검증 필요</span>':'')+'</dd>';
  }}
  if(n.confidence_reason) h+='<dt>확신도 산정 근거</dt><dd>'+n.confidence_reason+'</dd>';
  if(n.report_use) h+='<dt>보고서 반영</dt><dd>'+n.report_use+'</dd>';
  if(n.permit_gates&&n.permit_gates.length){{
    h+='<dt>{e(permit_label)}</dt><dd>'+n.permit_gates.map(function(g){{
      var dep=g.depends_on&&g.depends_on.length?' · {e(prerequisite_label)} '+g.depends_on.map(function(x){{return '{e(permit_prefix)}'+x;}}).join(', '):'';
      return '<div style="margin-bottom:8px"><b>{e(permit_prefix)}'+g.order+' '+g.gate+'</b>'+dep
        +'<div>'+g.decision+'</div><div style="color:var(--muted)">산출물 · '+g.output+'</div></div>';}}).join('')+'</dd>';
  }}
  if(n.open_questions&&n.open_questions.length){{
    h+='<dt>현장 확인질문</dt><dd>'+n.open_questions.map(function(q){{
      return '<div style="margin-bottom:10px"><span class="badge '+(q.blocking?'bad':'muted')+'">'
        +(q.blocking?'Gate 차단':'추가 확인')+'</span> <code>'+q.id+'</code><div>'+q.question+'</div>'
        +'<div style="color:var(--muted)">영향 · '+q.why+'</div>'
        +'<div style="color:var(--muted)">확인기관 · '+q.confirm_with.join(' · ')+'</div>'
        +'<div style="color:var(--muted)">증빙 · '+q.evidence.join(' · ')+'</div></div>';}}).join('')+'</dd>';
  }}
  var ins=EDGES.filter(function(x){{return x.target===id}}),
      outs=EDGES.filter(function(x){{return x.source===id}});
  if(ins.length) h+='<dt>선행</dt><dd>'+ins.map(function(x){{
    return (NODES[x.source]?NODES[x.source].name:x.source)+(x.label?' ('+x.label+')':'');}}).join(' · ')+'</dd>';
  if(outs.length) h+='<dt>후속</dt><dd>'+outs.map(function(x){{
    return (NODES[x.target]?NODES[x.target].name:x.target)+(x.label?' ('+x.label+')':'');}}).join(' · ')+'</dd>';
  h+='</dl>';
  document.getElementById('dbody').innerHTML=h;
  document.getElementById('dlg').showModal();
}}

document.querySelectorAll('.node').forEach(function(b){{
  b.addEventListener('click',function(){{openNode(b.dataset.id)}});
  b.addEventListener('mouseenter',function(){{
    var id=b.dataset.id;
    var rel={{}};rel[id]=1;
    EDGES.forEach(function(x){{if(x.source===id)rel[x.target]=1;if(x.target===id)rel[x.source]=1;}});
    document.querySelectorAll('.node').forEach(function(o){{o.classList.toggle('dim',!rel[o.dataset.id])}});
  }});
  b.addEventListener('mouseleave',function(){{
    document.querySelectorAll('.node').forEach(function(o){{o.classList.remove('dim')}});
  }});
}});
document.getElementById('dlg').addEventListener('click',function(ev){{
  if(ev.target===this) this.close();
}});

addEventListener('load',draw); addEventListener('resize',draw);
new MutationObserver(draw).observe(document.documentElement,{{attributes:true,attributeFilter:['data-theme']}});
"""
    return page(f"{d['name']} | {SITE_TITLE}", body, depth=2, extra_js=js, standalone=standalone)


# ─────────────────────────────────────────────────────────── ODA 건축 법·제도

def construction_instrument_link(instrument: dict, label: str | None = None) -> str:
    """건축 법령·공식자료 링크. 공식 URL이 있는 자료만 외부 링크로 만든다."""
    return link(e(label or instrument["titleKo"]), instrument.get("officialUrl"))


def construction_basis_html(refs: list[dict], instruments: dict[str, dict]) -> str:
    parts = []
    for ref in refs:
        instrument = instruments[ref["instrumentId"]]
        provisions = ", ".join(ref.get("provisions", []))
        parts.append(
            construction_instrument_link(instrument)
            + (f' <span class="ar">{e(provisions)}</span>' if provisions else "")
        )
    return "<br>".join(parts) if parts else "—"


def build_construction_index(items: list[dict]) -> str:
    items = sorted(items, key=lambda d: country_name_sort_key(d["country"]["name"]))
    n_sources = sum(len(d["instruments"]) for d in items)
    n_requirements = sum(len(d["requirements"]) for d in items)
    n_blockers = sum(1 for d in items for q in d["openQuestions"] if q["blocking"])
    n_verified = sum(1 for d in items if d["verification"]["status"] == "article-verified")
    n_board_nodes = sum(len(d["processBoard"]["nodes"]) for d in items)
    asof = max(d["asOfDate"] for d in items)

    cards = []
    for d in items:
        board = d["processBoard"]
        counts = {state: sum(1 for r in d["requirements"] if r["status"] == state)
                  for state in ("confirmed", "conditional", "unresolved")}
        blockers = sum(1 for q in d["openQuestions"] if q["blocking"])
        pilot = d.get("pilotContext") or {}
        first = d["reportReadyConclusions"][0]["text"] if d.get("reportReadyConclusions") else d["purpose"]
        cards.append(f"""<article class="country-card">
  <div class="top">
    <span class="badge ok">{e(CONSTRUCTION_VERIFY_LABEL[d['verification']['status']])}</span>
    <span class="badge plain muted">기준일 {e(d['asOfDate'])}</span>
    {f'<span class="badge info">{e(pilot.get("location", ""))}</span>' if pilot else ''}
  </div>
  <h2>{e(d['country']['name'])} <span style="font-size:13px;color:var(--muted);font-weight:500">{e(d['country']['nameEn'])}</span></h2>
  <p>{e(first)}</p>
  <div class="metrics">
    <span><b>{len(d['requirements'])}</b>생애주기 의무</span>
    <span><b>{blockers}</b>Gate 차단 질문</span>
    <span><b>{len(d['instruments'])}</b>법령·공식자료</span>
    <span><b>{counts['confirmed']}/{counts['conditional']}/{counts['unresolved']}</b>확정/조건부/미확정</span>
    <span><b>{len(board['nodes'])}</b>구조도 노드</span>
  </div>
  <div class="studio-preview">
    <div class="viewport"><img src="../boards/{e(d['slug'])}-construction.svg"
      alt="{e(d['country']['name'])} 건축 인허가 업무구조도 미리보기" loading="lazy"></div>
    <div class="caption"><b>korea100studio 구조도</b><span>{len(board['lanes'])}개 행위주체 · {len(board['stages'])}단계 · {len(board['edges'])}개 연결</span></div>
  </div>
  <a class="btn" href="{e(d['slug'])}/index.html">구조도·전문가 브리프 보기 →</a>
</article>""")

    body = f"""
<div class="wrap hero">
  <div class="eyebrow">부지에서 준공·개장까지</div>
  <h1>그 나라, 건물은 어떻게 지을까?</h1>
  <p class="lede">ODA 건축사업에 필요한 도시계획·건설·건축사·환경·소방 법제를 사업 단계와 Gate 질문으로 정리합니다.</p>
  <p class="meta">{len(items)}개국 · 조문 대조 {n_verified}개국 · 기준일 {e(asof)}</p>
</div>

<div class="statbar"><div class="wrap">
  <div style="font-size:13px;color:var(--muted);max-width:60ch">
    법령을 찾는 데서 끝내지 않고 <b>어떤 증빙을 누구에게 받아야 다음 설계로 넘어갈 수 있는지</b> 보여줍니다.
  </div>
  <div class="stats">
    <div class="stat"><b>{len(items)}</b><span>국가</span></div>
    <div class="stat ok"><b>{n_sources}</b><span>법령·공식자료</span></div>
    <div class="stat"><b>{n_requirements}</b><span>생애주기 의무</span></div>
    <div class="stat"><b>{n_board_nodes}</b><span>구조도 노드</span></div>
    <div class="stat bad"><b>{n_blockers}</b><span>Gate 차단 질문</span></div>
  </div>
</div></div>

<main class="wrap" style="padding-block:32px 60px">
  <div class="country-cards">{''.join(cards)}</div>

  <section class="blk" style="margin-top:38px">
    <h2>보고서에는 이렇게 연결합니다</h2>
    <p class="desc">법령 사실과 개별 사업 적용판단을 분리해 근거 없는 수치·일정을 막습니다.</p>
    <div class="cards">
      <div class="card"><h3>1 · 현행 법령</h3><p style="margin:0;font-size:13.5px">폐지·대체·심의 중인 문서를 나누고 실제 확인한 조문을 표시합니다.</p></div>
      <div class="card"><h3>2 · 사업 적용</h3><p style="margin:0;font-size:13.5px">층수·면적·시설의 용도·위험 분류·발주주체처럼 입력에 따라 달라지는 의무는 조건부로 둡니다.</p></div>
      <div class="card"><h3>3 · Gate 자료요청</h3><p style="margin:0;font-size:13.5px">필지별 개발규제, 지반·침수, 환경분류, 실제 수수료·기간, 현지 설계·검사·보험기관처럼 사업별로 확인할 항목을 분리합니다.</p></div>
    </div>
  </section>
</main>"""
    return page(f"건축 법·제도 | {SITE_TITLE}", body, depth=1, nav="construction")


def build_construction_detail(d: dict, all_items: list[dict], procurement_items: list[dict]) -> str:
    instruments = {x["id"]: x for x in d["instruments"]}
    authorities = {x["id"]: x for x in d["authorities"]}
    requirements = d["requirements"]
    board = d["processBoard"]
    blockers = [q for q in d["openQuestions"] if q["blocking"]]
    non_blockers = [q for q in d["openQuestions"] if not q["blocking"]]
    context = d.get("pilotContext") or {}
    counts = {state: sum(1 for r in requirements if r["status"] == state)
              for state in ("confirmed", "conditional", "unresolved")}

    opts = "".join(
        f'<option value="{e(x["slug"])}"{" selected" if x is d else ""}>'
        f'{e(x["country"]["name"])} · {e(x["asOfDate"])}</option>'
        for x in sorted(all_items, key=lambda y: country_name_sort_key(y["country"]["name"])))

    sibling_procurement = [x for x in procurement_items if country_slug(x) == d["slug"]]
    procurement_links = "".join(
        f'<a class="chip" style="text-decoration:none" href="../../model/{e(x["slug"])}/index.html">{e(AXIS_LABEL[x["axis"]])}</a>'
        for x in sibling_procurement
    )

    decisions = []
    for item in d["reportReadyConclusions"]:
        source_links = " · ".join(
            construction_instrument_link(instruments[ident]) for ident in item["basis"]
        )
        decisions.append(f"""<article class="decision" data-state="{e(item['confidence'])}">
  <span class="badge {CONSTRUCTION_STATUS_TONE[item['confidence']]}">{e(CONSTRUCTION_STATUS_LABEL[item['confidence']])}</span>
  <p>{e(item['text'])}</p>
  <div class="sources">근거 · {source_links}</div>
</article>""")

    blocker_cards = []
    for item in blockers:
        evidence = "".join(f"<li>{e(x)}</li>" for x in item["evidenceNeeded"])
        confirms = ", ".join(authorities[x]["nameKo"] for x in item["confirmWith"])
        blocker_cards.append(f"""<article class="blocker">
  <div class="stage">{e(CONSTRUCTION_STAGE_LABEL[item['stage']])} · {e(item['id'])}</div>
  <h3>{e(item['question'])}</h3>
  <p>{e(item['whyItMatters'])}</p>
  <ul>{evidence}</ul>
  <p style="margin-top:9px"><b>확인</b> {e(confirms)} · <b>담당</b> {e(item['owner'])}</p>
</article>""")

    gates = "".join(f"""<div class="gate-step">
  <b>{e(item['gate'])}</b>
  <p>{e(item['decision'])}</p>
  <div class="out"><b>산출물</b><br>{e(item['output'])}</div>
</div>""" for item in d["permitPath"])

    requirement_groups = []
    for stage_index, stage in enumerate(CONSTRUCTION_STAGE_ORDER):
        stage_items = [x for x in requirements if x["stage"] == stage]
        if not stage_items:
            continue
        req_html = []
        for item in stage_items:
            evidence = "".join(f'<span class="chip">{e(x)}</span>' for x in item["evidenceToObtain"])
            authority_names = ", ".join(authorities[x]["nameKo"] for x in item["authorityIds"])
            req_html.append(f"""<article class="req-item">
  <div class="top"><h3>{e(item['topic'])}</h3>
    <span class="badge {CONSTRUCTION_STATUS_TONE[item['status']]}">{e(CONSTRUCTION_STATUS_LABEL[item['status']])}</span></div>
  <p class="minor"><b>적용</b> · {e(item['applicability'])}</p>
  <p>{e(item['requirement'])}</p>
  <p class="minor"><b>근거</b> · {construction_basis_html(item['legalBasis'], instruments)}</p>
  <p class="minor"><b>관할</b> · {e(authority_names)}</p>
  <div class="chips">{evidence}</div>
  <div class="todo"><b>보고서 반영</b>{e(item['reportUse'])}</div>
</article>""")
        requirement_groups.append(f"""<details class="req-group" id="stage-{e(stage)}"{' open' if stage_index == 0 else ''}>
  <summary>{e(CONSTRUCTION_STAGE_LABEL[stage])} · {len(stage_items)}건</summary>
  <div class="req-items">{''.join(req_html)}</div>
</details>""")

    overlays = []
    for item in d["siteOverlays"]:
        missing = " · ".join(item["missingEvidence"])
        overlays.append(f"""<article class="overlay">
  <span class="badge {CONSTRUCTION_STATUS_TONE[item['status']]}">{e(CONSTRUCTION_STATUS_LABEL[item['status']])}</span>
  <h3>{e(item['area'])}</h3>
  <p>{e(item['rule'])}</p>
  <p class="missing"><b>빠진 증빙</b> · {e(missing)}</p>
  <p><b>보고서 처리</b> · {e(item['consequence'])}</p>
</article>""")

    other_question_rows = "".join(f"""<tr>
  <td><span class="badge plain muted">{e(CONSTRUCTION_STAGE_LABEL[item['stage']])}</span></td>
  <td class="name"><b>{e(item['question'])}</b><p>{e(item['whyItMatters'])}</p></td>
  <td style="font-size:12.5px">{e(' · '.join(item['evidenceNeeded']))}</td>
  <td style="font-size:12.5px;color:var(--muted)">{e(item['owner'])}</td>
</tr>""" for item in non_blockers)

    checklist_rows = "".join(f"""<tr>
  <td><span class="badge plain muted">{e(item['phase'])}</span></td>
  <td style="font-size:13px">{e(item['check'])}</td>
  <td style="font-size:13px;color:var(--muted)">{e(item['output'])}</td>
</tr>""" for item in d["fieldworkChecklist"])

    kind_label = {
        "act": "법률", "decree": "시행령·명령", "order": "부령", "plan": "도시계획",
        "official-guidance": "공식 안내", "draft": "법안",
    }
    instrument_rows = "".join(f"""<tr>
  <td class="name"><b>{construction_instrument_link(item)}</b><p>{e(item['title'])}</p></td>
  <td><span class="badge {CONSTRUCTION_STATUS_TONE[item['status']]}">{e(CONSTRUCTION_STATUS_LABEL[item['status']])}</span></td>
  <td style="font-size:12.5px">{e(kind_label.get(item['kind'], item['kind']))}</td>
  <td style="font-size:12.5px">{e(', '.join(item.get('articlesChecked', [])) or '—')}</td>
  <td style="font-size:12.5px;color:var(--muted)">{e(item.get('note', '—'))}</td>
</tr>""" for item in d["instruments"])

    anchor_links = "".join(
        f'<a href="#stage-{e(stage)}">{e(CONSTRUCTION_STAGE_LABEL[stage])}</a>'
        for stage in CONSTRUCTION_STAGE_ORDER if any(x["stage"] == stage for x in requirements)
    )
    known = "".join(f"<li>{e(x)}</li>" for x in context.get("known", []))
    unknown = "".join(f"<li>{e(x)}</li>" for x in context.get("unknown", []))
    limitations = "".join(f'<p class="note">{e(x)}</p>' for x in d["verification"].get("limitations", []))

    subnav = f"""<div class="subnav"><div class="wrap">
  <label for="construction-country">국가 선택</label>
  <select id="construction-country" style="min-width:220px">{opts}</select>
  <a class="btn" href="../index.html" style="text-decoration:none">전체 국가</a>
  <div class="chips" style="margin:0 0 0 auto">{procurement_links}</div>
</div></div>"""

    body = f"""
{subnav}
<div class="wrap dtl-hd">
  <div class="row">
    <span class="badge ok">{e(CONSTRUCTION_VERIFY_LABEL[d['verification']['status']])}</span>
    <span class="badge plain muted">{e(d['country']['name'])} · {e(d['country']['nameEn'])}</span>
    <span class="badge plain muted">기준일 {e(d['asOfDate'])}</span>
  </div>
  <h1>{e(d['country']['name'])} 건축 법·제도</h1>
  <p class="one">{e(d['purpose'])}</p>
  <div class="tiles">
    <div class="tile"><b>{len(d['instruments'])}</b><span>법령·공식자료</span></div>
    <div class="tile"><b>{len(requirements)}</b><span>생애주기 의무</span></div>
    <div class="tile"><b>{len(board['nodes'])}</b><span>구조도 노드</span></div>
    <div class="tile ok"><b>{counts['confirmed']}</b><span>확정</span></div>
    <div class="tile warn"><b>{counts['conditional']}</b><span>조건부</span></div>
    <div class="tile bad"><b>{len(blockers)}</b><span>Gate 차단 질문</span></div>
  </div>
  <div class="anchor-row">
    <a href="#process-board">업무구조도</a><a href="#decisions">핵심 판단</a><a href="#blockers">Gate 질문</a><a href="#permit-path">인허가 경로</a>
    <a href="#requirements">단계별 의무</a><a href="#site-overlays">부지 특례</a><a href="#sources">법령 원문</a>
  </div>
</div>

<div class="wrap">
  <section class="blk" style="border-top:0;padding-top:12px">
    <div class="cards">
      <div class="card"><h3>파일럿 사업</h3>
        <p style="font-size:13.5px;margin:0 0 7px"><b>{e(context.get('projectName', '국가 공통 검토'))}</b></p>
        <p style="font-size:13px;color:var(--muted);margin:0">{e(context.get('location', ''))} · {e(context.get('projectType', ''))}</p>
      </div>
      <div class="card"><h3>확인된 입력</h3><ul class="plain">{known}</ul></div>
      <div class="card span2"><h3>아직 받지 못한 핵심 입력</h3><ul class="plain">{unknown}</ul></div>
    </div>
  </section>

  <section class="blk" id="process-board">
    <div class="hd-row">
      <div>
        <h2>건축 인허가 업무구조도</h2>
        <p class="desc">행위주체 × 단계 × 업무와 보완 회귀를 한 판에 표시했습니다. 각 카드의 조문은 아래 단계별 요구사항·법령 원문 대장으로 추적됩니다.</p>
      </div>
      <div class="legend">
        <span><i style="background:var(--key)"></i>핵심</span>
        <span><i style="background:var(--warn)"></i>병목</span>
        <span><i style="background:var(--back)"></i>보완 회귀</span>
      </div>
    </div>
    <figure class="studio-board-shell">
      <div class="studio-board-view"><img src="../../boards/{e(d['slug'])}-construction.svg"
        alt="{e(board['title'])}: {len(board['lanes'])}개 행위주체와 {len(board['stages'])}단계의 업무구조도"></div>
      <figcaption>
        <span>{len(board['lanes'])}개 행위주체 · {len(board['stages'])}단계 · {len(board['nodes'])}개 업무 · {len(board['edges'])}개 연결</span>
        <span><a href="https://github.com/amnotyoung/korea100studio" target="_blank" rel="noopener">korea100studio</a> gov 프로필 · <a href="../../boards/{e(d['slug'])}-construction.svg" target="_blank">SVG 크게 보기</a></span>
      </figcaption>
    </figure>
  </section>

  <section class="blk" id="decisions">
    <h2>보고서에 바로 쓸 수 있는 판단</h2>
    <p class="desc">법령 사실과 사업 적용조건을 구분했습니다. 미확정 문장은 자료가 들어오기 전까지 확정형으로 바꾸지 않습니다.</p>
    <div class="decision-list">{''.join(decisions)}</div>
  </section>

  <section class="blk" id="blockers">
    <h2>Gate 1 차단 질문</h2>
    <p class="desc">답이 없으면 부지·규모·설비·비용·일정을 확정할 수 없는 질문입니다.</p>
    <div class="blocker-grid">{''.join(blocker_cards)}</div>
  </section>

  <section class="blk" id="permit-path">
    <h2>인허가·검사 경로</h2>
    <p class="desc">법정 처리기간은 완비서류 접수 이후의 기간입니다. 환경평가·보완·기관협의·개장승인은 별도로 계획합니다.</p>
    <div class="gateflow">{gates}</div>
  </section>

  <section class="blk" id="requirements">
    <h2>단계별 법·제도 요구사항</h2>
    <p class="desc">단계를 열면 적용조건, 법적 근거, 관할기관, 확보할 증빙과 보고서 반영문구를 함께 볼 수 있습니다.</p>
    <div class="anchor-row" style="margin:0 0 14px">{anchor_links}</div>
    <div class="req-groups">{''.join(requirement_groups)}</div>
  </section>

  <section class="blk" id="site-overlays">
    <h2>{e(context.get('location', d['country']['name']))} 부지 특례</h2>
    <p class="desc">국가 공통법과 부지별 도시계획·토지·인프라 조건을 분리했습니다.</p>
    <div class="overlay-grid">{''.join(overlays)}</div>
  </section>

  {f'''<section class="blk">
    <h2>추가 확인 질문</h2>
    <p class="desc">당장 Gate를 막지는 않지만 조사·조달·운영계획에 반영해야 합니다.</p>
    <div class="data-table-wrap"><table><thead><tr><th>단계</th><th>질문</th><th>증빙</th><th>담당</th></tr></thead>
      <tbody>{other_question_rows}</tbody></table></div>
  </section>''' if non_blockers else ''}

  <section class="blk">
    <h2>현지조사 체크리스트</h2>
    <div class="data-table-wrap"><table><thead><tr><th>시점</th><th>확인할 일</th><th>산출물</th></tr></thead>
      <tbody>{checklist_rows}</tbody></table></div>
  </section>

  <section class="blk" id="sources">
    <h2>법령·공식자료 대장</h2>
    <p class="desc">현행·심의 중·안내페이지를 섞지 않고 확인 깊이를 표시합니다.</p>
    <div class="data-table-wrap"><table><thead><tr><th>자료</th><th>상태</th><th>종류</th><th>확인 조문</th><th>주의</th></tr></thead>
      <tbody>{instrument_rows}</tbody></table></div>
  </section>

  <section class="blk">
    <h2>검증범위와 한계</h2>
    <div class="cards">
      <div class="card"><h3>확인 방법</h3><p style="font-size:13px;line-height:1.7;margin:0">{e(d['verification']['method'])}</p></div>
      <div class="card"><h3>확인 범위</h3><p style="font-size:13px;line-height:1.7;margin:0">{e(d['verification']['scope'])}</p></div>
      <div class="card span2"><h3>주의</h3>{limitations}</div>
    </div>
  </section>
</div>"""

    js = """
var cs=document.getElementById('construction-country');
if(cs) cs.addEventListener('change',function(){ location.href='../'+this.value+'/index.html'; });
"""
    return page(f"{d['country']['name']} 건축 법·제도 | {SITE_TITLE}", body,
                depth=2, nav="construction", extra_js=js)


# ─────────────────────────────────────────────────────────── 검증 대장

def build_verification(items: list[dict]) -> str:
    allд = []
    for d in items:
        for x in d["verification"].get("discrepancies", []):
            allд.append((d, x))
    order = {"high": 0, "medium": 1, "low": 2}
    allд.sort(key=lambda t: order[t[1]["severity"]])
    counts = {k: sum(1 for _, x in allд if x["severity"] == k) for k in order}

    cards = "".join(disc_card(d, x, link=f"../model/{e(d['slug'])}/index.html") for d, x in allд)
    n_up = sum(1 for _, x in allд if x.get("upstream"))
    n_fix = sum(1 for _, x in allд if (x.get("upstream") or {}).get("priority") == "정정 요망")

    unres = "".join(f"""<tr>
  <td class="name" style="font-weight:600">{e(u['law'])}</td>
  <td><span class="badge plain muted">{e(d['country']['name'])}</span></td>
  <td style="font-size:13px">{e(u['reason'])}</td>
  <td style="font-size:13px;color:var(--muted)">{e(u['nextStep'])}</td>
</tr>""" for d in items for u in d["verification"].get("unresolved", []))

    body = f"""
<div class="wrap hero" style="padding-bottom:24px">
  <div class="eyebrow">공식 원문 대조</div>
  <h1>현행 기준 확인 대장</h1>
  <p class="lede">각국 공식 법령·기관 원문으로 확인한 기준과 실무 확인사항을 공개합니다.</p>
  <p class="meta">확인사항 {len(allд)}건 · 필수 확인 {counts['high']} / 추가 확인 {counts['medium']} / 참고 {counts['low']}</p>
</div>

<div class="statbar"><div class="wrap">
  <div style="font-size:13px;color:var(--muted);max-width:56ch">
    확인된 현행 기준을 산출물에 반영하고, 근거 원문과
    <b>실무 확인사항</b>을 함께 제시합니다.
  </div>
  <div class="stats">
    <div class="stat bad"><b>{counts['high']}</b><span>필수 확인</span></div>
    <div class="stat"><b>{counts['medium']}</b><span>추가 확인</span></div>
    <div class="stat"><b>{counts['low']}</b><span>참고</span></div>
    <div class="stat"><b>{len(allд)}</b><span>출처 연결</span></div>
  </div>
</div></div>

<div class="wrap">
  <section class="blk" style="border-top:0">
    <h2>현행 기준 반영사항</h2>
    <p class="desc">실무 확인 우선순위 순입니다. 필수 확인 항목은 입찰 자격·서류·절차에 직접 영향을 줄 수 있습니다.
      공식 근거는 <a href="../errata/index.html">반영 출처</a>에서 한 번에 확인할 수 있습니다.</p>
    {cards}
  </section>

  <section class="blk">
    <h2>확인하지 못한 것</h2>
    <p class="desc">원문을 구하지 못했거나 현지어로만 공개된 항목입니다.</p>
    <div class="panel"><table>
      <thead><tr><th>문서</th><th>국가</th><th>사유</th><th>다음 조치</th></tr></thead>
      <tbody>{unres}</tbody>
    </table></div>
  </section>
</div>"""
    return page(f"검증 대장 | {SITE_TITLE}", body, depth=1, nav="verify")


# ─────────────────────────────────────────────────────────── 반영 출처

def build_errata(items: list[dict]) -> str:
    """현행 기준으로 반영한 내용과 공식 출처를 한곳에 모은다."""
    rows = []
    for d in items:
        for x in d["verification"].get("discrepancies", []):
            if x.get("upstream"):
                rows.append((d, x))
    rows.sort(key=lambda t: (0 if t[1]["upstream"]["priority"] == "정정 요망" else 1,
                             {"high": 0, "medium": 1, "low": 2}[t[1]["severity"]]))
    blocks = []
    for i, (d, x) in enumerate(rows, 1):
        ref = next((r for r in d["sourceRefs"]), {})
        blocks.append(f"""<div class="disc" data-sev="{e(x['severity'])}">
  <div class="top">
    <span class="badge plain muted">{i:02d}</span>
    <span class="badge {SEV_TONE[x['severity']]}">{e(SEV_LABEL[x['severity']])}</span>
    <span class="badge plain muted">{e(d['country']['name'])}</span>
    <span class="badge plain muted">{e(ref.get('pages', ''))}쪽 · {e(ref.get('section', ''))}</span>
  </div>
  <h3>{e(x['field'])}</h3>
  <div class="quote act"><b>현행 기준</b>{el(x['actualText'])}</div>
  <p class="cite">확인 출처 · {cite_link(d, x['citation'])}</p>
  <p class="act-row">산출물 반영 — {el(x['action'])}</p>
  <p class="act-row"><a href="../model/{e(d['slug'])}/index.html">{e(d['name'])}</a> · {e(x['id'])}</p>
</div>""")

    body = f"""
<div class="wrap hero" style="padding-bottom:24px">
  <div class="eyebrow">공식 원문 대조</div>
  <h1>현행 기준 반영 출처</h1>
  <p class="lede">외부 공식 자료로 확인해 산출물에 반영한 기준과 출처를 모았습니다.</p>
  <p class="meta">반영사항 {len(rows)}건 · 각 항목에서 공식 원문 확인 가능</p>
</div>

<div class="statbar"><div class="wrap">
  <div style="font-size:13px;color:var(--muted);max-width:70ch">
    각 항목은 <b>현행 기준 → 확인 출처 → 산출물 반영 내용</b> 순으로 정리했습니다.
    실제 입찰에서는 연결된 공식 원문과 발주처 공고를 다시 확인해야 합니다.
  </div>
  <div class="stats">
    <div class="stat ok"><b>{len(rows)}</b><span>출처 확인</span></div>
  </div>
</div></div>

<div class="wrap">
  <section class="blk" style="border-top:0">
    {''.join(blocks)}
  </section>
</div>"""
    return page(f"현행 기준 반영 출처 | {SITE_TITLE}", body, depth=1, nav="errata")


# ─────────────────────────────────────────────────────────── 배포용 단일 파일

def build_bundle(country_key: str, country_name: str, items: list[dict]) -> str:
    """한 국가의 제도들을 네비게이션 없는 자족 단일 HTML로 묶는다.

    각 제도를 standalone HTML로 만들어 iframe srcdoc에 임베드한다 — iframe이
    JS 스코프를 격리하므로 여러 제도의 업무구조도·drawer가 서로 충돌하지 않는다.
    외부 리소스 요청이 전혀 없어(모두 인라인·srcdoc) 파일 하나로 오프라인에서 열린다.
    """
    docs = [d for d in items if country_slug(d) == country_key]
    docs.sort(key=lambda d: d["priority"])
    if not docs:
        return ""
    has_construction = any(d["axis"] == "construction" for d in docs)
    bundle_label = "조달·건축 제도" if has_construction else "공공조달 제도"
    bundle_subtitle = (
        "조달 1~3번과 건축 4번부터를 같은 형식으로 정리한 한 장 요약"
        if has_construction else
        "KOICA 2026 참여전략 자료집과 각국 공식 원문을 바탕으로 정리한 한 장 요약"
    )
    bundle_warning = (
        "조달·건축 법령은 개정이 잦으므로 실제 입찰·설계·인허가 전 발주처 공고문과 현행 법령을 확인해야 합니다."
        if has_construction else
        "조달법은 개정이 잦으므로 실제 입찰 전 발주처 공고문과 현행 법령을 확인해야 합니다."
    )

    tabs, frames = [], []
    for i, d in enumerate(docs):
        inner = build_detail(d, items, standalone=True)
        srcdoc = html.escape(inner, quote=True)
        active = " active" if i == 0 else ""
        tab_label = AXIS_LABEL[d["axis"]]
        if d["axis"] == "construction":
            tab_label = d["name"].removeprefix(f'{d["country"]["name"]} ')
        tabs.append(
            f'<button class="tab{active}" data-i="{i}" onclick="showTab({i})">'
            f'{e(tab_label)}</button>')
        frames.append(
            f'<iframe class="fr{active}" data-i="{i}" title="{e(d["name"])}" '
            f'loading="{"eager" if i == 0 else "lazy"}" srcdoc="{srcdoc}"></iframe>')

    asof = max(d["asOfDate"] for d in docs)
    return f"""<!doctype html>
<html lang="ko"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(country_name)} {e(bundle_label)} | {e(SITE_TITLE)}</title>
<style>
*,*::before,*::after{{box-sizing:border-box}}
:root{{color-scheme:light dark}}
body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Pretendard","Noto Sans KR",sans-serif;
  background:#f4f5f7;color:#16181d}}
@media (prefers-color-scheme:dark){{body{{background:#0b0d11;color:#e8eaed}}}}
.top{{position:sticky;top:0;z-index:10;background:inherit;border-bottom:1px solid rgba(128,128,128,.25);
  padding:12px 18px 0}}
.top h1{{font-size:16px;margin:0 0 2px;letter-spacing:-.02em}}
.top .sub{{font-size:12px;color:#6b7280;margin:0 0 10px}}
@media (prefers-color-scheme:dark){{.top .sub{{color:#9aa3af}}}}
.tabs{{display:flex;gap:4px;flex-wrap:wrap}}
.tab{{font:inherit;font-size:13.5px;font-weight:600;border:1px solid transparent;border-bottom:none;
  background:none;color:#6b7280;padding:9px 15px;border-radius:8px 8px 0 0;cursor:pointer}}
.tab:hover{{color:inherit}}
.tab.active{{color:#157f3d;background:#fff;border-color:rgba(128,128,128,.25)}}
@media (prefers-color-scheme:dark){{.tab.active{{color:#4ade80;background:#0f1115}}}}
.frames{{background:#fff}}
@media (prefers-color-scheme:dark){{.frames{{background:#0f1115}}}}
.fr{{display:none;width:100%;border:0;min-height:80vh}}
.fr.active{{display:block}}
.foot{{font-size:11.5px;color:#6b7280;padding:14px 18px;line-height:1.7}}
</style>
</head><body>
<div class="top">
  <h1>{e(country_name)} {e(bundle_label)}</h1>
  <p class="sub">{e(bundle_subtitle)} · 기준일 {e(asof)}</p>
  <div class="tabs">{''.join(tabs)}</div>
</div>
<div class="frames">{''.join(frames)}</div>
<div class="foot">
  자료집 기준일 기준으로 작성된 참고자료입니다. 법률 자문이나 해당국 정부·KOICA의 공식 해석이 아닙니다.
  {e(bundle_warning)}
</div>
<script>
function fit(fr){{ try{{ fr.style.height=(fr.contentWindow.document.body.scrollHeight+20)+'px'; }}catch(e){{}} }}
function showTab(i){{
  document.querySelectorAll('.tab').forEach(function(t){{ t.classList.toggle('active', +t.dataset.i===i); }});
  document.querySelectorAll('.fr').forEach(function(fr){{
    var on=+fr.dataset.i===i; fr.classList.toggle('active', on);
    if(on){{ try{{ fr.contentWindow.draw && fr.contentWindow.draw(); }}catch(e){{}} setTimeout(function(){{fit(fr);}},60); }}
  }});
}}
document.querySelectorAll('.fr').forEach(function(fr){{
  fr.addEventListener('load', function(){{
    // iframe 안의 테마 토글·업무구조도가 부모 테마를 따르도록, 그리고 높이를 맞춘다
    fit(fr);
    if(fr.classList.contains('active')) setTimeout(function(){{ try{{fr.contentWindow.draw&&fr.contentWindow.draw();}}catch(e){{}} fit(fr); }},80);
  }});
}});
addEventListener('resize', function(){{ var a=document.querySelector('.fr.active'); if(a) fit(a); }});
</script>
</body></html>"""


# ─────────────────────────────────────────────────────────── main

def main() -> int:
    procurement_items = []
    for f in sorted(INST_DIR.glob("*.json")):
        procurement_items.append(json.loads(f.read_text(encoding="utf-8")))
    if not procurement_items:
        print("제도 데이터가 없습니다.")
        return 1

    construction_items = []
    for f in sorted(CONSTRUCTION_DIR.glob("*.json")):
        if f.name == "manifest.json":
            continue
        construction_items.append(json.loads(f.read_text(encoding="utf-8")))
    construction_items.sort(key=lambda d: country_name_sort_key(d["country"]["name"]))

    construction_models = [
        model
        for item in construction_items
        for model in construction_to_models(item)
    ]
    items = procurement_items + construction_models
    items.sort(key=lambda d: (country_name_sort_key(d["country"]["name"]), d["priority"]))

    if SITE.exists():
        shutil.rmtree(SITE)
    (SITE / "model").mkdir(parents=True)
    (SITE / "verification").mkdir(parents=True)
    (SITE / "errata").mkdir(parents=True)
    (SITE / "construction").mkdir(parents=True)

    (SITE / "index.html").write_text(
        clean_generated_html(build_index(items)), encoding="utf-8"
    )
    (SITE / "verification" / "index.html").write_text(
        clean_generated_html(build_verification(items)), encoding="utf-8"
    )
    (SITE / "errata" / "index.html").write_text(
        clean_generated_html(build_errata(items)), encoding="utf-8"
    )
    for d in items:
        out = SITE / "model" / d["slug"]
        out.mkdir(parents=True, exist_ok=True)
        (out / "index.html").write_text(
            clean_generated_html(build_detail(d, items)), encoding="utf-8"
        )
    if construction_items:
        (SITE / "construction" / "index.html").write_text(
            clean_generated_html(redirect_page(
                "../index.html?axis=construction",
                f"건축 법·제도 | {SITE_TITLE}",
            )),
            encoding="utf-8",
        )
        for d in construction_items:
            country_models = [
                item for item in construction_models if item["countryKey"] == d["slug"]
            ]
            primary_model = min(country_models, key=lambda item: item["priority"])
            out = SITE / "construction" / d["slug"]
            out.mkdir(parents=True, exist_ok=True)
            (out / "index.html").write_text(
                clean_generated_html(redirect_page(
                    f'../../model/{primary_model["slug"]}/index.html',
                    f'{d["country"]["name"]} 건축 법·제도 | {SITE_TITLE}',
                )),
                encoding="utf-8",
            )
            legacy_slug = f'{d["slug"]}-construction-regulations'
            if legacy_slug != primary_model["slug"]:
                legacy_out = SITE / "model" / legacy_slug
                legacy_out.mkdir(parents=True, exist_ok=True)
                (legacy_out / "index.html").write_text(
                    clean_generated_html(redirect_page(
                        f'../{primary_model["slug"]}/index.html',
                        f'{d["country"]["name"]} 건축 법·제도 | {SITE_TITLE}',
                    )),
                    encoding="utf-8",
                )

    n = len(list(SITE.rglob("*.html")))
    print(f"빌드 완료 — {n}개 페이지")
    print(f"  {SITE}/index.html")
    print(f"  {SITE}/verification/index.html")
    if construction_items:
        print(f"  {SITE}/construction/index.html  (통합 대장으로 이동)")
        for d in construction_items:
            print(f"  {SITE}/construction/{d['slug']}/index.html  (첫 건축 model로 이동)")
    for d in items:
        print(f"  {SITE}/model/{d['slug']}/index.html")

    # 배포용 단일 파일 — 국가별로 dist/{country}.html 생성 (네비 없는 자족 파일)
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    countries = {}  # country_slug(= 제도 slug 접두) → 국가 한글명
    for d in items:
        countries[country_slug(d)] = d["country"]["name"]
    print("\n배포용 단일 파일 (dist/):")
    for country_key, country_name in sorted(countries.items()):
        html_str = build_bundle(country_key, country_name, items)
        if not html_str:
            continue
        out = dist / f"{country_key}.html"
        out.write_text(clean_generated_html(html_str), encoding="utf-8")
        size_kb = len(html_str.encode("utf-8")) // 1024
        print(f"  {out}  ({size_kb}KB, 자족·오프라인)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
