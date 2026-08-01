import assert from "node:assert/strict";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { after, test } from "node:test";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(scriptDir, "..");
const repoRoot = path.resolve(webRoot, "..", "..");
const scriptPath = path.join(scriptDir, "generate-basemap-config.js");
const generatedPath = path.join(
  webRoot,
  "src",
  "lib",
  "generated",
  "basemapConfig.ts",
);
const buildIdentityPath = path.join(
  webRoot,
  "static",
  "_app",
  "basemap-build.json",
);
const remoteStyleUrl =
  "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json";
const sourceCommit = "0123456789abcdef0123456789abcdef01234567";

const sha256File = (filePath) =>
  crypto.createHash("sha256").update(fs.readFileSync(filePath)).digest("hex");

function runGenerator(extraEnv = {}) {
  const env = { ...process.env };
  delete env.PUBLIC_BASEMAP_MODE;
  delete env.PUBLIC_BASEMAP_VARIANT;
  delete env.PUBLIC_SOURCE_COMMIT;
  Object.assign(env, { PUBLIC_SOURCE_COMMIT: sourceCommit }, extraEnv);
  return spawnSync(process.execPath, [scriptPath], {
    cwd: webRoot,
    env,
    encoding: "utf8",
  });
}

function generatedConfig() {
  return fs.readFileSync(generatedPath, "utf8");
}

function buildIdentity() {
  return JSON.parse(fs.readFileSync(buildIdentityPath, "utf8"));
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
  assert.deepEqual(buildIdentity(), {
    schema_version: 1,
    mode: "local-sovereign",
    variant: "regional",
    style_path: "/local-basemap/style.json",
    source_commit: sourceCommit,
    style_sha256: sha256File(path.join(repoRoot, "map-style", "style.json")),
  });
});

test("emits the Germany variant only when explicitly selected", () => {
  const result = runGenerator({
    PUBLIC_BASEMAP_MODE: "local-sovereign",
    PUBLIC_BASEMAP_VARIANT: "germany",
  });
  assert.equal(result.status, 0, result.stderr);
  assert.match(generatedConfig(), /variant: "germany"/);
  assert.doesNotMatch(generatedConfig(), /basemaps\.cartocdn\.com/);
  assert.deepEqual(buildIdentity(), {
    schema_version: 1,
    mode: "local-sovereign",
    variant: "germany",
    style_path: "/local-basemap/style-germany.json",
    source_commit: sourceCommit,
    style_sha256: sha256File(
      path.join(repoRoot, "map-style", "style-germany.json"),
    ),
  });
});

test("emits a remote identity without a sovereign variant", () => {
  const result = runGenerator({ PUBLIC_BASEMAP_MODE: "remote-style" });
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(buildIdentity(), {
    schema_version: 1,
    mode: "remote-style",
    style_url: remoteStyleUrl,
    source_commit: sourceCommit,
  });
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

test("rejects a non-canonical source commit", () => {
  const result = runGenerator({ PUBLIC_SOURCE_COMMIT: "short" });
  assert.notEqual(result.status, 0);
  assert.match(
    result.stderr,
    /PUBLIC_SOURCE_COMMIT must be a full lowercase Git SHA/,
  );
});
