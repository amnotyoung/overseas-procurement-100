#!/usr/bin/env python3
"""data/institutions/*.json → docs/verification-log.md, docs/errata.md 생성.

검증 대장과 정오표를 손으로 쓰면 데이터와 어긋난다. 실제로 어긋났다.
불일치는 JSON이 단일 출처이고, 문서는 그것을 읽는 형식으로 옮긴 것일 뿐이다.

사용법:
    python3 tools/build_docs.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INST_DIR = ROOT / "data" / "institutions"
DOCS = ROOT / "docs"

SEV_LABEL = {"high": "높음", "medium": "보통", "low": "낮음"}
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
    a("# 검증 대장")
    a("")
    a("> 이 문서는 `tools/build_docs.py`가 `data/institutions/*.json`에서 생성한다. 직접 고치지 말 것.")
    a("")
    a("자료집 서술을 각국 법령 원문과 대조한 결과를 공개한다.")
    a("")
    a(f"- 기준일: {verified}")
    a(f"- 대상: {len(items)}개 제도 ({', '.join(countries)})")
    a(f"- 결과: **불일치 {len(rows)}건 — 높음 {counts['high']} / 보통 {counts['medium']} / 낮음 {counts['low']}**")
    n_office = sum(1 for _, x in rows if (x.get("fieldCheck") or {}).get("status")
                   in ("confirmed", "refuted", "partial"))
    a(f"- 발행처 조치 필요: **{n_up}건** (정정 요망 {n_fix} / 보완 권고 {n_up - n_fix}) → [정오표](errata.md)")
    a(f"- 사무소 현장 확인: **{n_office}/{len(rows)}건** 회신됨 → [영어 검토 시트](review-sheet.en.md)")
    a("")
    a("## 제도별 검증 상태")
    a("")
    a("| 제도 | 국가 | 검증 | 불일치 | 사무소 확인 | 확인일 |")
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
          f"{VERIF_LABEL[v['status']]} | {len(ds)}건{f' (높음 {hi})' if hi else ''} | {office_cell} | {v['verifiedAt']} |")
    a("")
    a("---")
    a("")

    for sev in ("high", "medium", "low"):
        group = [(d, x) for d, x in rows if x["severity"] == sev]
        if not group:
            continue
        head = {"high": "높음 — 실무에서 바로 문제가 되는 것",
                "medium": "보통 — 근거 추적과 판단이 막히는 것",
                "low": "낮음 — 표기·누락"}[sev]
        a(f"## {head}")
        a("")
        for d, x in group:
            up = x.get("upstream")
            a(f"### {x['field']}")
            a("")
            a(f"- 제도: [{d['name']}](../data/institutions/{d['slug']}.json) · `{x['id']}`")
            a(f"- 근거: {x['citation']}")
            if up:
                a(f"- 발행처 조치: **{up['priority']}** · {UP_STATE.get(up['state'], up['state'])}")
            else:
                a("- 발행처 조치: 없음 (본 데이터의 보완 사항)")
            fc = x.get("fieldCheck")
            if fc:
                fc_ko = {"confirmed": "✔ 확인됨", "refuted": "✗ 반증됨(우리 판단 오류)",
                         "partial": "◐ 부분 확인", "pending": "… 확인 중"}
                a(f"- 사무소 확인: **{fc_ko.get(fc['status'], fc['status'])}** · "
                  f"{fc['checkedBy']} · {fc['checkedOn']} — {fc['finding']}")
            elif x.get("review"):
                a("- 사무소 확인: 미회신 (영어 검토 시트에 확인 대기)")
            a("")
            a("**자료집**")
            a("")
            a(f"> {x['sourceText']}")
            a("")
            a("**법령 원문**")
            a("")
            a(f"> {x['actualText']}")
            a("")
            a(x["impact"])
            a("")
            a(f"**실무자가 할 일** — {x['userAction']}")
            a("")
            a(f"*이 데이터에 반영* — {x['action']}")
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
    a("1. 자료집에서 인용 조문을 **전부** 뽑는다.")
    a("2. 해당국 법령 **영문 원문을 확보**하고, 조문 목록을 먼저 뽑아 **총 조문 수를 확인**한다.")
    a("   — 네팔 건은 이 단계에서 \"법은 76조뿐\"이 나왔고, 그 덕에 자료집의 \"141 조항\"이 규칙 조항임을 특정할 수 있었다.")
    a("3. 인용 조문을 **하나씩 대조**한다. 조문 제목·문언·수치를 본다.")
    a("4. 수치는 반드시 원문 표와 맞춘다.")
    a("5. 자료집이 **말하지 않은 것**도 본다. 근거 문서를 읽다 보면 자료집에 없는 의무가 나온다.")
    a("6. **근거 문서가 아직 살아 있는지 확인한다.** 폐지·개정됐으면 대조 자체가 무의미해진다.")
    a("7. 불일치는 **자료집을 틀렸다고 적지 말고**, 무엇이 어떻게 다르며 실무에 어떤 영향인지 적는다.")
    a("   자료집이 옳은데 표기만 부족한 경우가 있고, 발행 시점에는 옳았으나 근거가 바뀐 경우도 있다.")
    a("")
    return "\n".join(L)


def build_errata(items: list[dict]) -> str:
    rows = [(d, x) for d in items for x in d["verification"].get("discrepancies", [])
            if x.get("upstream")]
    rows.sort(key=lambda t: (0 if t[1]["upstream"]["priority"] == "정정 요망" else 1,
                             SEV_ORDER[t[1]["severity"]]))
    n_fix = sum(1 for _, x in rows if x["upstream"]["priority"] == "정정 요망")
    verified = max((d["verification"]["verifiedAt"] for d in items), default="")
    docs_used = {r["document"] for d in items for r in d["sourceRefs"]}

    L: list[str] = []
    a = L.append
    a("# 자료집 정오표")
    a("")
    a("> 이 문서는 `tools/build_docs.py`가 `data/institutions/*.json`에서 생성한다. 직접 고치지 말 것.")
    a("")
    a("법령 원문 대조에서 나온 항목 중 **자료집 수정이 필요한 것**을 모았다.")
    a("각 항목은 `현재 서술 → 수정 제안 → 근거 조문` 형태라 그대로 옮겨 전달할 수 있다.")
    a("")
    for doc in sorted(docs_used):
        a(f"- 대상: {doc}")
    a(f"- 작성 기준일: {verified}")
    a(f"- 결과: **정정 요망 {n_fix}건 / 보완 권고 {len(rows) - n_fix}건**")
    a("")
    a("| 구분 | 뜻 |")
    a("|---|---|")
    a("| **정정 요망** | 그대로 따르면 실무 손해가 발생하거나, 자료집 안에서 서로 모순되는 것 |")
    a("| **보완 권고** | 서술은 맞으나 출처 표기·누락 보완이 필요한 것 |")
    a("")
    a("> 본 정오표는 법령 원문 대조 결과이며 발행처의 공식 견해가 아니다.")
    a("> 대조에 쓴 원문은 `sources/laws/`에 보관돼 있다.")
    a("")
    a("---")
    a("")

    for i, (d, x) in enumerate(rows, 1):
        up = x["upstream"]
        ref = d["sourceRefs"][0] if d["sourceRefs"] else {}
        # 불일치가 자료집의 어느 대목인지는 제도 전체의 첫 출처와 다를 수 있다.
        # 정오표는 발행처가 그 쪽을 펴 봐야 하는 문서라 개별 지정을 우선한다.
        page = x.get("sourcePage") or ref.get("pages", "?")
        section = x.get("sourceSection") or ref.get("section", "")
        a(f"## {i:02d}. {x['field']}")
        a("")
        a(f"**{up['priority']}** · {UP_STATE.get(up['state'], up['state'])} · "
          f"{d['country']['name']} · 자료집 {page}쪽 ({section})")
        a("")
        a("**현재 자료집 서술**")
        a("")
        a(f"> {x['sourceText']}")
        a("")
        a("**수정 제안**")
        a("")
        a(f"> {up['suggestedText']}")
        a("")
        a(f"**근거** — {x['citation']}")
        a("")
        a(f"**사유** — {x['impact']}")
        if up.get("note"):
            a("")
            a(f"*비고* — {up['note']}")
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
    """현지 직원(영어)용 검증 시트. 각 불일치를 '자료집 서술 → 법령 → 확인할 것'으로.

    이 데이터를 실제로 검증하는 KOICA 해외사무소 직원이 현지인이면 한국어를 못 읽는다.
    review 블록이 있는 불일치만 담아, 원문·발주처와 대조할 수 있게 한다.
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
    a("For the KOICA field-office officer verifying this dataset against the law and the procuring")
    a("entity. Each item below is a point where the Korean-language KOICA strategy guide differs from")
    a("the current law. Your job is the **Verify** line: confirm it against the original text or the")
    a("procuring entity, and flag whether the guide needs correcting.")
    a("")
    n_done = sum(1 for _, x in rows if (x.get("fieldCheck") or {}).get("status") in
                 ("confirmed", "refuted", "partial"))
    a(f"- As of: {verified}")
    a(f"- Countries: {', '.join(countries)}")
    a(f"- Items needing field check: **{len(rows)}** (HIGH {n_hi}) · returned by office: **{n_done}/{len(rows)}**")
    a("")
    a("HIGH = following the guide risks bid rejection, document loss, or a procedural breach.")
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
        a(f"### {i:02d}. [{SEV_EN[x['severity']]}] {rv['topic']}{done_mark}")
        a("")
        a(f"- Institution: {d['country']['nameEn']} — {AXIS_EN.get(d['axis'], d['axis'])}")
        a(f"- Legal basis: {x['citation']}")
        ref = d["sourceRefs"][0] if d["sourceRefs"] else {}
        page = x.get("sourcePage") or ref.get("pages", "?")
        a(f"- KOICA guide: p.{page}")
        a("")
        a(f"**The guide says** — {rv['guideSays']}")
        a("")
        a(f"**The law says** — {rv['lawSays']}")
        a("")
        a(f"**Why it matters** — {rv['impact']}")
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
    a("1. Work through the HIGH items first — those are where following the guide can cause real loss.")
    a("2. For each item, do the **Verify** action: open the cited article in the original law")
    a("   (links are in each institution's *Legal source* section) or ask the procuring entity.")
    a("3. Record the outcome. If the guide is wrong, the correction is already drafted in Korean in")
    a("   `docs/errata.md` for transmission to the guide's publisher (KOICA headquarters).")
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
    print(f"문서 생성 완료 — 제도 {len(items)} · 불일치 {n_d} · 발행처 조치 {n_u} · 영어 검토 {n_r}")
    print(f"  {DOCS / 'verification-log.md'}")
    print(f"  {DOCS / 'errata.md'}")
    print(f"  {DOCS / 'review-sheet.en.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
