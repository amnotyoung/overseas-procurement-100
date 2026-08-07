// 프로세스 보드 품질 게이트 — korea100studio의 audit을 우리 데이터에 돌린다.
//
// 왜 절대 판정이 아니라 회귀 감지인가:
//   audit은 korea100studio의 "세로 스윔레인" 레이아웃 기준으로 채점한다.
//   우리 화면(build_site.py)은 가로 그리드에 아래 거터 우회라 배치가 다르다.
//   그래서 stretch·crossings 같은 레이아웃 의존 지표를 절대 기준으로 강제하면
//   거짓 실패가 난다. 대신 baseline과 비교해 "이번 변경이 더 나쁘게 만들었나"를 본다.
//
// hard fail (exit 1):
//   - nodePiercings 가 baseline보다 증가 (엣지가 무관한 노드를 관통 — 렌더러 반중립 신호)
//   - collinear 렌더 실패가 새로 발생 (한 지점에 엣지가 과밀)
// warn (exit 0):
//   - score 가 baseline보다 악화
//   - 레이아웃 의존 예산 초과 (stretch·bends·crossings·labels)
//
// 사용법:
//   node tools/check_boards.mjs            점검
//   node tools/check_boards.mjs --update   현재 상태를 baseline으로 기록

import { execFileSync } from "node:child_process";
import { writeFileSync, readFileSync, existsSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { toBoard } from "./board_adapter.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = dirname(HERE);
const INST_DIR = join(ROOT, "data", "institutions");
const CONSTRUCTION_DIR = join(ROOT, "data", "construction-regulations");
const BASELINE = join(HERE, "board-baseline.json");
const BOARD_CLI = join(ROOT, "node_modules", "korea100studio", "scripts", "board.mjs");

const UPDATE = process.argv.includes("--update");

function fail(msg) {
  console.error(`\n${msg}`);
  process.exit(1);
}

if (!existsSync(BOARD_CLI)) {
  fail("korea100studio가 설치돼 있지 않습니다. `npm install`을 먼저 실행하세요.\n" +
       "(품질 게이트는 개발용 선택 도구입니다. 데이터 검증은 python3 tools/validate.py가 담당합니다.)");
}

// audit 한 판. 렌더 실패(collinear 등)는 renderError로 캡처한다.
function audit(board) {
  const dir = mkdtempSync(join(tmpdir(), "board-"));
  const f = join(dir, "b.json");
  try {
    writeFileSync(f, JSON.stringify(board));
    try {
      const out = execFileSync("node", [BOARD_CLI, "audit", f, "--json", "--profile", "gov"],
                               { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
      const parsed = JSON.parse(out);
      return { ok: true, score: parsed.score, ...parsed.metrics };
    } catch (e) {
      const err = (e.stderr || e.stdout || String(e)).trim();
      const m = err.match(/error:\s*(.+)/);
      return { ok: false, renderError: m ? m[1] : err.split("\n")[0] };
    }
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

// --- 전 제도 audit ---
import { readdirSync } from "node:fs";
const files = readdirSync(INST_DIR).filter((f) => f.endsWith(".json")).sort();
const results = {};
for (const f of files) {
  const inst = JSON.parse(readFileSync(join(INST_DIR, f), "utf8"));
  if (!inst.process) continue;
  results[inst.slug] = audit(toBoard(inst));
}

const constructionFiles = readdirSync(CONSTRUCTION_DIR)
  .filter((f) => f.endsWith(".json") && f !== "manifest.json")
  .sort();
for (const f of constructionFiles) {
  const item = JSON.parse(readFileSync(join(CONSTRUCTION_DIR, f), "utf8"));
  if (!item.processBoard) continue;
  // Catalog-generated boards share the versioned workflow templates and are all
  // validated/rendered with korea100studio --strict by build_construction_boards.mjs.
  // Keep this regression baseline for hand-maintained boards; otherwise 129 nearly
  // identical CLI subprocesses make the faster regression check needlessly expensive.
  if (item.generatedFrom) continue;
  const publicModels = item.publicModels || [];
  if (!publicModels.length) {
    results[`construction/${item.slug}`] = audit(item.processBoard);
    continue;
  }
  for (const spec of publicModels) {
    const nodeIds = new Set(spec.nodeIds);
    const nodes = item.processBoard.nodes.filter((node) => nodeIds.has(node.id));
    const usedLanes = new Set(nodes.map((node) => node.lane));
    const usedStages = new Set(nodes.map((node) => node.stage));
    results[`construction/${spec.slug}`] = audit({
      schema_version: item.processBoard.schema_version,
      profile: item.processBoard.profile,
      title: spec.name,
      subtitle: spec.oneLiner,
      lanes: item.processBoard.lanes.filter((lane) => usedLanes.has(lane)),
      stages: item.processBoard.stages.filter((stage) => usedStages.has(stage)),
      nodes,
      edges: spec.edges,
    });
  }
}

// --- baseline ---
if (UPDATE) {
  writeFileSync(BASELINE, JSON.stringify(results, null, 2) + "\n");
  console.log(`baseline 갱신 — ${Object.keys(results).length}개 보드`);
  console.log(`  ${BASELINE}`);
  process.exit(0);
}

const base = existsSync(BASELINE) ? JSON.parse(readFileSync(BASELINE, "utf8")) : {};
if (!existsSync(BASELINE)) {
  console.log("baseline이 없습니다. 현재 상태를 기록합니다.\n");
}

// --- 표 출력 + 판정 ---
const P = (s, n) => String(s).padEnd(n);
console.log(P("제도", 34) + P("piercing", 10) + P("crossings", 11) + P("stretch", 9) + P("score", 8) + "상태");
console.log("─".repeat(84));

let hardFail = false;
let warn = false;
const budgets = { crossings: 6, bendsPerEdgeMax: 4, routeStretchMax: 2.2, adjustedLabels: 4 };

for (const [slug, r] of Object.entries(results)) {
  const b = base[slug];
  let status = "ok";

  if (!r.ok) {
    // 렌더 실패. baseline에도 같은 실패가 있으면 알려진 상태, 새로 생기면 hard fail.
    const known = b && !b.ok;
    status = known ? `알려진 렌더한계(${r.renderError.split(":")[0]})` : `!! 신규 렌더실패: ${r.renderError}`;
    if (!known) { hardFail = true; }
    console.log(P(slug, 34) + P("—", 10) + P("—", 11) + P("—", 9) + P("—", 8) + status);
    continue;
  }

  const flags = [];
  // hard: piercing 증가
  if (b && b.ok && r.nodePiercings > (b.nodePiercings ?? 0)) {
    flags.push(`piercing↑ ${b.nodePiercings}→${r.nodePiercings}`);
    hardFail = true;
  } else if (r.nodePiercings > 0) {
    flags.push(b ? `piercing ${r.nodePiercings}(기존)` : `신규 piercing ${r.nodePiercings}`);
    if (!b) hardFail = true;
  }
  // warn: score 악화
  if (b && b.ok && b.score != null && r.score > b.score + 0.5) {
    flags.push(`score↑ ${b.score}→${r.score}`);
    warn = true;
  }
  // warn: 레이아웃 의존 예산 초과 (절대 실패는 아님)
  for (const [k, lim] of Object.entries(budgets)) {
    if (r[k] > lim) {
      flags.push(`${k} ${r[k]}>${lim}`);
      if (b) warn = true;
      else hardFail = true;
    }
  }
  if (!b && !flags.length) status = "신규 보드 · strict clean";
  if (flags.length) status = flags.join(", ");

  console.log(
    P(slug, 34) +
    P(r.nodePiercings, 10) +
    P(r.crossings, 11) +
    P(r.routeStretchMax, 9) +
    P(r.score, 8) +
    status,
  );
}

console.log("─".repeat(84));
console.log("piercing/collinear = 그래프 구조 신호(렌더러 반중립) · stretch 등 = board-v1 레이아웃 의존(참고)");

if (!existsSync(BASELINE)) {
  writeFileSync(BASELINE, JSON.stringify(results, null, 2) + "\n");
  console.log(`\nbaseline 생성됨: ${BASELINE}`);
  process.exit(0);
}

if (hardFail) {
  fail("실패 — 노드 관통이 늘었거나 새 렌더 실패가 생겼습니다. 해당 보드의 그래프 구조를 확인하세요.\n" +
       "(구조가 실제 제도 모습이라 불가피하면 --update로 baseline을 갱신하세요.)");
}
if (warn) {
  console.log("\n경고 — 레이아웃 지표가 예산을 넘거나 score가 악화됐습니다. 우리 렌더에는 무해할 수 있으나 확인 권장.");
}
console.log(warn ? "" : "\n통과 — baseline 대비 구조 회귀 없음.");
