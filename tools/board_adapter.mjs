// 우리 institution.process → korea100studio board-v1 형식 어댑터.
//
// 두 스키마는 거의 1:1이다 — 둘 다 korea100의 프로세스 렌더러에서 나왔다.
// 이 어댑터는 korea100studio의 audit(구성 품질 감사)을 우리 데이터에 돌리기 위한 것이다.
// 렌더는 우리 build_site.py가 담당하고, 이 변환은 품질 점검 전용이다.
//
// 주의: board-v1의 emphasis(강조)는 우리 status(시간축: 선행→후속)와 축이 다르다.
// build_site.py의 강조 규칙과 같은 의미로 맞춘다 — current=핵심, risk=병목, loop=회귀,
// 나머지(done·waiting)는 중립. 이 매핑은 색에만 영향을 주고 레이아웃·audit 점수와 무관하다.

const EMPHASIS = {
  current: "key",
  risk: "bottleneck",
  loop: "loop",
  done: "normal",
  waiting: "normal",
};

/** institution 객체 하나를 board-v1 객체로 변환한다. */
export function toBoard(inst) {
  const p = inst.process;
  if (!p) return null;
  return {
    schema_version: 1,
    title: inst.name,
    subtitle: inst.oneLiner,
    lanes: p.lanes,
    stages: p.stages,
    nodes: p.nodes.map((n) => {
      const note = [n.action, n.deadline].filter(Boolean).join(" · ");
      return {
        id: n.id,
        lane: n.lane,
        stage: n.stage,
        label: n.name,
        emphasis: EMPHASIS[n.status] ?? "normal",
        ...(note ? { note } : {}),
      };
    }),
    edges: p.edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      ...(e.type ? { type: e.type } : {}),
      ...(e.label ? { label: e.label } : {}),
    })),
  };
}
