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

if (!existsSync(BOARD_CLI)) {
  fail("korea100studio is not installed; run `npm ci` first");
}

mkdirSync(OUTPUT_DIR, { recursive: true });
const files = readdirSync(DATA_DIR)
  .filter((name) => name.endsWith(".json") && name !== "manifest.json")
  .sort()
  .filter((_, index) => index % shardCount === shardIndex);

let rendered = 0;
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
    const nodeIds = new Set(spec.nodeIds);
    const nodes = sourceBoard.nodes.filter((node) => nodeIds.has(node.id));
    const usedLanes = new Set(nodes.map((node) => node.lane));
    const usedStages = new Set(nodes.map((node) => node.stage));
    targets.push({
      id: spec.slug,
      outputName: `${spec.slug}.svg`,
      board: {
        schema_version: sourceBoard.schema_version,
        profile: sourceBoard.profile,
        title: spec.name,
        subtitle: spec.oneLiner,
        lanes: sourceBoard.lanes.filter((lane) => usedLanes.has(lane)),
        stages: sourceBoard.stages.filter((stage) => usedStages.has(stage)),
        nodes,
        edges: spec.edges,
      },
    });
  }

  for (const target of targets) {
    const scratch = mkdtempSync(join(tmpdir(), "construction-board-"));
    const boardPath = join(scratch, `${target.id}.json`);
    const outputPath = join(OUTPUT_DIR, target.outputName);
    try {
      writeFileSync(boardPath, `${JSON.stringify(target.board, null, 2)}\n`);
      execFileSync(
        "node",
        [BOARD_CLI, "validate", boardPath, "--strict", "--profile", "gov"],
        { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] },
      );
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
  (shardCount > 1 ? ` (shard ${shardIndex}/${shardCount})` : ""),
);
