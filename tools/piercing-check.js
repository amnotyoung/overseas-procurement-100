// 우리 렌더(build_site.py)의 프로세스 보드 관통 검사.
//
// board-v1 audit(tools/check_boards.mjs)은 korea100studio의 세로 스윔레인 레이아웃을
// 기준으로 채점하므로, 우리 가로 그리드 렌더의 실제 관통과는 다르다.
// 우리 렌더의 관통은 브라우저에서 그려진 SVG를 실측해야 정확하다.
//
// 사용법: 상세 페이지(/model/{slug}/)를 브라우저로 연 뒤 개발자 콘솔에 붙여넣는다.
//   python3 -m http.server 8765 --directory site
//   → http://localhost:8765/model/nepal-bidding-system/ 열고 콘솔에서 실행
//
// 결과 []가 정상. 항목이 있으면 그 엣지가 무관한 카드를 지난다는 뜻이다.
// 라우터(build_site.py의 route())가 거터 회피로 최소화하지만, 그래프가 극단적으로
// 얽히면 남을 수 있다. 그때는 노드 배치(lane/stage)나 엣지를 조정한다.

(function piercingCheck() {
  const board = document.getElementById("board");
  if (!board) return console.warn("이 페이지에는 업무구조도가 없습니다.");
  const bb = board.getBoundingClientRect();
  const nodes = [...board.querySelectorAll(".node")].map((n) => {
    const r = n.getBoundingClientRect();
    return {
      id: n.dataset.id,
      x: r.left - bb.left + board.scrollLeft,
      y: r.top - bb.top + board.scrollTop,
      w: r.width,
      h: r.height,
    };
  });
  const MARGIN = 3;
  const pierces = [];
  board.querySelectorAll("#edges path[marker-end]").forEach((p, i) => {
    const ed = EDGES[i];
    if (!ed) return;
    const L = p.getTotalLength();
    const hit = {};
    for (let t = 0; t <= L; t += 3) {
      const pt = p.getPointAtLength(t);
      nodes.forEach((n) => {
        if (n.id === ed.source || n.id === ed.target) return;
        if (
          pt.x > n.x + MARGIN &&
          pt.x < n.x + n.w - MARGIN &&
          pt.y > n.y + MARGIN &&
          pt.y < n.y + n.h - MARGIN
        )
          hit[n.id] = 1;
      });
    }
    Object.keys(hit).forEach((nid) =>
      pierces.push(`${ed.id} (${ed.source}→${ed.target}) ↯ ${nid}`),
    );
  });
  if (pierces.length === 0) console.log("관통 0 — 깨끗합니다.");
  else console.warn(`관통 ${pierces.length}건:`, pierces);
  return pierces;
})();
