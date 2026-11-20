#!/usr/bin/env node
/**
 * Regenerate tests/fixtures/frontend_mapping_golden.json from the real
 * TypeScript mapper (lib/mapping.ts). Usage:
 *   node scripts/regen_frontend_golden.mjs        # rewrite the fixture
 *   node scripts/regen_frontend_golden.mjs --check # exit 1 when stale
 */
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const tsc = join(root, "node_modules", ".bin", "tsc");
const fixturePath = join(root, "tests", "fixtures", "frontend_mapping_golden.json");

const outDir = mkdtempSync(join(tmpdir(), "awwal-map-"));
try {
  execFileSync(
    tsc,
    [
      join(root, "lib", "mapping.ts"),
      "--outDir", outDir,
      "--module", "commonjs",
      "--target", "es2021",
      "--lib", "es2021,dom",
      "--esModuleInterop",
      "--skipLibCheck",
    ],
    { stdio: "inherit" }
  );
  const require = createRequire(join(root, "package.json"));
  const mapping = require(join(outDir, "mapping.js"));
  const fixture = JSON.parse(readFileSync(fixturePath, "utf-8"));
  const next = {
    _note: fixture._note,
    frontend_answers: fixture.frontend_answers,
    backend_answers: mapping.toBackendAnswers(fixture.frontend_answers),
    reverse_map: mapping.REVERSE_MAP,
    red_flag_questions: mapping.RED_FLAG_QUESTIONS,
  };
  const text = JSON.stringify(next, null, 2) + "\n";
  if (process.argv.includes("--check")) {
    if (text !== readFileSync(fixturePath, "utf-8")) {
      console.error("golden fixture is stale; run node scripts/regen_frontend_golden.mjs");
      process.exit(1);
    }
    console.log("golden fixture is fresh");
  } else {
    writeFileSync(fixturePath, text);
    console.log("golden fixture regenerated");
  }
} finally {
  rmSync(outDir, { recursive: true, force: true });
}
