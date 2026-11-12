#!/usr/bin/env python3
"""조달 원천의 기관·근거·출처·현장질문이 공개 HTML에 보존되는지 검사한다."""
from __future__ import annotations

import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"


class EvidenceCards(HTMLParser):
    def __init__(self):
        super().__init__()
        self.card_links = []
        self.in_citation = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "p" and attrs.get("class") == "cite":
            self.in_citation = True
            self.card_links.append([])
        elif tag == "a" and self.in_citation:
            self.card_links[-1].append(attrs.get("href"))

    def handle_endtag(self, tag):
        if tag == "p":
            self.in_citation = False


def check_cards(page, expected):
    parser = EvidenceCards()
    parser.feed(page)
    actual = sorted(tuple(links) for links in parser.card_links)
    wanted = sorted(tuple(ref["url"] for ref in x["citationSources"] if ref.get("accessStatus") != "unavailable") for x in expected)
    if actual != wanted or any(not links for links in actual):
        raise ValueError("정정 카드의 원문 링크와 원천 데이터가 다릅니다")


def main():
    discrepancies = []
    count = 0
    for path in sorted((ROOT / "data/institutions").glob("*.json")):
        data = json.loads(path.read_text())
        page = (SITE / "model" / data["slug"] / "index.html").read_text()
        cards = data["verification"]["discrepancies"]
        check_cards(page, cards)
        discrepancies.extend(cards)
        if re.search(r"<li>\s*\{['\"]", html.unescape(page)):
            raise ValueError(f"{path.stem}: 현장 확인사항에 객체가 노출됐습니다")
        for item in data["fieldVerification"]:
            if isinstance(item, dict) and html.escape(item["question"]) not in page:
                raise ValueError(f"{path.stem}: 현장 질문 누락")
        if re.search(r"<h3>[^<]*(?:canvas\.|verification /|process /)", page):
            raise ValueError(f"{path.stem}: 내부 필드 경로가 독자용 제목에 노출됐습니다")
        if data["slug"] == "nepal-bidding-system":
            panel = re.search(r'<div class="edition-pair">(.+?)</article>', page, re.S)
            if not panel or not all(term in panel[1] for term in ("2~3%", "2.5%", "2007년", "제16차")):
                raise ValueError("네팔 입찰보증의 산정 기준과 비교 판본 누락")
        nodes = json.loads(re.search(r"^var NODES=(.+);$", page, re.M)[1])
        if data["slug"] == "nepal-bidding-system":
            comparison = next(q["comparison"] for q in data["sourceQuotes"] if q.get("comparison"))
            guide = comparison["guideCitation"]
            targets = [node_id for node_id, view in nodes.items() if view.get("guide_comparison")]
            panel = nodes["P07"].get("guide_comparison", "")
            if targets != ["P07"] or not all(html.escape(t) in panel for t in
                    (guide["quote"], guide["url"], comparison["summary"], comparison["sourceUrl"])):
                raise ValueError("네팔 P07 자료집·개정 조문 대조 누락")
        for node in data["process"]["nodes"]:
            rendered = nodes[node["id"]]
            evidence = rendered["procurement_evidence"]
            if html.unescape(rendered["actor"]) != node["actor"]:
                raise ValueError(f"{path.stem}/{node['id']}: 담당 기관 불일치")
            if node.get("basisStatus") == "pending" and "추가 확인" not in evidence:
                raise ValueError(f"{path.stem}/{node['id']}: 근거 확인 상태 누락")
            if node.get("guideRef") and html.escape(node["guideRef"]["excerpt"]) not in evidence:
                raise ValueError(f"{path.stem}/{node['id']}: 자료집 발췌 누락")
            for key in node.get("requirementRefs", []):
                url = data["verification"]["articleAudit"]["requirements"][key]["evidenceUrl"]
                if html.escape(url) not in evidence:
                    raise ValueError(f"{path.stem}/{node['id']}: 관련 요건 원문 누락")
            if node.get("legal_basis") and [b["url"] for b in node["legal_basis"]] != [
                html.unescape(b["url"]) for b in rendered["legal_basis"]
            ]:
                raise ValueError(f"{path.stem}/{node['id']}: 조문 원문 누락")
            count += 1
        if data["slug"] == "peru-bidding-system" and nodes["P06"]["actor"] != "개별 계약기관":
            raise ValueError("페루 평가·낙찰 담당기관 회귀")
        if data["slug"] == "ghana-oda-project-pipeline":
            if "예비조사 실시" not in nodes["P05"]["procurement_evidence"] or any(
                "Procurement" in basis["law"] for basis in nodes["P05"].get("legal_basis", [])
            ):
                raise ValueError("가나 예비조사 근거 회귀")
        if data["slug"] in {"senegal-bidding-system", "senegal-procurement-governance"}:
            current = json.dumps(data["canvas"], ensure_ascii=False)
            if any(stale in current for stale in ("ARMP", "2014-1212", "Public Service Contract for")):
                raise ValueError(f"{path.stem}: 구 명칭·구법 또는 불완전한 법령명")
    check_cards((SITE / "verification/index.html").read_text(), discrepancies)
    check_cards((SITE / "errata/index.html").read_text(), [x for x in discrepancies if x.get("upstream")])
    print(f"OK: 조달 절차 {count}단계, 검증 대장 {len(discrepancies)}건의 공개 HTML 검사 완료")


if __name__ == "__main__":
    main()
