"""기관 역할과 단계별로 명시적으로 선택한 자료를 검증한다."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
ROLE_ACTORS = {
    "개찰·적격심사": "공고상 개찰·적격심사 담당기관",
    "평가·낙찰": "공고상 평가·낙찰 권한기관",
    "조달방식·서류 검토": "해당 조달의 방식·서류 심사기관",
    "공고·전자조달 게시": "발주기관의 공고 담당부서",
    "절차 감독·감사": "해당 조달의 감독·감사기관",
    "이의·분쟁 처리": "해당 심급의 이의심사기관",
    "국가 우선순위 검토": "사업유형별 우선순위 심사기관",
    "공식 사업요청": "사업유형별 공식 요청기관",
    "RD·MOU 공식화": "해당 협정의 양측 서명권자",
}
REQUIREMENTS = {
    "thresholds": "조달방식·기준금액",
    "deadlines": "기한",
    "bidSecurity": "입찰보증",
    "performanceSecurity": "계약이행보증",
    "complaints": "이의·구제",
    "exceptions": "예외 적용",
}
GENERATED_REASONS = {
    "강화 검증에서 확인한 해당 요건의 공식 조문과 직접 연결",
    "현행 공식 원문의 적용범위·절차 조문과 연결",
    "공식 공여기관 자료를 현행 법령과 교차확인한 절차",
}


def web_url(value):
    if not isinstance(value, str):
        return False
    parsed = urlsplit(value)
    return parsed.scheme in {"https", "http"} and bool(parsed.netloc)


def assigned_actor(data, node):
    names = [a["name"] for a in data["canvas"]["authorities"]
             if node["id"] in a.get("processNodes", [])]
    if names:
        return " · ".join(names)
    if node.get("actorScope") == "role":
        return ROLE_ACTORS.get(node["name"], node["lane"])
    return None


def canvas_projections(data):
    canvas = data["canvas"]
    result = {}
    if canvas.get("stakeholdersFromAuthorities"):
        names = [a["name"] for a in canvas["authorities"]]
        participants = ["수원부처", "KOICA"] if data["axis"] == "pipeline" else ["발주기관", "입찰자"]
        result["stakeholders"] = ", ".join(dict.fromkeys(names + participants))
    if canvas.get("procedureFromNodes"):
        result["procedure"] = [
            f"{i}. {node['name']} · {node['actor']} — {node['action']}"
            + (" (단계 근거 확인 필요)" if node.get("basisStatus") == "pending" else "")
            for i, node in enumerate(data["process"]["nodes"], 1)
        ]
    return result


def guide_error(data, guide):
    suffix = {"pipeline": "-oda-project-pipeline", "bidding": "-bidding-system",
              "governance": "-procurement-governance"}.get(data.get("axis"))
    if not suffix or not isinstance(guide, dict) or not isinstance(guide.get("path"), str):
        return "guideRef.path"
    country = data["slug"].removesuffix(suffix)
    path = Path(guide["path"])
    if (len(path.parts) != 4 or path.parts[:2] != ("sources", "koica-2026")
            or path.parts[2] == ".." or path.name != country + ".txt" or not (ROOT / path).is_file()):
        return "guideRef.path"
    start, end = guide.get("start"), guide.get("end")
    lines = (ROOT / path).read_text(encoding="utf-8").splitlines()
    if not (type(start) is int and type(end) is int and 1 <= start <= end <= len(lines)):
        return "guideRef.range"
    excerpt = " ".join(line.strip() for line in lines[start - 1:end] if line.strip())
    if not excerpt or guide.get("excerpt") != excerpt:
        return "guideRef.excerpt"
    return None


def node_errors(data, node):
    problems = []
    actor = assigned_actor(data, node)
    scope = node.get("actorScope")
    if scope not in (None, "role", "authority") or (scope == "authority" and not actor):
        problems.append("actorScope")
    if actor and node.get("actor") != actor:
        problems.append("actor")
    if scope == "role" and actor != ROLE_ACTORS.get(node["name"], node["lane"]):
        problems.append("actorScope")
    if node.get("confidence_reason") in GENERATED_REASONS:
        problems.append("automatic-confidence")
    bases = node.get("legal_basis", [])
    if not isinstance(bases, list):
        return problems + ["legal_basis"]
    for basis in bases:
        if not (isinstance(basis, dict) and basis.get("law") and basis.get("article") and web_url(basis.get("url"))):
            problems.append("legal_basis")
    if "confidence" in node:
        score = node["confidence"]
        if type(score) not in (int, float) or not 0 <= score <= 1 or not node.get("confidence_reason"):
            problems.append("confidence")
    if not bases and ("confidence" in node or "confidence_reason" in node):
        problems.append("confidence-without-node-basis")

    guide = node.get("guideRef")
    if "guideRef" in node:
        problem = guide_error(data, guide)
        if problem:
            problems.append(problem)
    requirements = data["verification"].get("articleAudit", {}).get("requirements", {})
    keys = node.get("requirementRefs", [])
    if not isinstance(keys, list):
        return problems + ["requirementRefs"]
    for key in keys:
        if not isinstance(key, str) or key not in REQUIREMENTS:
            problems.append("requirementRefs")
            continue
        ref = requirements.get(key, {})
        if ref.get("status") != "confirmed" or not web_url(ref.get("evidenceUrl")):
            problems.append("requirementRefs")
    has_source = bool(bases or guide or keys)
    if has_source and "basisStatus" in node or not has_source and node.get("basisStatus") != "pending":
        problems.append("basisStatus")
    return problems
