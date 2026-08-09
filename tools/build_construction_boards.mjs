#!/usr/bin/env node
// Render construction processBoard records with the actual korea100studio CLI.

import { execFileSync } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = dirname(HERE);
const DATA_DIR = join(ROOT, "data", "construction-regulations");
const OUTPUT_DIR = join(ROOT, "site", "boards");
const BOARD_CLI = join(ROOT, "node_modules", "korea100studio", "scripts", "board.mjs");
const VERBOSE = process.argv.includes("--verbose");
const shardArg = process.argv.find((value) => value.startsWith("--shard="));
let shardIndex = 0;
let shardCount = 1;
if (shardArg) {
  const match = shardArg.slice("--shard=".length).match(/^(\d+)\/(\d+)$/);
  if (!match || Number(match[2]) < 1 || Number(match[1]) >= Number(match[2])) {
    fail("--shard must use zero-based INDEX/COUNT, for example --shard=0/4");
  }
  shardIndex = Number(match[1]);
  shardCount = Number(match[2]);
}

function fail(message) {
  console.error(`ERROR: ${message}`);
  process.exit(1);
}

// 구조도에 실제로 그릴 간선 라벨만 남긴다.  곧장 다음 단계로 이어지는 간선은
// 화살표만으로 읽히고, 거기까지 라벨을 달면 갈림길과 보완회귀가 글자에 묻힌다.
// 선택이 필요한 곳 — 나가는 길이 둘 이상인 분기, 병렬 흐름 사이의 전달,
// 보완회귀 — 에만 남기고 나머지는 카드 상세에서 읽게 한다.
// 공개 화면은 축마다 절차구간을 G1부터 다시 매긴다(build_site.py). 감사용 SVG가
// 원천 생애주기 번호(G0·G4·C3 …)를 그대로 쓰면 같은 축을 두 번호로 읽게 된다.
function renumberStages(stages) {
  const map = new Map();
  stages.forEach((stage, index) => {
    const [, label = stage] = stage.match(/^\S+\s+(.*)$/) || [];
    map.set(stage, `G${index + 1} ${label}`);
  });
  return map;
}

function displayEdges(edges) {
  const outgoing = new Map();
  for (const edge of edges) {
    outgoing.set(edge.source, (outgoing.get(edge.source) || 0) + 1);
  }
  return edges.map((edge) => {
    if (edge.label && edge.type === "sequence" && (outgoing.get(edge.source) || 0) < 2) {
      const { label, ...rest } = edge;
      return rest;
    }
    return edge;
  });
}

if (!existsSync(BOARD_CLI)) {
  fail("korea100studio is not installed; run `npm ci` first");
}

mkdirSync(OUTPUT_DIR, { recursive: true });
const files = readdirSync(DATA_DIR)
  .filter((name) => name.endsWith(".json") && name !== "manifest.json")
  .sort()
  .filter((_, index) => index % shardCount === shardIndex);

let rendered = 0;
let skipped = 0;
let softBudgetWarnings = 0;
for (const file of files) {
  const sourcePath = join(DATA_DIR, file);
  const data = JSON.parse(readFileSync(sourcePath, "utf8"));
  const sourceBoard = data.processBoard;
  if (!sourceBoard) fail(`${file} is missing processBoard`);

  const publicModels = data.publicModels || [];
  const targets = publicModels.length ? [] : [{
    id: data.slug,
    board: sourceBoard,
    outputName: `${data.slug}-construction.svg`,
  }];
  for (const spec of publicModels) {
    if (spec.procedureStatus === "detail-unverified") {
      // A one-node evidence-entry record is deliberately not a statutory
      // workflow.  Rendering it as a process board would visually imply that
      // the country's official procedure had been mapped when it has not.
      rmSync(join(OUTPUT_DIR, `${spec.slug}.svg`), { force: true });
      skipped += 1;
      continue;
    }
    const nodeIds = new Set(spec.nodeIds);
    const nodes = sourceBoard.nodes.filter((node) => nodeIds.has(node.id));
    const usedLanes = new Set(nodes.map((node) => node.lane));
    const usedStages = new Set(nodes.map((node) => node.stage));
    const axisStages = sourceBoard.stages.filter((stage) => usedStages.has(stage));
    const stageLabels = renumberStages(axisStages);
    targets.push({
      id: spec.slug,
      outputName: `${spec.slug}.svg`,
      board: {
        schema_version: sourceBoard.schema_version,
        profile: sourceBoard.profile,
        title: spec.name,
        subtitle: spec.oneLiner,
        lanes: sourceBoard.lanes.filter((lane) => usedLanes.has(lane)),
        stages: axisStages.map((stage) => stageLabels.get(stage)),
        nodes: nodes.map((node) => ({ ...node, stage: stageLabels.get(node.stage) })),
        edges: displayEdges(spec.edges),
      },
    });
  }

  for (const target of targets) {
    const scratch = mkdtempSync(join(tmpdir(), "construction-board-"));
    const boardPath = join(scratch, `${target.id}.json`);
    const outputPath = join(OUTPUT_DIR, target.outputName);
    try {
      writeFileSync(boardPath, `${JSON.stringify(target.board, null, 2)}\n`);
      // Statutory correction loops can legitimately exceed korea100studio's
      // soft crossing/stretch budgets.  Keep schema/layout failures and node
      // piercings as hard errors, while reporting the soft metrics separately.
      execFileSync(
        "node",
        [BOARD_CLI, "validate", boardPath, "--profile", "gov"],
        { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] },
      );
      const audit = JSON.parse(execFileSync(
        "node",
        [BOARD_CLI, "audit", boardPath, "--json", "--profile", "gov"],
        { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] },
      ));
      if (audit.metrics?.nodePiercings > 0) {
        throw new Error(
          `node-piercing ${audit.metrics.nodePiercings}: ${
            (audit.metrics.piercingOffenders || []).join(", ")
          }`,
        );
      }
      if ((audit.violations || []).length) {
        softBudgetWarnings += 1;
        if (VERBOSE) {
          console.warn(`layout warning ${target.id}: ${audit.violations.join(", ")}`);
        }
      }
      execFileSync(
        "node",
        [BOARD_CLI, "render", boardPath, "--out", outputPath, "--profile", "gov"],
        { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] },
      );
      execFileSync("node", [BOARD_CLI, "check", outputPath], {
        encoding: "utf8",
        stdio: ["ignore", "pipe", "pipe"],
      });
    } catch (error) {
      const detail = String(error.stderr || error.stdout || error.message || error).trim();
      fail(`${target.id}: korea100studio render failed\n${detail}`);
    } finally {
      rmSync(scratch, { recursive: true, force: true });
    }
    rendered += 1;
    if (VERBOSE) console.log(`rendered ${target.id}: ${outputPath}`);
  }
}

console.log(
  `OK: ${rendered} construction board(s) rendered with korea100studio` +
  (skipped ? `; ${skipped} detail-unverified model(s) skipped` : "") +
  (softBudgetWarnings ? `; ${softBudgetWarnings} board(s) over soft layout budgets` : "") +
  (shardCount > 1 ? ` (shard ${shardIndex}/${shardCount})` : ""),
);
