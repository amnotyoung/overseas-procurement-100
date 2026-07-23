#!/usr/bin/env python3
"""data/institutions/*.json을 docs/data-contract.md 규칙으로 검증한다.

사용법:
    python3 tools/validate.py
종료코드 0 = 통과, 1 = 오류 있음
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INST_DIR = ROOT / "data" / "institutions"

AXES = {"bidding", "governance", "pipeline"}
AXIS_SUFFIX = {
    "bidding": "-bidding-system",
    "governance": "-procurement-governance",
    "pipeline": "-oda-project-pipeline",
}
LEGAL_KINDS = {
    "act", "regulation", "ordinance", "directive",
    "standard-document", "treaty-agreement", "donor-rule", "practice",
}
VERIF_STATUS = {"source-document", "law-linked", "article-verified", "needs-review"}
NODE_TYPES = {"task", "gateway", "notice", "system"}
NODE_STATUS = {"done", "current", "waiting", "risk", "loop"}
EDGE_TYPES = {"sequence", "message", "loop"}
SEVERITIES = {"high", "medium", "low"}
UPSTREAM_PRIORITY = {"정정 요망", "보완 권고"}
UPSTREAM_STATE = {"not-reported", "reported", "acknowledged", "fixed", "declined"}
REASON_CODES = {
    "no-public-text", "local-language-only", "paywalled",
    "donor-internal", "site-unreachable", "title-needs-confirmation",
}

errors: list[str] = []
warnings: list[str] = []


def err(slug: str, msg: str) -> None:
    errors.append(f"  [ERROR] {slug}: {msg}")


def warn(slug: str, msg: str) -> None:
    warnings.append(f"  [WARN ] {slug}: {msg}")


def check(path: Path) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        errors.append(f"  [ERROR] {path.name}: JSON 파싱 실패 — {e}")
        return

    slug = data.get("slug", path.stem)

    # --- 기본 메타데이터 ---
    for field in ("slug", "name", "oneLiner", "axis", "type", "priority", "asOfDate", "status"):
        if field not in data:
            err(slug, f"필수 필드 누락: {field}")

    axis = data.get("axis")
    if axis not in AXES:
        err(slug, f"axis가 3축이 아님: {axis!r}")
    elif not slug.endswith(AXIS_SUFFIX[axis]):
        err(slug, f"slug가 axis({axis}) 접미사 {AXIS_SUFFIX[axis]!r}로 끝나지 않음")

    if data.get("status") not in {"full", "canvas"}:
        err(slug, f"status는 full|canvas 여야 함: {data.get('status')!r}")

    if path.stem != slug:
        err(slug, f"파일명({path.stem})과 slug가 불일치")

    # --- country ---
    country = data.get("country")
    if not isinstance(country, dict):
        err(slug, "country 블록 누락")
    else:
        for field in ("name", "nameEn", "iso3", "region"):
            if not country.get(field):
                err(slug, f"country.{field} 누락")
        if country.get("iso3") and len(country["iso3"]) != 3:
            err(slug, f"country.iso3는 3자리여야 함: {country['iso3']!r}")

    # --- canvas ---
    canvas = data.get("canvas")
    if not isinstance(canvas, dict):
        err(slug, "canvas 블록 누락")
        canvas = {}

    for field in ("purpose", "stakeholders", "legalBasis", "authorities",
                  "procedure", "applicability", "submittedDocuments", "bottlenecks"):
        if field not in canvas:
            err(slug, f"canvas.{field} 누락")

    proc = canvas.get("procedure", [])
    if isinstance(proc, list) and not (6 <= len(proc) <= 12):
        warn(slug, f"canvas.procedure 길이 {len(proc)} — 계약 권장 6~10(최대 12)")

    for i, lb in enumerate(canvas.get("legalBasis", [])):
        if lb.get("kind") not in LEGAL_KINDS:
            err(slug, f"canvas.legalBasis[{i}].kind가 8종 밖: {lb.get('kind')!r}")
        if not lb.get("law"):
            err(slug, f"canvas.legalBasis[{i}].law 누락")
        if lb.get("url") and not str(lb["url"]).startswith(("http://", "https://")):
            err(slug, f"canvas.legalBasis[{i}].url이 스킴 없이 기재됨: {lb['url']!r}")

    for i, a in enumerate(canvas.get("authorities", [])):
        if not a.get("name") or not a.get("role"):
            err(slug, f"canvas.authorities[{i}]에 name/role 누락")
        if a.get("url") and not str(a["url"]).startswith(("http://", "https://")):
            err(slug, f"canvas.authorities[{i}].url이 스킴 없이 기재됨: {a['url']!r}")

    for i, d in enumerate(canvas.get("submittedDocuments", [])):
        if not d.get("actor") or not isinstance(d.get("documents"), list):
            err(slug, f"canvas.submittedDocuments[{i}] 형식 오류")

    # practice로 분류한 근거는 fieldVerification에 등재돼 있어야 함
    fv = data.get("fieldVerification")
    if not isinstance(fv, list):
        err(slug, "fieldVerification 배열 누락")
        fv = []
    has_practice = any(lb.get("kind") == "practice" for lb in canvas.get("legalBasis", []))
    if has_practice and not fv:
        err(slug, "legalBasis에 practice가 있으나 fieldVerification이 비어 있음")

    if not isinstance(data.get("related"), list):
        err(slug, "related 배열 누락")

    # --- sourceQuotes (선택이지만 있으면 규칙 준수) ---
    sq = data.get("sourceQuotes")
    if sq is not None:
        if not isinstance(sq, list):
            err(slug, "sourceQuotes는 배열이어야 함")
        else:
            source_laws = {s.get("law") for s in data.get("verification", {}).get("sources", [])}
            for i, q in enumerate(sq):
                for field in ("law", "article", "quote", "gist"):
                    if not q.get(field):
                        err(slug, f"sourceQuotes[{i}].{field} 누락")
                # quote는 원문이므로 최소 길이 확인(요약이 아니라 verbatim이어야)
                if q.get("quote") and len(q["quote"]) < 20:
                    warn(slug, f"sourceQuotes[{i}] quote가 너무 짧음 — verbatim 원문인지 확인")
                # law가 verification.sources와 연결되는지 (URL 자동 연결 조건)
                if q.get("law") and q["law"] not in source_laws:
                    warn(slug, f"sourceQuotes[{i}].law가 verification.sources에 없음 — 원문 URL 연결 안 됨: {q['law']!r}")

    # --- sourceRefs ---
    refs = data.get("sourceRefs")
    if not isinstance(refs, list) or not refs:
        err(slug, "sourceRefs가 비어 있음 — 자료집 역추적 불가")
    else:
        for i, r in enumerate(refs):
            for field in ("document", "pages", "section"):
                if not r.get(field):
                    err(slug, f"sourceRefs[{i}].{field} 누락")

    # --- verification ---
    v = data.get("verification")
    if not isinstance(v, dict):
        err(slug, "verification 블록 누락")
    else:
        if v.get("status") not in VERIF_STATUS:
            err(slug, f"verification.status가 4종 밖: {v.get('status')!r}")
        for field in ("verifiedAt", "method", "scope"):
            if not v.get(field):
                err(slug, f"verification.{field} 누락")

        srcs = v.get("sources", [])
        if not srcs:
            err(slug, "verification.sources가 비어 있음")
        for i, s in enumerate(srcs):
            if not s.get("officialUrl"):
                err(slug, f"verification.sources[{i}].officialUrl 누락")
            if not s.get("retrievedOn"):
                err(slug, f"verification.sources[{i}].retrievedOn 누락")
            if s.get("kind") not in LEGAL_KINDS:
                err(slug, f"verification.sources[{i}].kind가 8종 밖: {s.get('kind')!r}")

        # status가 article-verified면 최소 1개 source에 articlesChecked가 있어야 함
        if v.get("status") == "article-verified":
            if not any(s.get("articlesChecked") for s in srcs):
                err(slug, "status=article-verified인데 articlesChecked를 기재한 source가 없음")

        for i, d in enumerate(v.get("discrepancies", [])):
            for field in ("id", "severity", "field", "sourceText", "actualText",
                          "citation", "impact", "action", "userAction"):
                if not d.get(field):
                    err(slug, f"verification.discrepancies[{i}].{field} 누락")
            if d.get("severity") not in SEVERITIES:
                err(slug, f"discrepancies[{i}].severity가 3종 밖: {d.get('severity')!r}")
            if d.get("id") and not d["id"].startswith(slug):
                err(slug, f"discrepancies[{i}].id가 slug로 시작하지 않음: {d['id']!r}")

            up = d.get("upstream")
            if up is not None:
                if up.get("priority") not in UPSTREAM_PRIORITY:
                    err(slug, f"discrepancies[{i}].upstream.priority가 목록 밖: {up.get('priority')!r}")
                if up.get("state") not in UPSTREAM_STATE:
                    err(slug, f"discrepancies[{i}].upstream.state가 목록 밖: {up.get('state')!r}")
                if not up.get("suggestedText"):
                    err(slug, f"discrepancies[{i}].upstream.suggestedText 누락 — 대안 문안 없이 정정 요청 불가")
            elif d.get("severity") == "high":
                # high인데 발행처 조치가 없다면 판단을 미룬 것일 가능성이 높다
                warn(slug, f"discrepancies[{i}]({d.get('id')})는 severity=high인데 upstream이 없음 — "
                           f"발행처 정정이 정말 불필요한지 확인")

        for i, u in enumerate(v.get("unresolved", [])):
            if u.get("reasonCode") not in REASON_CODES:
                err(slug, f"unresolved[{i}].reasonCode가 목록 밖: {u.get('reasonCode')!r}")
            for field in ("law", "reason", "nextStep"):
                if not u.get(field):
                    err(slug, f"unresolved[{i}].{field} 누락")

    # --- process ---
    process = data.get("process")
    if data.get("status") == "full" and not process:
        err(slug, "status=full인데 process 블록이 없음")

    if isinstance(process, dict):
        lanes = set(process.get("lanes", []))
        stages = set(process.get("stages", []))
        if not lanes:
            err(slug, "process.lanes 비어 있음")
        if not stages:
            err(slug, "process.stages 비어 있음")

        node_ids: set[str] = set()
        for n in process.get("nodes", []):
            nid = n.get("id", "?")
            if nid in node_ids:
                err(slug, f"노드 ID 중복: {nid}")
            node_ids.add(nid)
            if n.get("lane") not in lanes:
                err(slug, f"노드 {nid}의 lane이 선언 목록 밖: {n.get('lane')!r}")
            if n.get("stage") not in stages:
                err(slug, f"노드 {nid}의 stage가 선언 목록 밖: {n.get('stage')!r}")
            if n.get("type") not in NODE_TYPES:
                err(slug, f"노드 {nid}의 type이 목록 밖: {n.get('type')!r}")
            if n.get("status") not in NODE_STATUS:
                err(slug, f"노드 {nid}의 status가 목록 밖: {n.get('status')!r}")
            if not n.get("actor"):
                err(slug, f"노드 {nid}에 actor 누락")
            c = n.get("confidence")
            if c is not None and not (0 <= c <= 1):
                err(slug, f"노드 {nid}의 confidence가 0~1 밖: {c}")
            if c is not None and c < 0.8 and nid not in {x.get("id") for x in process.get("nodes", []) if x.get("blocker")}:
                pass  # confidence<0.8은 UI에서 '현장 검증 필요' 배지로 처리. 오류 아님.

        edge_ids: set[str] = set()
        for e in process.get("edges", []):
            eid = e.get("id", "?")
            if eid in edge_ids:
                err(slug, f"엣지 ID 중복: {eid}")
            edge_ids.add(eid)
            if e.get("source") not in node_ids:
                err(slug, f"엣지 {eid}의 source가 유효하지 않음: {e.get('source')!r}")
            if e.get("target") not in node_ids:
                err(slug, f"엣지 {eid}의 target이 유효하지 않음: {e.get('target')!r}")
            if e.get("type") not in EDGE_TYPES:
                err(slug, f"엣지 {eid}의 type이 목록 밖: {e.get('type')!r}")

        # 고립 노드 탐지
        connected = {e.get("source") for e in process.get("edges", [])} | \
                    {e.get("target") for e in process.get("edges", [])}
        for nid in node_ids - connected:
            warn(slug, f"노드 {nid}가 어떤 엣지에도 연결되지 않음")

        # 선언만 하고 쓰이지 않는 레인/게이트 — 업무구조도에 빈 행/열로 렌더링된다
        used_lanes = {n.get("lane") for n in process.get("nodes", [])}
        used_stages = {n.get("stage") for n in process.get("nodes", [])}
        for lane in lanes - used_lanes:
            err(slug, f"레인 {lane!r}을 선언했으나 해당 레인의 노드가 없음 (구조도에 빈 행이 생김)")
        for st in stages - used_stages:
            err(slug, f"게이트 {st!r}를 선언했으나 해당 단계의 노드가 없음 (구조도에 빈 열이 생김)")


def main() -> int:
    files = sorted(INST_DIR.glob("*.json"))
    if not files:
        print(f"검증할 파일이 없습니다: {INST_DIR}")
        return 1

    slugs = set()
    for f in files:
        check(f)
        try:
            slugs.add(json.loads(f.read_text(encoding="utf-8")).get("slug"))
        except json.JSONDecodeError:
            pass

    # related 상호참조 검사
    for f in files:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for r in d.get("related", []):
            if r not in slugs:
                warn(d.get("slug", f.stem), f"related의 {r!r}가 아직 작성되지 않음")

    print(f"검증 대상: {len(files)}개 제도\n")
    if warnings:
        print("경고")
        print("\n".join(warnings))
        print()
    if errors:
        print("오류")
        print("\n".join(errors))
        print(f"\n실패 — 오류 {len(errors)}건, 경고 {len(warnings)}건")
        return 1

    print(f"통과 — 오류 0건, 경고 {len(warnings)}건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
