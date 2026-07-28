#!/usr/bin/env python3
"""data/institutions/*.json → site/ 정적 HTML 생성.

원본 how-did-they-do-all-that-procurement의 화면 구성을 승계한다.
  /                    제도 대장 (검색·국가/축 필터·비교 선반)
  /model/{slug}/       한 장 요약 (업무구조도 + 캔버스 + 검증)
  /verification/       현행 기준 확인 대장

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
SITE = ROOT / "site"

SITE_TITLE = "그 나라 조달은 어떻게 할까"
SITE_SUB = "협력국 조달제도 안내"


def clean_generated_html(value: str) -> str:
    """생성 HTML의 줄 끝 공백을 제거하고 POSIX 개행으로 끝낸다."""
    return "\n".join(line.rstrip() for line in value.splitlines()) + "\n"


AXIS_LABEL = {"bidding": "입찰제도", "governance": "조달 거버넌스", "pipeline": "ODA 사업형성"}
VERIF_LABEL = {
    "article-verified": "조문 대조 완료",
    "law-linked": "원문 링크 연결",
    "source-document": "자료집 기재",
    "needs-review": "재검토 필요",
}
VERIF_TONE = {
    "article-verified": "ok",
    "law-linked": "info",
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
}


UP_STATE_LABEL = {
    "not-reported": "미제보",
    "reported": "제보함 · 회신 대기",
    "acknowledged": "발행처 확인",
    "fixed": "개정판 반영",
    "declined": "정정 불요 회신",
}
SEV_TONE = {"high": "bad", "medium": "warn", "low": "muted"}


def e(s) -> str:
    return html.escape(str(s if s is not None else ""))


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

.boardwrap{position:relative;border:1px solid var(--line);border-radius:12px;overflow:auto}
.board{position:relative;min-width:940px}
.board svg.edges{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:1}
.brow{display:grid;border-bottom:1px solid var(--line)}
.brow:last-child{border-bottom:0}
.brow.head{background:var(--soft);position:sticky;top:0;z-index:3}
/* gap은 같은 셀에 세로로 쌓인 노드 사이로 화살표가 지나갈 통로다. 좁히면 화살촉이 뭉갠다. */
.bcell{padding:14px 12px;border-right:1px solid var(--line);min-height:64px;
  display:flex;flex-direction:column;gap:26px;justify-content:center}
.bcell:last-child{border-right:0}
.brow.head .bcell{min-height:0;padding:11px 12px;justify-content:flex-start}
.stage-k{font-weight:800;font-size:12px;color:var(--key);letter-spacing:.02em}
.stage-t{font-size:13px;font-weight:700}
.lane-t{font-size:13px;font-weight:700;color:var(--muted)}
.node{position:relative;z-index:2;background:var(--bg);border:1px solid var(--line);
  border-radius:9px;padding:10px 12px;cursor:pointer;text-align:left;font:inherit;color:inherit;
  width:100%;display:block;transition:box-shadow .12s,border-color .12s}
.node:hover{border-color:var(--muted);box-shadow:0 2px 10px rgba(0,0,0,.07)}
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
  자료집 기준일 기준으로 작성된 참고자료입니다. 법률 자문이나 해당국 정부·KOICA의 공식 해석이 아닙니다.<br>
  조달법은 개정이 잦습니다 — 실제 입찰 전 발주처 공고문과 현행 법령을 확인해야 합니다.<br>
  1차 출처 KOICA 2026 국가별 개발협력사업 참여전략 자료집 · 현행 기준 출처는 각 제도의 검증 블록 참조
</div></footer>
{f'<script>{extra_js}</script>' if extra_js else ''}
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

    rows = []
    for i, d in enumerate(items, 1):
        v = d["verification"]["status"]
        nd = len(d["verification"].get("discrepancies", []))
        hi = sum(1 for x in d["verification"].get("discrepancies", []) if x["severity"] == "high")
        disc_badge = (
            f'<span class="badge {"bad" if hi else "warn"}">확인사항 {nd}</span>' if nd else
            '<span class="badge muted plain">—</span>'
        )
        rows.append(f"""<tr data-c="{e(d['country']['name'])}" data-a="{e(d['axis'])}"
  data-s="{e((d['name'] + ' ' + d['oneLiner'] + ' ' + d['country']['nameEn']).lower())}">
  <td class="no">{i:02d}</td>
  <td class="name"><a href="model/{e(d['slug'])}/index.html">{e(d['name'])}</a>
    <p>{e(d['oneLiner'])}</p></td>
  <td><span class="badge plain muted">{e(d['country']['name'])}</span></td>
  <td style="font-size:13px;color:var(--muted)">{e(AXIS_LABEL[d['axis']])}</td>
  <td><span class="badge {VERIF_TONE[v]}">{e(VERIF_LABEL[v])}</span></td>
  <td>{disc_badge}</td>
</tr>""")

    side_c = "".join(
        f'<button aria-pressed="false" data-f="c" data-v="{e(k)}"><i class="dot"></i>{e(k)}<span class="n">{n}</span></button>'
        for k, n in sorted(countries.items(), key=lambda x: -x[1]))
    side_a = "".join(
        f'<button aria-pressed="false" data-f="a" data-v="{e(k)}"><i class="dot"></i>{e(AXIS_LABEL[k])}<span class="n">{n}</span></button>'
        for k, n in axes.items())

    body = f"""
<div class="wrap hero">
  <div class="eyebrow">자료집에서 원문으로</div>
  <h1>그 나라 조달은 어떻게 할까?</h1>
  <p class="lede">협력국 입찰에 처음 들어가더라도 괜찮습니다.</p>
  <p class="lede">자료집에 흩어진 절차를 담당자·서류·기한이 보이는 한 장으로 정리하고, 근거는 각국 법령 원문까지 대조했습니다.</p>
  <p class="meta">제도 {len(items)}개 · {len(countries)}개국 · 조문 대조 완료 {verified}개 · 자료집 기준일 {e(asof)}</p>
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
"""
    return page(SITE_TITLE, body, nav="list", extra_js=js)


# ─────────────────────────────────────────────────────────── 상세

def build_detail(d: dict, items: list[dict], *, standalone: bool = False) -> str:
    idx = items.index(d)
    prev = items[idx - 1] if idx > 0 else None
    nxt = items[idx + 1] if idx < len(items) - 1 else None
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
        f'{i:02d} · {e(x["country"]["name"])} {e(AXIS_LABEL[x["axis"]])}</option>'
        for i, x in enumerate(items, 1))

    # 업무구조도 그리드
    grid_cols = f"180px repeat({len(stages)},minmax(190px,1fr))"
    head = f'<div class="brow head" style="grid-template-columns:{grid_cols}">' \
           f'<div class="bcell"><span class="lane-t">레인 \\ 게이트</span></div>'
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
        f'<div class="auth"><b>{link(e(a["name"]), a.get("url"))}</b><span>{el(a["role"])}</span></div>'
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
    # 관련 제도 — standalone(단독 파일)에서는 그 파일이 없으므로 링크 대신 이름만.
    rel = "".join(
        (f'<span class="chip">{e(next((y["name"] for y in items if y["slug"] == r), r))}</span>'
         if standalone else
         f'<a class="chip" style="text-decoration:none" href="../{e(r)}/index.html">{e(next((y["name"] for y in items if y["slug"] == r), r))}</a>')
        for r in d["related"])

    # 검증
    srcs = "".join(
        f'<li><a class="ref" href="{e(s["officialUrl"])}" target="_blank" rel="noopener">{e(s.get("officialName") or s["law"])}</a>'
        f'<span class="badge plain muted" style="margin-left:6px">{e(KIND_LABEL.get(s["kind"], s["kind"]))}</span>'
        + (f'<span class="ar">대조 조문 {e(s["articlesChecked"])}</span>' if s.get("articlesChecked") else "")
        + f'<span class="ar">확인 {e(s["retrievedOn"])}{" · " + e(s["publisher"]) if s.get("publisher") else ""}</span></li>'
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
  <span class="pos">{idx + 1}/{len(items)}</span>
</div></div>"""

    body = f"""
{subnav}

<div class="wrap dtl-hd">
  <div class="row">
    <span class="badge plain muted">NO {idx + 1:02d}</span>
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
  <div class="boardwrap"><div class="board" id="board">
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
  <button class="close" onclick="document.getElementById('dlg').close()">×</button>
  <div id="dbody"></div>
</div></dialog>"""

    # drawer는 innerHTML로 그리므로 텍스트를 미리 escape하고, 조문에는 원문 URL을 붙여 넘긴다
    node_view = {}
    for n in nodes:
        nv = dict(n)
        for k in ("name", "actor", "action", "deadline", "blocker", "lane", "stage"):
            if nv.get(k):
                nv[k] = el(nv[k])
        if nv.get("output_documents"):
            nv["output_documents"] = [e(x) for x in nv["output_documents"]]
        if nv.get("legal_basis"):
            nv["legal_basis"] = [
                {"law": e(lb["law"]), "article": e(lb["article"]), "url": surl.get(lb["law"], "")}
                for lb in nv["legal_basis"]
            ]
        node_view[n["id"]] = nv

    js = f"""
var NODES={json.dumps(node_view, ensure_ascii=False)};
var EDGES={json.dumps(edges, ensure_ascii=False)};

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
    var el=board.querySelector('.node[data-id="'+id+'"]');
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

var KIND={json.dumps(KIND_LABEL, ensure_ascii=False)};
function openNode(id){{
  var n=NODES[id]; if(!n)return;
  var h='<span class="badge plain muted">'+n.id+'</span> '
       +'<span class="badge plain muted">'+n.lane+'</span> '
       +'<span class="badge plain muted">'+n.stage+'</span>';
  h+='<h3>'+n.name+'</h3>';
  h+='<dl class="kv">';
  h+='<dt>담당</dt><dd>'+n.actor+'</dd>';
  if(n.action) h+='<dt>내용</dt><dd>'+n.action+'</dd>';
  if(n.deadline) h+='<dt>기한</dt><dd>'+n.deadline+'</dd>';
  if(n.output_documents&&n.output_documents.length)
    h+='<dt>산출 문서</dt><dd>'+n.output_documents.join(' · ')+'</dd>';
  if(n.blocker) h+='<dt>병목</dt><dd style="color:var(--warn)">'+n.blocker+'</dd>';
  if(n.legal_basis&&n.legal_basis.length){{
    h+='<dt>근거 조문</dt><dd>'+n.legal_basis.map(function(l){{
      var nm=l.url?'<a class="ref" href="'+l.url+'" target="_blank" rel="noopener">'+l.law+'</a>':l.law;
      return '<div style="margin-bottom:4px">'+nm+' <code>'+l.article+'</code></div>';}}).join('')+'</dd>';
  }}
  if(typeof n.confidence==='number'){{
    h+='<dt>법령 근거 확신도</dt><dd>'+n.confidence.toFixed(2)
      +(n.confidence<0.8?' <span class="badge warn">현장 검증 필요</span>':'')+'</dd>';
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

def build_bundle(country_slug: str, country_name: str, items: list[dict]) -> str:
    """한 국가의 제도들을 네비게이션 없는 자족 단일 HTML로 묶는다.

    각 제도를 standalone HTML로 만들어 iframe srcdoc에 임베드한다 — iframe이
    JS 스코프를 격리하므로 여러 제도의 업무구조도·drawer가 서로 충돌하지 않는다.
    외부 리소스 요청이 전혀 없어(모두 인라인·srcdoc) 파일 하나로 오프라인에서 열린다.
    """
    docs = [d for d in items if d["slug"].startswith(country_slug + "-")]
    docs.sort(key=lambda d: d["priority"])
    if not docs:
        return ""

    tabs, frames = [], []
    for i, d in enumerate(docs):
        inner = build_detail(d, items, standalone=True)
        srcdoc = html.escape(inner, quote=True)
        active = " active" if i == 0 else ""
        tabs.append(
            f'<button class="tab{active}" data-i="{i}" onclick="showTab({i})">'
            f'{e(AXIS_LABEL[d["axis"]])}</button>')
        frames.append(
            f'<iframe class="fr{active}" data-i="{i}" title="{e(d["name"])}" '
            f'loading="{"eager" if i == 0 else "lazy"}" srcdoc="{srcdoc}"></iframe>')

    asof = max(d["asOfDate"] for d in docs)
    return f"""<!doctype html>
<html lang="ko"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(country_name)} 공공조달 제도 | {e(SITE_TITLE)}</title>
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
  <h1>{e(country_name)} 공공조달 제도</h1>
  <p class="sub">KOICA 2026 참여전략 자료집과 각국 공식 원문을 바탕으로 정리한 한 장 요약 · 기준일 {e(asof)}</p>
  <div class="tabs">{''.join(tabs)}</div>
</div>
<div class="frames">{''.join(frames)}</div>
<div class="foot">
  자료집 기준일 기준으로 작성된 참고자료입니다. 법률 자문이나 해당국 정부·KOICA의 공식 해석이 아닙니다.
  조달법은 개정이 잦으므로 실제 입찰 전 발주처 공고문과 현행 법령을 확인해야 합니다.
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
    items = []
    for f in sorted(INST_DIR.glob("*.json")):
        items.append(json.loads(f.read_text(encoding="utf-8")))
    items.sort(key=lambda d: (d["country"]["name"], d["priority"]))
    if not items:
        print("제도 데이터가 없습니다.")
        return 1

    if SITE.exists():
        shutil.rmtree(SITE)
    (SITE / "model").mkdir(parents=True)
    (SITE / "verification").mkdir(parents=True)
    (SITE / "errata").mkdir(parents=True)

    (SITE / "index.html").write_text(clean_generated_html(build_index(items)), encoding="utf-8")
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

    n = len(list(SITE.rglob("*.html")))
    print(f"빌드 완료 — {n}개 페이지")
    print(f"  {SITE}/index.html")
    print(f"  {SITE}/verification/index.html")
    for d in items:
        print(f"  {SITE}/model/{d['slug']}/index.html")

    # 배포용 단일 파일 — 국가별로 dist/{country}.html 생성 (네비 없는 자족 파일)
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    countries = {}  # country_slug(= 제도 slug 접두) → 국가 한글명
    for d in items:
        countries[d["country"]["nameEn"].lower().replace(" ", "-")] = d["country"]["name"]
    print("\n배포용 단일 파일 (dist/):")
    for country_slug, country_name in sorted(countries.items()):
        html_str = build_bundle(country_slug, country_name, items)
        if not html_str:
            continue
        out = dist / f"{country_slug}.html"
        out.write_text(clean_generated_html(html_str), encoding="utf-8")
        size_kb = len(html_str.encode("utf-8")) // 1024
        print(f"  {out}  ({size_kb}KB, 자족·오프라인)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
