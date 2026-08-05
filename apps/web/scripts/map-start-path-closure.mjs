#!/usr/bin/env node
import { readFileSync } from "node:fs";
import {
  dirname,
  extname,
  isAbsolute,
  relative,
  resolve,
  sep,
} from "node:path";
import { fileURLToPath } from "node:url";
import { gzipSync } from "node:zlib";
import { collectInitialAssetReferences } from "./route-performance-budget-html.mjs";

const scriptPath = fileURLToPath(import.meta.url);
export const webRoot = resolve(dirname(scriptPath), "..");

function normalizeAsset(reference) {
  return reference.replace(/^\.\//, "").replace(/^\//, "");
}

function resolveInside(root, reference) {
  const path = resolve(root, normalizeAsset(reference));
  const fromRoot = relative(root, path);
  if (
    fromRoot === ".." ||
    fromRoot.startsWith(".." + sep) ||
    isAbsolute(fromRoot)
  ) {
    throw new Error(`asset escapes build directory: ${reference}`);
  }
  return path;
}

function manifestFileIndex(manifest) {
  const index = new Map();
  for (const [key, record] of Object.entries(manifest)) {
    if (record && typeof record.file === "string") index.set(record.file, key);
  }
  return index;
}

export function collectStaticManifestClosure(manifest, initialAssets) {
  const fileIndex = manifestFileIndex(manifest);
  const assets = new Set(initialAssets.map(normalizeAsset));
  const visited = new Set();
  const missingManifestEntries = [];

  function visitKey(key) {
    if (visited.has(key)) return;
    visited.add(key);
    const record = manifest[key];
    if (!record) throw new Error(`manifest import is missing: ${key}`);
    if (typeof record.file === "string") assets.add(record.file);
    for (const css of record.css ?? []) assets.add(css);
    for (const imported of record.imports ?? []) visitKey(imported);
  }

  for (const asset of [...assets]) {
    if (extname(asset) !== ".js") continue;
    const key = fileIndex.get(asset);
    if (key) visitKey(key);
    else missingManifestEntries.push(asset);
  }
  return {
    assets: [...assets].sort(),
    manifestKeys: [...visited].sort(),
    missingManifestEntries: missingManifestEntries.sort(),
  };
}

export function findMapRuntimeEntry(manifest) {
  const matches = Object.entries(manifest).filter(([, record]) =>
    (record.dynamicImports ?? []).some((key) =>
      key.endsWith("src/lib/map/overlay/nodes.ts"),
    ),
  );
  if (matches.length !== 1) {
    throw new Error(`expected one map runtime entry, found ${matches.length}`);
  }
  return matches[0][0];
}

function measureAssets(buildDir, assetNames) {
  const assets = assetNames.map((name) => {
    const bytes = readFileSync(resolveInside(buildDir, name));
    return {
      path: name,
      kind:
        extname(name) === ".js"
          ? "js"
          : extname(name) === ".css"
            ? "css"
            : "other",
      raw_bytes: bytes.byteLength,
      gzip_bytes: gzipSync(bytes, { level: 9, mtime: 0 }).byteLength,
    };
  });
  const summary = (kind) => {
    const selected = assets.filter((asset) => asset.kind === kind);
    return {
      asset_count: selected.length,
      raw_bytes: selected.reduce((sum, asset) => sum + asset.raw_bytes, 0),
      gzip_bytes: selected.reduce((sum, asset) => sum + asset.gzip_bytes, 0),
    };
  };
  return { js: summary("js"), css: summary("css"), assets };
}

export function measureMapStartPath({ buildDir, manifestPath }) {
  const html = readFileSync(resolve(buildDir, "map.html"), "utf8");
  const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
  const initialAssets = collectInitialAssetReferences(html).map(normalizeAsset);
  const staticClosure = collectStaticManifestClosure(manifest, initialAssets);
  const mapRuntimeKey = findMapRuntimeEntry(manifest);
  const dynamicFrontier = (manifest[mapRuntimeKey].dynamicImports ?? []).map(
    (key) => {
      const record = manifest[key];
      if (!record || typeof record.file !== "string") {
        return { key, file: null, name: null };
      }
      return { key, file: record.file, name: record.name ?? null };
    },
  );
  const initial = measureAssets(buildDir, initialAssets);
  const closure = measureAssets(buildDir, staticClosure.assets);
  const initialSet = new Set(initialAssets);
  const additional = measureAssets(
    buildDir,
    staticClosure.assets.filter((asset) => !initialSet.has(asset)),
  );
  return {
    schema_version: 1,
    route: "/map",
    build_directory: buildDir,
    manifest_path: manifestPath,
    html_initial: initial,
    static_import_closure: closure,
    additional_static_imports: additional,
    missing_manifest_entries: staticClosure.missingManifestEntries,
    dynamic_frontier: dynamicFrontier,
    limitations: [
      "The dynamic frontier is reported but not counted as initial transfer.",
      "Request timing for interaction-only chunks is verified by Playwright.",
      "This measurement does not establish runtime latency or network cache behaviour.",
    ],
  };
}

function parseArguments(args) {
  const options = {
    buildDir: resolve(webRoot, "build"),
    manifestPath: resolve(
      webRoot,
      ".svelte-kit/output/client/.vite/manifest.json",
    ),
    json: false,
  };
  for (let index = 0; index < args.length; index += 1) {
    const argument = args[index];
    if (argument === "--json") options.json = true;
    else if (argument === "--build-dir" || argument === "--manifest") {
      const value = args[index + 1];
      if (!value) throw new Error(`${argument} requires a value`);
      const path = isAbsolute(value) ? value : resolve(webRoot, value);
      if (argument === "--build-dir") options.buildDir = path;
      else options.manifestPath = path;
      index += 1;
    } else throw new Error(`unsupported argument: ${argument}`);
  }
  return options;
}

function format(result) {
  const initial = result.html_initial;
  const closure = result.static_import_closure;
  const additional = result.additional_static_imports;
  return [
    "map start-path closure",
    `build directory: ${result.build_directory}`,
    `HTML initial: JS ${initial.js.gzip_bytes} B gzip (${initial.js.asset_count} assets) / CSS ${initial.css.gzip_bytes} B gzip (${initial.css.asset_count} assets)`,
    `static import closure: JS ${closure.js.gzip_bytes} B gzip (${closure.js.asset_count} assets) / CSS ${closure.css.gzip_bytes} B gzip (${closure.css.asset_count} assets)`,
    `additional static imports: JS ${additional.js.gzip_bytes} B gzip (${additional.js.asset_count} assets) / CSS ${additional.css.gzip_bytes} B gzip (${additional.css.asset_count} assets)`,
    `dynamic frontier: ${result.dynamic_frontier.length} roots (reported, not counted)`,
  ].join("\n");
}

const isMain =
  process.argv[1] && resolve(process.argv[1]) === resolve(scriptPath);
if (isMain) {
  const options = parseArguments(process.argv.slice(2));
  const result = measureMapStartPath(options);
  console.log(options.json ? JSON.stringify(result, null, 2) : format(result));
}
