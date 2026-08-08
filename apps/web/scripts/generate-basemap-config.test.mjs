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

function runGenerator(
  extraEnv = {},
  { includePublicSourceCommit = true } = {},
) {
  const env = { ...process.env };
  delete env.PUBLIC_BASEMAP_MODE;
  delete env.PUBLIC_BASEMAP_VARIANT;
  delete env.PUBLIC_SOURCE_COMMIT;
  delete env.GIT_COMMIT_SHA;
  // Host may set VERCEL during CI agents; defaults must stay non-Vercel unless requested.
  delete env.VERCEL;
  if (includePublicSourceCommit) {
    env.PUBLIC_SOURCE_COMMIT = sourceCommit;
  }
  Object.assign(env, extraEnv);
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

test("defaults local sovereign builds to nationwide Germany", () => {
  const result = runGenerator();
  assert.equal(result.status, 0, result.stderr);
  assert.match(generatedConfig(), /mode: "local-sovereign"/);
  assert.match(generatedConfig(), /variant: "germany"/);
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

test("keeps the regional variant as an explicit rollback", () => {
  const result = runGenerator({
    PUBLIC_BASEMAP_MODE: "local-sovereign",
    PUBLIC_BASEMAP_VARIANT: "regional",
  });
  assert.equal(result.status, 0, result.stderr);
  assert.match(generatedConfig(), /variant: "regional"/);
  assert.doesNotMatch(generatedConfig(), /basemaps\.cartocdn\.com/);
  assert.deepEqual(buildIdentity(), {
    schema_version: 1,
    mode: "local-sovereign",
    variant: "regional",
    style_path: "/local-basemap/style.json",
    source_commit: sourceCommit,
    style_sha256: sha256File(path.join(repoRoot, "map-style", "style.json")),
  });
});

test("emits a remote identity without a sovereign variant", () => {
  const result = runGenerator({ PUBLIC_BASEMAP_MODE: "remote-style" });
  assert.equal(result.status, 0, result.stderr);
  assert.match(generatedConfig(), /darkStyleUrl:/);
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

test("uses the reconciler-supplied commit when the build has no explicit public commit", () => {
  const archiveCommit = "89abcdef0123456789abcdef0123456789abcdef";
  const result = runGenerator(
    { GIT_COMMIT_SHA: archiveCommit },
    { includePublicSourceCommit: false },
  );
  assert.equal(result.status, 0, result.stderr);
  assert.equal(buildIdentity().source_commit, archiveCommit);
});

test("keeps PUBLIC_SOURCE_COMMIT authoritative over the generic build commit", () => {
  const result = runGenerator({
    GIT_COMMIT_SHA: "89abcdef0123456789abcdef0123456789abcdef",
  });
  assert.equal(result.status, 0, result.stderr);
  assert.equal(buildIdentity().source_commit, sourceCommit);
});

test("rejects a non-canonical reconciler build commit", () => {
  const result = runGenerator(
    { GIT_COMMIT_SHA: "short" },
    { includePublicSourceCommit: false },
  );
  assert.notEqual(result.status, 0);
  assert.match(
    result.stderr,
    /GIT_COMMIT_SHA must be a full lowercase Git SHA/,
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

test("on Vercel without explicit mode selects remote-style", () => {
  const result = runGenerator({ VERCEL: "1" });
  assert.equal(result.status, 0, result.stderr);
  assert.match(generatedConfig(), /mode: "remote-style"/);
  assert.deepEqual(buildIdentity(), {
    schema_version: 1,
    mode: "remote-style",
    style_url: remoteStyleUrl,
    source_commit: sourceCommit,
  });
});

test("explicit local-sovereign on Vercel remains local when light and dark styles are delivered", () => {
  const deliveredDir = path.join(webRoot, "static", "local-basemap");
  const deliveredStyle = path.join(deliveredDir, "style-germany.json");
  const deliveredDarkStyle = path.join(deliveredDir, "style-germany-dark.json");
  fs.mkdirSync(deliveredDir, { recursive: true });
  fs.copyFileSync(
    path.join(repoRoot, "map-style", "style-germany.json"),
    deliveredStyle,
  );
  fs.copyFileSync(
    path.join(repoRoot, "map-style", "style-germany-dark.json"),
    deliveredDarkStyle,
  );
  try {
    const result = runGenerator({
      VERCEL: "1",
      PUBLIC_BASEMAP_MODE: "local-sovereign",
    });
    assert.equal(result.status, 0, result.stderr);
    assert.match(generatedConfig(), /mode: "local-sovereign"/);
    assert.match(generatedConfig(), /variant: "germany"/);
  } finally {
    fs.rmSync(deliveredStyle, { force: true });
    fs.rmSync(deliveredDarkStyle, { force: true });
    try {
      fs.rmdirSync(deliveredDir);
    } catch {
      // directory may contain unrelated leftovers; leave it
    }
  }
});

test("explicit local-sovereign on Vercel fails closed without delivered style", () => {
  const deliveredStyle = path.join(
    webRoot,
    "static",
    "local-basemap",
    "style-germany.json",
  );
  const deliveredDarkStyle = path.join(
    webRoot,
    "static",
    "local-basemap",
    "style-germany-dark.json",
  );
  fs.rmSync(deliveredStyle, { force: true });
  fs.rmSync(deliveredDarkStyle, { force: true });
  const result = runGenerator({
    VERCEL: "1",
    PUBLIC_BASEMAP_MODE: "local-sovereign",
  });
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /not delivered/);
});

test("non-Vercel without explicit mode keeps the policy default", () => {
  const result = runGenerator();
  assert.equal(result.status, 0, result.stderr);
  assert.match(generatedConfig(), /mode: "local-sovereign"/);
});
