import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const packageJson = JSON.parse(
  readFileSync(new URL("../package.json", import.meta.url), "utf8"),
);
const scripts = packageJson.scripts;

test("production and E2E builds share preparation and finalization", () => {
  assert.match(scripts.build, /pnpm run build:prepare/);
  assert.match(scripts.build, /pnpm run build:finalize/);
  assert.match(scripts["build:e2e"], /pnpm run build:prepare/);
  assert.match(scripts["build:e2e"], /pnpm run build:finalize/);
  assert.match(scripts["build:e2e"], /vite build --mode test/);
  assert.doesNotMatch(scripts["build:e2e"], /assert-route-performance-budget/);
});
