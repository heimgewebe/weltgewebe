import assert from "node:assert/strict";
import {
  mkdtempSync,
  mkdirSync,
  rmSync,
  symlinkSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import test from "node:test";
import { parseCliArguments } from "./assert-route-performance-budget.mjs";
import {
  parsePerformanceBudget,
  routeIdToHtmlFile,
  validatePerformanceBudget,
} from "./route-performance-budget-config.mjs";
import {
  measureRoute,
  resolveBuildDirectory,
  validateEmittedAssetBudgets,
  validateRouteBudget,
} from "./route-performance-budget-core.mjs";
import { collectInitialAssetReferences } from "./route-performance-budget-html.mjs";

function temporaryDirectory(t, prefix) {
  const root = mkdtempSync(join(tmpdir(), prefix));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  return root;
}

function routeBudget(overrides = {}) {
  return {
    min_initial_js_assets: 1,
    min_initial_css_assets: 1,
    max_initial_js_gzip_bytes: 10_000,
    max_initial_css_gzip_bytes: 10_000,
    forbid_css_markers: [],
    require_css_markers: [],
    ...overrides,
  };
}

function validBudget(overrides = {}) {
  return {
    schema_version: 2,
    measurement: "test",
    output_directories: ["build", ".vercel/output/static"],
    routes: { "/login": routeBudget() },
    emitted_assets: {},
    ...overrides,
  };
}

test("collects quoted and unquoted initial assets without parsing comments or scripts", () => {
  const html = `
    <!-- <link rel="stylesheet" href="./ignored.css"> -->
    <script>const fake = '<link rel="stylesheet" href="./ignored-script.css">';</script>
    <scripture><link rel="stylesheet" href="./scripture.css"></scripture>
    <link rel=modulepreload href=./_app/a.js>
    <link href='./_app/a.js' rel='modulepreload'>
    <link rel="stylesheet" href="./_app/a>b.css?version=1">
    <link rel="icon" href="/favicon.svg">
  `;
  assert.deepEqual(collectInitialAssetReferences(html), [
    "./scripture.css",
    "./_app/a.js",
    "./_app/a>b.css",
  ]);
});

test("fails closed on malformed or external initial assets", () => {
  assert.throws(
    () =>
      collectInitialAssetReferences(
        '<link rel="stylesheet" href="https://fonts.example/style.css">',
      ),
    /External initial asset cannot be measured/,
  );
  assert.throws(
    () => collectInitialAssetReferences('<link rel="stylesheet" href="broken>'),
    /Unterminated HTML tag|Unterminated quoted/,
  );
  assert.throws(
    () =>
      collectInitialAssetReferences(
        '<link rel="stylesheet" rel="modulepreload" href="a.css">',
      ),
    /Duplicate <link> attribute rel/,
  );
});

test("measures nested route references and multiple stylesheets", (t) => {
  const root = temporaryDirectory(t, "route-budget-nested-");
  mkdirSync(join(root, "auth/step-up"), { recursive: true });
  mkdirSync(join(root, "_app"));
  writeFileSync(
    join(root, "auth/step-up/consume.html"),
    '<link rel="modulepreload" href="../../_app/a.js"><link rel="stylesheet" href="../../_app/a.css"><link rel=stylesheet href=../../_app/b.css>',
  );
  writeFileSync(join(root, "_app/a.js"), "export const answer = 42;\n");
  writeFileSync(join(root, "_app/a.css"), ".maplibregl-map{display:block}\n");
  writeFileSync(join(root, "_app/b.css"), ".second{display:block}\n");

  const metrics = measureRoute({
    buildDir: root,
    routeId: "/auth/step-up/consume",
    routeFile: "auth/step-up/consume.html",
  });
  assert.equal(metrics.initial_js_asset_count, 1);
  assert.equal(metrics.initial_css_asset_count, 2);
  assert.ok(metrics.initial_js_gzip_bytes > 0);
  assert.ok(metrics.initial_css_gzip_bytes > 0);
  assert.deepEqual(
    validateRouteBudget(
      metrics,
      routeBudget({
        forbid_css_markers: [".maplibregl-"],
        require_css_markers: [".required-control"],
      }),
    ),
    [
      '/auth/step-up/consume: forbidden CSS marker ".maplibregl-" found in ../../_app/a.css',
      '/auth/step-up/consume: required CSS marker ".required-control" was not found',
    ],
  );
});

test("rejects intermediate symlink escapes", (t) => {
  const root = temporaryDirectory(t, "route-budget-symlink-root-");
  const outside = temporaryDirectory(t, "route-budget-symlink-outside-");
  writeFileSync(
    join(root, "login.html"),
    '<link rel="modulepreload" href="./nested/a.js">',
  );
  writeFileSync(join(outside, "a.js"), "export const escaped = true;\n");
  symlinkSync(outside, join(root, "nested"), "dir");

  assert.throws(
    () =>
      measureRoute({
        buildDir: root,
        routeId: "/login",
        routeFile: "login.html",
      }),
    /resolves outside build directory/,
  );
});

test("rejects route asset traversal and missing regular files", (t) => {
  const root = temporaryDirectory(t, "route-budget-traversal-");
  writeFileSync(
    join(root, "login.html"),
    '<link rel="modulepreload" href="../outside.js">',
  );
  assert.throws(
    () =>
      measureRoute({
        buildDir: root,
        routeId: "/login",
        routeFile: "login.html",
      }),
    /escapes build directory/,
  );
  assert.throws(
    () =>
      measureRoute({
        buildDir: root,
        routeId: "/missing",
        routeFile: "missing.html",
      }),
    /Route HTML does not exist/,
  );
});

test("selects one complete output and rejects stale ambiguity", (t) => {
  const root = temporaryDirectory(t, "route-budget-output-");
  const staticOutput = join(root, ".vercel/output/static");
  const localOutput = join(root, "build");
  mkdirSync(staticOutput, { recursive: true });
  mkdirSync(localOutput, { recursive: true });
  writeFileSync(join(staticOutput, "login.html"), "vercel");
  writeFileSync(join(localOutput, "login.html"), "local");
  writeFileSync(join(localOutput, "settings.html"), "local");

  const arguments_ = {
    root,
    routeFiles: ["login.html", "settings.html"],
    candidates: ["build", ".vercel/output/static"],
  };
  assert.equal(resolveBuildDirectory(arguments_), resolve(localOutput));

  writeFileSync(join(staticOutput, "settings.html"), "vercel");
  assert.throws(
    () => resolveBuildDirectory(arguments_),
    /Multiple complete route build directories found/,
  );
  rmSync(join(localOutput, "settings.html"));
  rmSync(join(staticOutput, "settings.html"));
  assert.throws(
    () => resolveBuildDirectory(arguments_),
    /No complete route build directory found/,
  );
});

test("maps clean route IDs to adapter-static HTML paths", () => {
  assert.equal(routeIdToHtmlFile("/"), "index.html");
  assert.equal(routeIdToHtmlFile("/login"), "login.html");
  assert.equal(
    routeIdToHtmlFile("/auth/step-up/consume"),
    "auth/step-up/consume.html",
  );
  assert.equal(routeIdToHtmlFile("/docs/"), "docs/index.html");
  assert.throws(() => routeIdToHtmlFile("login"), /absolute clean path/);
  assert.throws(() => routeIdToHtmlFile("/a/../b"), /unsafe segment/);
});

test("validates the complete schema instead of accepting magic fields", () => {
  assert.equal(validatePerformanceBudget(validBudget()).schema_version, 2);
  assert.throws(
    () => validatePerformanceBudget(validBudget({ routes: {} })),
    /at least one route/,
  );
  assert.throws(
    () =>
      validatePerformanceBudget(
        validBudget({ routes: { "/login": routeBudget({ typo: 1 }) } }),
      ),
    /unsupported field "typo"/,
  );
  assert.throws(
    () =>
      validatePerformanceBudget(
        validBudget({ output_directories: ["../build"] }),
      ),
    /safe relative directory/,
  );
  assert.throws(() => parsePerformanceBudget("{not-json"), /not valid JSON/);
});

test("keeps positive discovery minima as a parser liveness guard", () => {
  assert.throws(
    () =>
      validatePerformanceBudget(
        validBudget({
          routes: { "/login": routeBudget({ min_initial_css_assets: 0 }) },
        }),
      ),
    /min_initial_css_assets must be an integer >= 1/,
  );
  const errors = validateRouteBudget(
    {
      route: "/login",
      initial_js_asset_count: 0,
      initial_js_gzip_bytes: 0,
      initial_css_asset_count: 0,
      initial_css_gzip_bytes: 0,
      stylesheet_contents: [],
      assets: [],
    },
    routeBudget(),
  );
  assert.deepEqual(errors, [
    "/login: initial_js_asset_count 0 is below 1",
    "/login: initial_css_asset_count 0 is below 1",
  ]);
});

test("reports oversized route assets with per-file context", () => {
  const errors = validateRouteBudget(
    {
      route: "/map",
      initial_js_asset_count: 1,
      initial_js_gzip_bytes: 11,
      initial_css_asset_count: 1,
      initial_css_gzip_bytes: 12,
      stylesheet_contents: [],
      assets: [
        { href: "a.js", kind: "js", gzip_bytes: 11 },
        { href: "a.css", kind: "css", gzip_bytes: 12 },
      ],
    },
    routeBudget({
      max_initial_js_gzip_bytes: 10,
      max_initial_css_gzip_bytes: 10,
    }),
  );
  assert.deepEqual(errors, [
    "/map: initial_js_gzip_bytes 11 exceeds 10; assets: a.js=11B",
    "/map: initial_css_gzip_bytes 12 exceeds 10; assets: a.css=12B",
  ]);
});

test("enforces configurable emitted asset directories and regular files", (t) => {
  const root = temporaryDirectory(t, "emitted-asset-budget-");
  const assetDirectory = join(root, "custom/assets");
  mkdirSync(assetDirectory, { recursive: true });
  writeFileSync(join(assetDirectory, "garnrolle.hash.webp"), "1234");

  const budgets = {
    garnrolle: {
      directory: "custom/assets",
      filename_prefix: "garnrolle.",
      required_extension: ".webp",
      forbid_extensions: [".png"],
      max_bytes: 4,
    },
  };
  assert.deepEqual(
    validateEmittedAssetBudgets({ buildDir: root, budgets }),
    [],
  );

  writeFileSync(join(assetDirectory, "garnrolle.old.png"), "legacy");
  writeFileSync(join(assetDirectory, "garnrolle.hash.webp"), "12345");
  assert.deepEqual(validateEmittedAssetBudgets({ buildDir: root, budgets }), [
    "garnrolle: forbidden emitted asset garnrolle.old.png",
    "garnrolle: emitted asset garnrolle.hash.webp is 5 bytes, exceeds 4",
  ]);

  rmSync(join(assetDirectory, "garnrolle.hash.webp"));
  symlinkSync("target.webp", join(assetDirectory, "garnrolle.hash.webp"));
  assert.match(
    validateEmittedAssetBudgets({ buildDir: root, budgets }).join("\n"),
    /not a regular file/,
  );
});

test("parses CLI arguments without silent or duplicate options", () => {
  assert.deepEqual(
    parseCliArguments(["--build-dir", "build", "--report-only", "--json"]),
    {
      buildDir: "build",
      json: true,
      reportOnly: true,
    },
  );
  assert.deepEqual(parseCliArguments(["--build-dir=build"]), {
    buildDir: "build",
    json: false,
    reportOnly: false,
  });
  assert.throws(() => parseCliArguments(["--unknown"]), /Unsupported argument/);
  assert.throws(
    () => parseCliArguments(["--build-dir", "build", "--build-dir=other"]),
    /may only be provided once/,
  );
  assert.throws(() => parseCliArguments(["--build-dir"]), /requires a value/);
});
