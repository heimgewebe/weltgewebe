import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import test from "node:test";
import {
  collectInitialAssetReferences,
  measureRoute,
  resolveBuildDirectory,
  validateRouteBudget,
} from "./assert-route-performance-budget.mjs";

test("collects initial assets once and ignores unrelated links", () => {
  const html = `
    <link rel="modulepreload" href="./_app/a.js">
    <link href='./_app/a.js' rel='modulepreload'>
    <link rel="stylesheet" href="./_app/a.css?version=1">
    <link rel="icon" href="/favicon.svg">
  `;
  assert.deepEqual(collectInitialAssetReferences(html), [
    "./_app/a.js",
    "./_app/a.css",
  ]);
});

test("measures gzip bytes and detects forbidden CSS", () => {
  const root = mkdtempSync(join(tmpdir(), "route-budget-"));
  mkdirSync(join(root, "_app"));
  writeFileSync(
    join(root, "login.html"),
    '<link rel="modulepreload" href="./_app/a.js"><link rel="stylesheet" href="./_app/a.css">',
  );
  writeFileSync(join(root, "_app/a.js"), "export const answer = 42;\n");
  writeFileSync(join(root, "_app/a.css"), ".maplibregl-map{display:block}\n");

  const metrics = measureRoute({ buildDir: root, routeFile: "login.html" });
  assert.ok(metrics.initial_js_gzip_bytes > 0);
  assert.ok(metrics.initial_css_gzip_bytes > 0);
  assert.deepEqual(
    validateRouteBudget(metrics, {
      min_initial_js_assets: 1,
      min_initial_css_assets: 1,
      max_initial_js_gzip_bytes: 10_000,
      max_initial_css_gzip_bytes: 10_000,
      forbid_css_markers: [".maplibregl-"],
      require_css_markers: [".required-control"],
    }),
    [
      'login.html: forbidden CSS marker ".maplibregl-" found in ./_app/a.css',
      'login.html: required CSS marker ".required-control" was not found',
    ],
  );
});

test("rejects route asset traversal", () => {
  const root = mkdtempSync(join(tmpdir(), "route-budget-traversal-"));
  writeFileSync(
    join(root, "login.html"),
    '<link rel="modulepreload" href="../route-budget-traversal.js">',
  );
  assert.throws(
    () => measureRoute({ buildDir: root, routeFile: "login.html" }),
    /escapes build directory/,
  );
});

test("selects only an adapter output containing every budgeted route", () => {
  const root = mkdtempSync(join(tmpdir(), "route-budget-output-"));
  const staticOutput = join(root, ".vercel/output/static");
  const localOutput = join(root, "build");
  mkdirSync(staticOutput, { recursive: true });
  mkdirSync(localOutput, { recursive: true });
  writeFileSync(join(staticOutput, "login.html"), "vercel");
  writeFileSync(join(localOutput, "login.html"), "local");
  writeFileSync(join(localOutput, "settings.html"), "local");

  const routeFiles = ["login.html", "settings.html"];
  assert.equal(
    resolveBuildDirectory({ root, routeFiles, preferVercel: true }),
    resolve(localOutput),
  );

  writeFileSync(join(staticOutput, "settings.html"), "vercel");
  assert.equal(
    resolveBuildDirectory({ root, routeFiles, preferVercel: false }),
    resolve(localOutput),
  );
  assert.equal(
    resolveBuildDirectory({ root, routeFiles, preferVercel: true }),
    resolve(staticOutput),
  );
});

test("fails closed when initial asset discovery yields no JS or CSS", () => {
  const errors = validateRouteBudget(
    {
      route: "login.html",
      initial_js_asset_count: 0,
      initial_js_gzip_bytes: 0,
      initial_css_asset_count: 0,
      initial_css_gzip_bytes: 0,
      stylesheet_contents: [],
    },
    {
      min_initial_js_assets: 1,
      min_initial_css_assets: 1,
      max_initial_js_gzip_bytes: 10_000,
      max_initial_css_gzip_bytes: 10_000,
      forbid_css_markers: [],
      require_css_markers: [],
    },
  );
  assert.deepEqual(errors, [
    "login.html: initial_js_asset_count 0 is below 1",
    "login.html: initial_css_asset_count 0 is below 1",
  ]);
});
