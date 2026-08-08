// 우리 렌더(build_site.py)의 프로세스 보드 실측 검사 — 카드 관통과 라벨 배치.
//
// board-v1 audit(tools/check_boards.mjs)은 korea100studio의 세로 스윔레인 레이아웃을
// 기준으로 채점하므로, 우리 가로 그리드 렌더의 실제 결과와는 다르다.
// 우리 렌더는 브라우저에서 그려진 SVG를 실측해야 정확하다.
//
// 사용법: 상세 페이지(/model/{slug}/)를 브라우저로 연 뒤 개발자 콘솔에 붙여넣는다.
//   python3 -m http.server 8765 --directory site
//   → http://localhost:8765/model/paraguay-permit-environment-construction-regulations/ 에서 실행
//
// 판정 기준
//   piercings        0이어야 한다. 엣지가 무관한 카드를 지나면 여기 잡힌다.
//   foreignCoverings 0이어야 한다. 라벨 배경이 "남의" 연결선을 덮으면 그 선이
//                    끊어져 보인다. 자기 경로 위에 얹는 것(ownCoverings)은
//                    라벨과 선의 소속을 분명히 하려는 의도된 배치라 세지 않는다.
//   labelOverlaps    0이어야 한다. 확정된 라벨끼리의 겹침.
//   cardHits         0이어야 한다. 라벨이 카드·머리글을 덮는 경우.
//   crowdedPairs     낮을수록 좋다. 60px 이내로 붙은 상시 라벨 쌍.
//   haloFallbacks    패널티로 못 피해 반투명 헤일로로 처리된 라벨 수. 0에 수렴해야 한다.
//   leaders          급증하면 라벨이 선에서 멀어졌다는 신호다.
//
// 순차(sequence) 라벨은 기본으로 접혀 있어 visibleLabels에서 빠진다. 카드에
// 마우스를 올리거나 포커스하면, 또는 범례의 "순차 라벨 모두 보기"로 드러난다.

(function boardCheck() {
  const board = document.getElementById("board");
  if (!board) return console.warn("이 페이지에는 업무구조도가 없습니다.");
  const svg = document.getElementById("edges");
  const bb = board.getBoundingClientRect();
  const rel = (r) => ({
    x: r.left - bb.left + board.scrollLeft,
    y: r.top - bb.top + board.scrollTop,
    r: r.right - bb.left + board.scrollLeft,
    b: r.bottom - bb.top + board.scrollTop,
  });
  const overlaps = (a, b) => a.x < b.r && a.r > b.x && a.y < b.b && a.b > b.y;

  const nodes = [...board.querySelectorAll(".node")].map((n) => ({
    id: n.dataset.id,
    ...rel(n.getBoundingClientRect()),
  }));
  const textCells = [
    ...board.querySelectorAll(".brow.head .bcell,.brow:not(.head) .bcell:first-child"),
  ].map((el) => rel(el.getBoundingClientRect()));
  const paths = [...svg.querySelectorAll("path.edge-path")];
  const groups = [...svg.querySelectorAll(".edge-label-group")];
  const visible = groups.filter((g) => getComputedStyle(g).opacity !== "0");
  const boxOf = (g) => {
    const r = g.querySelector("rect");
    return {
      x: +r.getAttribute("x"),
      y: +r.getAttribute("y"),
      r: +r.getAttribute("x") + +r.getAttribute("width"),
      b: +r.getAttribute("y") + +r.getAttribute("height"),
    };
  };

  // 1) 엣지가 무관한 카드를 지나는가
  const MARGIN = 3;
  const piercings = [];
  paths.forEach((p) => {
    const id = p.getAttribute("data-edge-id");
    const ed = EDGES.find((e) => e.id === id);
    if (!ed) return;
    const len = p.getTotalLength();
    const hit = {};
    for (let t = 0; t <= len; t += 3) {
      const pt = p.getPointAtLength(t);
      nodes.forEach((n) => {
        if (n.id === ed.source || n.id === ed.target) return;
        if (pt.x > n.x + MARGIN && pt.x < n.r - MARGIN && pt.y > n.y + MARGIN && pt.y < n.b - MARGIN)
          hit[n.id] = 1;
      });
    }
    Object.keys(hit).forEach((nid) => piercings.push(`${id} (${ed.source}→${ed.target}) ↯ ${nid}`));
  });

  // 2) 라벨이 남의 연결선을 덮는가 — 연속으로 가린 길이를 잰다.
  //    박스 경계에서 1px 이내를 지나는 선은 세지 않는다. 라벨을 선 바로 옆에
  //    붙이면 테두리와 스치는데, 이것은 가림이 아니라 의도한 인접 배치다.
  //    렌더러의 segmentCoverLength()와 같은 마진을 쓴다.
  const EDGE_M = 1;
  const foreign = [];
  let ownCoverings = 0;
  visible.forEach((g) => {
    const L = boxOf(g);
    const id = g.getAttribute("data-edge-id");
    const text = g.querySelector("text").textContent;
    paths.forEach((p) => {
      const pid = p.getAttribute("data-edge-id");
      const len = p.getTotalLength();
      let run = 0;
      let max = 0;
      for (let t = 0; t <= len; t += 2) {
        const pt = p.getPointAtLength(t);
        if (
          pt.x > L.x + EDGE_M &&
          pt.x < L.r - EDGE_M &&
          pt.y > L.y + EDGE_M &&
          pt.y < L.b - EDGE_M
        ) {
          run += 2;
          if (run > max) max = run;
        } else run = 0;
      }
      if (max <= 4) return;
      if (pid === id) ownCoverings++;
      else foreign.push({ label: text, edge: id, covers: pid, maxRunPx: max });
    });
  });
  foreign.sort((a, b) => b.maxRunPx - a.maxRunPx);

  // 3) 라벨끼리 · 라벨과 카드/머리글
  let labelOverlaps = 0;
  let crowdedPairs = 0;
  for (let i = 0; i < visible.length; i++) {
    for (let j = i + 1; j < visible.length; j++) {
      const A = boxOf(visible[i]);
      const B = boxOf(visible[j]);
      if (overlaps(A, B)) labelOverlaps++;
      const d = Math.hypot((A.x + A.r) / 2 - (B.x + B.r) / 2, (A.y + A.b) / 2 - (B.y + B.b) / 2);
      if (d < 60) crowdedPairs++;
    }
  }
  let cardHits = 0;
  visible.forEach((g) => {
    const L = boxOf(g);
    [...nodes, ...textCells].forEach((o) => {
      if (overlaps(L, o)) cardHits++;
    });
  });

  const report = {
    page: document.title.split("|")[0].trim(),
    nodes: nodes.length,
    edges: paths.length,
    totalLabels: groups.length,
    visibleLabels: visible.length,
    piercings: piercings.length,
    foreignCoverings: foreign.length,
    foreignMaxRunPx: foreign.length ? foreign[0].maxRunPx : 0,
    ownCoverings,
    labelOverlaps,
    cardHits,
    crowdedPairs,
    haloFallbacks: svg.querySelectorAll(".edge-label-group[data-covers]").length,
    leaders: svg.querySelectorAll(".edge-label-leader").length,
  };
  const clean =
    !piercings.length && !foreign.length && !labelOverlaps && !cardHits;
  console[clean ? "log" : "warn"](clean ? "깨끗합니다." : "확인이 필요합니다.", report);
  if (piercings.length) console.warn("카드 관통:", piercings);
  if (foreign.length) console.warn("남의 연결선을 덮은 라벨:", foreign.slice(0, 10));
  return report;
})();
