#!/usr/bin/env node
import { readFileSync } from "node:fs";
import { dirname, extname, resolve, sep } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { gzipSync } from "node:zlib";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const webRoot = resolve(scriptDir, "..");
const defaultBuildDir = resolve(webRoot, "build");
const defaultBudgetPath = resolve(webRoot, "route-performance-budget.json");

function attribute(tag, name) {
  const pattern = new RegExp(
    "(?:^|\\s)" + name + "\\s*=\\s*(?:\"([^\"]*)\"|'([^']*)')",
    "i",
  );
  const match = tag.match(pattern);
  return match?.[1] ?? match?.[2] ?? null;
}

export function collectInitialAssetReferences(html) {
  const references = [];
  const seen = new Set();
  for (const match of html.matchAll(/<link\b[^>]*>/gi)) {
    const tag = match[0];
    const rel = attribute(tag, "rel");
    const href = attribute(tag, "href");
    if (!rel || !href) continue;
    const relTokens = rel.toLowerCase().split(/\s+/);
    if (
      !relTokens.includes("modulepreload") &&
      !relTokens.includes("stylesheet")
    ) {
      continue;
    }
    const cleanHref = href.split(/[?#]/, 1)[0];
    if (!cleanHref || seen.has(cleanHref)) continue;
    seen.add(cleanHref);
    references.push(cleanHref);
  }
  return references;
}

function resolveAssetPath(buildDir, href) {
  let relative = href.replace(/^\.\//, "").replace(/^\//, "");
  try {
    relative = decodeURIComponent(relative);
  } catch {
    throw new Error("Route asset reference is not valid URI encoding: " + href);
  }
  const target = resolve(buildDir, relative);
  const prefix = buildDir.endsWith(sep) ? buildDir : buildDir + sep;
  if (target !== buildDir && !target.startsWith(prefix)) {
    throw new Error("Route asset escapes build directory: " + href);
  }
  return target;
}

export function measureRoute({ buildDir, routeFile }) {
  const routePath = resolveAssetPath(buildDir, routeFile);
  const html = readFileSync(routePath, "utf8");
  const metrics = {
    route: routeFile,
    initial_js_raw_bytes: 0,
    initial_js_gzip_bytes: 0,
    initial_css_raw_bytes: 0,
    initial_css_gzip_bytes: 0,
    stylesheet_contents: [],
    assets: [],
  };

  for (const href of collectInitialAssetReferences(html)) {
    const assetPath = resolveAssetPath(buildDir, href);
    const bytes = readFileSync(assetPath);
    const extension = extname(assetPath).toLowerCase();
    const gzipBytes = gzipSync(bytes, { level: 9, mtime: 0 }).byteLength;
    metrics.assets.push({
      href,
      raw_bytes: bytes.byteLength,
      gzip_bytes: gzipBytes,
    });
    if (extension === ".js") {
      metrics.initial_js_raw_bytes += bytes.byteLength;
      metrics.initial_js_gzip_bytes += gzipBytes;
    } else if (extension === ".css") {
      metrics.initial_css_raw_bytes += bytes.byteLength;
      metrics.initial_css_gzip_bytes += gzipBytes;
      metrics.stylesheet_contents.push({
        href,
        text: bytes.toString("utf8"),
      });
    }
  }
  return metrics;
}

export function validateRouteBudget(metrics, budget) {
  const errors = [];
  const maxima = {
    initial_js_gzip_bytes: budget.max_initial_js_gzip_bytes,
    initial_css_gzip_bytes: budget.max_initial_css_gzip_bytes,
  };
  for (const [key, maximum] of Object.entries(maxima)) {
    if (!Number.isInteger(maximum) || maximum < 0) {
      errors.push(
        metrics.route + ": budget " + key + " must be a non-negative integer",
      );
      continue;
    }
    if (metrics[key] > maximum) {
      errors.push(
        metrics.route + ": " + key + " " + metrics[key] + " exceeds " + maximum,
      );
    }
  }

  for (const marker of budget.forbid_css_markers ?? []) {
    if (typeof marker !== "string" || marker.length === 0) {
      errors.push(metrics.route + ": CSS marker must be a non-empty string");
      continue;
    }
    for (const stylesheet of metrics.stylesheet_contents) {
      if (stylesheet.text.includes(marker)) {
        errors.push(
          metrics.route +
            ": forbidden CSS marker " +
            JSON.stringify(marker) +
            " found in " +
            stylesheet.href,
        );
      }
    }
  }

  for (const marker of budget.require_css_markers ?? []) {
    if (typeof marker !== "string" || marker.length === 0) {
      errors.push(metrics.route + ": CSS marker must be a non-empty string");
      continue;
    }
    const found = metrics.stylesheet_contents.some((stylesheet) =>
      stylesheet.text.includes(marker),
    );
    if (!found) {
      errors.push(
        metrics.route +
          ": required CSS marker " +
          JSON.stringify(marker) +
          " was not found",
      );
    }
  }
  return errors;
}

export function runBudgetCheck({
  buildDir = defaultBuildDir,
  budgetPath = defaultBudgetPath,
  reportOnly = false,
} = {}) {
  const parsed = JSON.parse(readFileSync(budgetPath, "utf8"));
  if (
    parsed?.schema_version !== 1 ||
    !parsed.routes ||
    typeof parsed.routes !== "object"
  ) {
    throw new Error(
      "Route performance budget must use schema_version 1 and define routes",
    );
  }

  const reports = [];
  const errors = [];
  for (const [routeFile, budget] of Object.entries(parsed.routes)) {
    const metrics = measureRoute({ buildDir, routeFile });
    reports.push({
      route: routeFile,
      initial_js_raw_bytes: metrics.initial_js_raw_bytes,
      initial_js_gzip_bytes: metrics.initial_js_gzip_bytes,
      initial_css_raw_bytes: metrics.initial_css_raw_bytes,
      initial_css_gzip_bytes: metrics.initial_css_gzip_bytes,
      assets: metrics.assets,
    });
    if (!reportOnly) errors.push(...validateRouteBudget(metrics, budget));
  }

  for (const report of reports) {
    console.log(
      report.route +
        ": JS " +
        report.initial_js_gzip_bytes +
        " B gzip / CSS " +
        report.initial_css_gzip_bytes +
        " B gzip",
    );
  }
  if (errors.length > 0) throw new Error(errors.join("\n"));
  return reports;
}

const isMain =
  process.argv[1] &&
  import.meta.url === pathToFileURL(resolve(process.argv[1])).href;
if (isMain) {
  runBudgetCheck({ reportOnly: process.argv.includes("--report-only") });
}
