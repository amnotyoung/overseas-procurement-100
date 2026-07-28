#!/usr/bin/env python3
"""data/institutions/*.json → 현행 기준 확인 문서 생성.

확인사항은 JSON을 단일 출처로 삼고, 공개 문서는 그 내용을 중립적으로 옮긴다.

사용법:
    python3 tools/build_docs.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INST_DIR = ROOT / "data" / "institutions"
DOCS = ROOT / "docs"

SEV_LABEL = {"high": "필수 확인", "medium": "추가 확인", "low": "참고"}
SEV_ORDER = {"high": 0, "medium": 1, "low": 2}
UP_STATE = {
    "not-reported": "미제보",
    "reported": "제보함 · 회신 대기",
    "acknowledged": "발행처 확인",
    "fixed": "개정판 반영",
    "declined": "정정 불요 회신",
}
VERIF_LABEL = {
    "article-verified": "조문 대조 완료",
    "law-linked": "원문 링크 연결",
    "source-document": "자료집 기재",
    "needs-review": "재검토 필요",
}


def load() -> list[dict]:
    items = [json.loads(f.read_text(encoding="utf-8")) for f in sorted(INST_DIR.glob("*.json"))]
    items.sort(key=lambda d: (d["country"]["name"], d["priority"]))
    return items


def build_verification_log(items: list[dict]) -> str:
    rows = [(d, x) for d in items for x in d["verification"].get("discrepancies", [])]
    rows.sort(key=lambda t: (SEV_ORDER[t[1]["severity"]], t[0]["slug"]))
    counts = {k: sum(1 for _, x in rows if x["severity"] == k) for k in SEV_ORDER}
    n_up = sum(1 for _, x in rows if x.get("upstream"))
    n_fix = sum(1 for _, x in rows if (x.get("upstream") or {}).get("priority") == "정정 요망")
    verified = max((d["verification"]["verifiedAt"] for d in items), default="")
    countries = sorted({d["country"]["name"] for d in items})

    L: list[str] = []
    a = L.append
    a("# 현행 기준 확인 대장")
    a("")
    a("> 이 문서는 `tools/build_docs.py`가 `data/institutions/*.json`에서 생성한다. 직접 고치지 말 것.")
    a("")
    a("각국 공식 법령·기관 원문으로 확인한 현행 기준과 실무 확인사항을 공개한다.")
    a("")
    a(f"- 기준일: {verified}")
    a(f"- 대상: {len(items)}개 제도 ({', '.join(countries)})")
    a(f"- 결과: **확인사항 {len(rows)}건 — 필수 확인 {counts['high']} / 추가 확인 {counts['medium']} / 참고 {counts['low']}**")
    n_office = sum(1 for _, x in rows if (x.get("fieldCheck") or {}).get("status")
                   in ("confirmed", "refuted", "partial"))
    a(f"- 공식 출처가 연결된 반영사항: **{n_up}건** → [반영 출처](errata.md)")
    a(f"- 사무소 현장 확인: **{n_office}/{len(rows)}건** 회신됨 → [영어 검토 시트](review-sheet.en.md)")
    a("")
    a("## 제도별 검증 상태")
    a("")
    a("| 제도 | 국가 | 검증 | 확인사항 | 사무소 확인 | 확인일 |")
    a("|---|---|---|---|---|---|")
    for d in items:
        v = d["verification"]
        ds = v.get("discrepancies", [])
        hi = sum(1 for x in ds if x["severity"] == "high")
        office = sum(1 for x in ds if (x.get("fieldCheck") or {}).get("status")
                     in ("confirmed", "refuted", "partial"))
        reviewable = sum(1 for x in ds if x.get("review"))
        office_cell = f"{office}/{reviewable}" if reviewable else "—"
        a(f"| [{d['name']}](../data/institutions/{d['slug']}.json) | {d['country']['name']} | "
          f"{VERIF_LABEL[v['status']]} | {len(ds)}건{f' (필수 확인 {hi})' if hi else ''} | {office_cell} | {v['verifiedAt']} |")
    a("")
    a("---")
    a("")

    for sev in ("high", "medium", "low"):
        group = [(d, x) for d, x in rows if x["severity"] == sev]
        if not group:
            continue
        head = {"high": "필수 확인 — 입찰 자격·서류·절차에 직접 영향을 줄 수 있는 것",
                "medium": "추가 확인 — 원문 또는 발주처 확인이 필요한 것",
                "low": "참고 — 출처·표기 보완"}[sev]
        a(f"## {head}")
        a("")
        for d, x in group:
            a(f"### {x['field']}")
            a("")
            a(f"- 제도: [{d['name']}](../data/institutions/{d['slug']}.json) · `{x['id']}`")
            a(f"- 근거: {x['citation']}")
            fc = x.get("fieldCheck")
            if fc:
                fc_ko = {"confirmed": "✔ 확인됨", "refuted": "✗ 반증됨(우리 판단 오류)",
                         "partial": "◐ 부분 확인", "pending": "… 확인 중"}
                a(f"- 사무소 확인: **{fc_ko.get(fc['status'], fc['status'])}** · "
                  f"{fc['checkedBy']} · {fc['checkedOn']} — {fc['finding']}")
            elif x.get("review"):
                a("- 사무소 확인: 미회신 (영어 검토 시트에 확인 대기)")
            a("")
            a("**현행 기준**")
            a("")
            a(f"> {x['actualText']}")
            a("")
            a(f"**실무 확인** — {x['userAction']}")
            a("")
            a(f"*산출물 반영* — {x['action']}")
            a("")
        a("---")
        a("")

    a("## 확인하지 못한 것")
    a("")
    a("| 문서 | 제도 | 사유 | 다음 조치 |")
    a("|---|---|---|---|")
    for d in items:
        for u in d["verification"].get("unresolved", []):
            a(f"| {u['law']} | {d['country']['name']} | {u['reason']} | {u['nextStep']} |")
    a("")

    notes = [(d, n) for d in items for n in d["verification"].get("notes", [])]
    if notes:
        a("## 주의")
        a("")
        for d, n in notes:
            a(f"- **{d['name']}** — {n}")
        a("")

    a("---")
    a("")
    a("## 방법론")
    a("")
    a("1. 기준자료에서 인용 조문을 **전부** 뽑는다.")
    a("2. 해당국 법령 **영문 원문을 확보**하고, 조문 목록을 먼저 뽑아 **총 조문 수를 확인**한다.")
    a("   — 네팔 건은 이 단계에서 법률과 시행규칙의 조문 체계를 구분했다.")
    a("3. 인용 조문을 **하나씩 대조**한다. 조문 제목·문언·수치를 본다.")
    a("4. 수치는 반드시 원문 표와 맞춘다.")
    a("5. 공식 원문에서 추가 실무 의무와 적용 조건도 확인한다.")
    a("6. **근거 문서가 아직 살아 있는지 확인한다.** 폐지·개정됐으면 대조 자체가 무의미해진다.")
    a("7. 확인된 현행 기준은 근거 출처와 함께 산출물에 반영한다.")
    a("")
    return "\n".join(L)


def build_errata(items: list[dict]) -> str:
    rows = [(d, x) for d in items for x in d["verification"].get("discrepancies", [])
            if x.get("upstream")]
    rows.sort(key=lambda t: (0 if t[1]["upstream"]["priority"] == "정정 요망" else 1,
                             SEV_ORDER[t[1]["severity"]]))
    n_fix = sum(1 for _, x in rows if x["upstream"]["priority"] == "정정 요망")
    verified = max((d["verification"]["verifiedAt"] for d in items), default="")
    # 공개 반영 출처에는 공식 원문으로 확인해 실제 반영한 항목만 적는다.
    docs_used = {r["document"] for d, _ in rows for r in d["sourceRefs"]}

    L: list[str] = []
    a = L.append
    a("# 현행 기준 반영 출처")
    a("")
    a("> 이 문서는 `tools/build_docs.py`가 `data/institutions/*.json`에서 생성한다. 직접 고치지 말 것.")
    a("")
    a("외부 공식 자료로 확인해 산출물에 반영한 현행 기준과 출처를 모았다.")
    a("각 항목은 `현행 기준 → 확인 출처 → 산출물 반영` 순으로 정리한다.")
    a("")
    for doc in sorted(docs_used):
        a(f"- 대상: {doc}")
    a(f"- 작성 기준일: {verified}")
    a(f"- 결과: **공식 출처 연결 {len(rows)}건**")
    a("")
    a("> 이 문서는 법률 자문이나 해당국 정부·KOICA의 공식 해석이 아니다.")
    a("> 대조에 쓴 원문은 각 항목의 근거 링크와 `sources/laws/`에서 확인할 수 있다.")
    a("")
    a("---")
    a("")

    for i, (d, x) in enumerate(rows, 1):
        ref = d["sourceRefs"][0] if d["sourceRefs"] else {}
        page = x.get("sourcePage") or ref.get("pages", "?")
        section = x.get("sourceSection") or ref.get("section", "")
        a(f"## {i:02d}. {x['field']}")
        a("")
        a(f"**{SEV_LABEL[x['severity']]}** · {d['country']['name']} · 기준자료 {page}쪽 ({section})")
        a("")
        a("**현행 기준**")
        a("")
        a(f"> {x['actualText']}")
        a("")
        a("**산출물 반영**")
        a("")
        a(f"> {x['action']}")
        a("")
        a(f"**근거** — {x['citation']}")
        a("")
        a("")
        a("---")
        a("")

    a("## 전달 상태")
    a("")
    a("각 항목의 상태는 `data/institutions/*.json`의 "
      "`verification.discrepancies[].upstream.state`에서 관리한다.")
    a("전달 후 상태를 갱신하고 `python3 tools/build_docs.py`를 다시 돌리면 이 문서가 따라온다.")
    a("")
    a("| 항목 | 우선순위 | 상태 |")
    a("|---|---|---|")
    for i, (d, x) in enumerate(rows, 1):
        up = x["upstream"]
        a(f"| {i:02d} {x['field']} | {up['priority']} | {UP_STATE.get(up['state'], up['state'])} |")
    a("")
    a("상태값: `not-reported`(미제보) · `reported`(제보함) · `acknowledged`(발행처 확인) · "
      "`fixed`(개정판 반영) · `declined`(정정 불요 회신)")
    a("")
    a("**전달 여부와 시점은 이 데이터셋 관리자가 판단한다.** 자동으로 발송되지 않는다.")
    a("")
    return "\n".join(L)


AXIS_EN = {"bidding": "Bidding system", "governance": "Procurement governance",
           "pipeline": "ODA project pipeline"}
SEV_EN = {"high": "HIGH", "medium": "MEDIUM", "low": "LOW"}


def build_review_sheet(items: list[dict]) -> str:
    """현지 직원(영어)용 확인 시트. 각 항목을 '현행 기준 → 확인할 것'으로 정리한다.

    이 데이터를 실제로 검증하는 KOICA 해외사무소 직원이 현지인이면 한국어를 못 읽는다.
    review 블록이 있는 항목만 담아, 원문·발주처와 대조할 수 있게 한다.
    """
    rows = [(d, x) for d in items for x in d["verification"].get("discrepancies", [])
            if x.get("review")]
    rows.sort(key=lambda t: (SEV_ORDER[t[1]["severity"]], t[0]["country"]["nameEn"], t[0]["slug"]))
    verified = max((d["verification"]["verifiedAt"] for d in items), default="")
    countries = sorted({d["country"]["nameEn"] for d in items})
    n_hi = sum(1 for _, x in rows if x["severity"] == "high")

    L: list[str] = []
    a = L.append
    a("# Field Verification Sheet")
    a("")
    a("> Generated by `tools/build_docs.py` from `data/institutions/*.json`. Do not edit by hand.")
    a("")
    a("For the KOICA field-office officer verifying this dataset against current law and the procuring")
    a("entity. Each item below records a current legal basis used in the output. Your job is the")
    a("**Verify** line: confirm it against the original text or the procuring entity.")
    a("")
    n_done = sum(1 for _, x in rows if (x.get("fieldCheck") or {}).get("status") in
                 ("confirmed", "refuted", "partial"))
    a(f"- As of: {verified}")
    a(f"- Countries: {', '.join(countries)}")
    a(f"- Items needing field check: **{len(rows)}** (HIGH {n_hi}) · returned by office: **{n_done}/{len(rows)}**")
    a("")
    a("HIGH = verify first because the point can affect bid eligibility, documents, or procedure.")
    a("")
    a("**How to return your findings:** under each item's *Office result* line, mark the status,")
    a("write what you found, and add your office name and date. Send the filled sheet back;")
    a("the dataset manager will record it. Items already returned show the result inline.")
    a("")
    a("---")
    a("")

    fc_label = {"confirmed": "✔ CONFIRMED", "refuted": "✗ REFUTED (our call was off)",
                "partial": "◐ PARTIAL", "pending": "… pending"}
    cur_country = None
    for i, (d, x) in enumerate(rows, 1):
        cc = d["country"]["nameEn"]
        if cc != cur_country:
            a(f"## {cc}")
            a("")
            cur_country = cc
        rv = x["review"]
        fc = x.get("fieldCheck")
        done_mark = f" — {fc_label.get(fc['status'], fc['status'])}" if fc and fc.get("status") != "pending" else ""
        a(f"### {i:02d}. [{SEV_EN[x['severity']]}] Current legal basis check{done_mark}")
        a("")
        a(f"- Institution: {d['country']['nameEn']} — {AXIS_EN.get(d['axis'], d['axis'])}")
        a(f"- Legal basis: {x['citation']}")
        ref = d["sourceRefs"][0] if d["sourceRefs"] else {}
        page = x.get("sourcePage") or ref.get("pages", "?")
        a(f"- KOICA guide: p.{page}")
        a("")
        a(f"**Current legal basis** — {rv['lawSays']}")
        a("")
        a(f"**✔ Verify** — {rv['verify']}")
        a("")
        if fc:
            a(f"**Office result** — {fc_label.get(fc['status'], fc['status'])} · "
              f"{fc['checkedBy']} · {fc['checkedOn']}")
            a(f"> {fc['finding']}"
              + (f" ([evidence]({fc['evidenceUrl']}))" if fc.get("evidenceUrl") else ""))
        else:
            a("**Office result** *(fill and return)* —")
            a("- Status: `[ ] confirmed`  `[ ] refuted`  `[ ] partial`")
            a("- Finding: ")
            a("- Checked by / date: ")
        a("")
        a("---")
        a("")

    a("## How to use this sheet")
    a("")
    a("1. Work through the HIGH items first — those can directly affect bid eligibility or procedure.")
    a("2. For each item, do the **Verify** action: open the cited article in the original law")
    a("   (links are in each institution's *Legal source* section) or ask the procuring entity.")
    a("3. Record the outcome. The Korean summary and official sources are collected in")
    a("   `docs/errata.md` for the dataset manager.")
    a("")
    a("This sheet is a verification aid, not an official interpretation. The original-language law")
    a("prevails where a translation differs.")
    a("")
    return "\n".join(L)


def main() -> int:
    items = load()
    if not items:
        print("제도 데이터가 없습니다.")
        return 1

    (DOCS / "verification-log.md").write_text(build_verification_log(items), encoding="utf-8")
    (DOCS / "errata.md").write_text(build_errata(items), encoding="utf-8")
    (DOCS / "review-sheet.en.md").write_text(build_review_sheet(items), encoding="utf-8")

    n_d = sum(len(d["verification"].get("discrepancies", [])) for d in items)
    n_u = sum(1 for d in items for x in d["verification"].get("discrepancies", []) if x.get("upstream"))
    n_r = sum(1 for d in items for x in d["verification"].get("discrepancies", []) if x.get("review"))
    print(f"문서 생성 완료 — 제도 {len(items)} · 확인사항 {n_d} · 출처 연결 {n_u} · 영어 검토 {n_r}")
    print(f"  {DOCS / 'verification-log.md'}")
    print(f"  {DOCS / 'errata.md'}")
    print(f"  {DOCS / 'review-sheet.en.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
