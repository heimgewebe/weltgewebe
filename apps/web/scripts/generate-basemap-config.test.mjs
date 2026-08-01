import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { after, test } from "node:test";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const scriptPath = path.join(scriptDir, "generate-basemap-config.js");
const generatedPath = path.resolve(
  scriptDir,
  "..",
  "src",
  "lib",
  "generated",
  "basemapConfig.ts",
);

function runGenerator(extraEnv = {}) {
  const env = { ...process.env };
  delete env.PUBLIC_BASEMAP_MODE;
  delete env.PUBLIC_BASEMAP_VARIANT;
  Object.assign(env, extraEnv);
  return spawnSync(process.execPath, [scriptPath], {
    cwd: path.resolve(scriptDir, ".."),
    env,
    encoding: "utf8",
  });
}

function generatedConfig() {
  return fs.readFileSync(generatedPath, "utf8");
}

after(() => {
  const result = runGenerator();
  assert.equal(result.status, 0, result.stderr);
});

test("defaults local sovereign builds to the regional rollback variant", () => {
  const result = runGenerator();
  assert.equal(result.status, 0, result.stderr);
  assert.match(generatedConfig(), /mode: "local-sovereign"/);
  assert.match(generatedConfig(), /variant: "regional"/);
});

test("emits the Germany variant only when explicitly selected", () => {
  const result = runGenerator({
    PUBLIC_BASEMAP_MODE: "local-sovereign",
    PUBLIC_BASEMAP_VARIANT: "germany",
  });
  assert.equal(result.status, 0, result.stderr);
  assert.match(generatedConfig(), /variant: "germany"/);
  assert.doesNotMatch(generatedConfig(), /basemaps\.cartocdn\.com/);
});

test("fails closed on an unknown sovereign variant", () => {
  const result = runGenerator({
    PUBLIC_BASEMAP_MODE: "local-sovereign",
    PUBLIC_BASEMAP_VARIANT: "planet",
  });
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /Invalid PUBLIC_BASEMAP_VARIANT='planet'/);
});

test("rejects a meaningless variant on remote-style builds", () => {
  const result = runGenerator({
    PUBLIC_BASEMAP_MODE: "remote-style",
    PUBLIC_BASEMAP_VARIANT: "germany",
  });
  assert.notEqual(result.status, 0);
  assert.match(
    result.stderr,
    /PUBLIC_BASEMAP_VARIANT is only valid with PUBLIC_BASEMAP_MODE=local-sovereign/,
  );
});
