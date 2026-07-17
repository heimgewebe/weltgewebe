import { lstatSync, readFileSync, readdirSync, realpathSync } from "node:fs";
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
import {
  assertSafeRelativeDirectory,
  parsePerformanceBudget,
  routeIdToHtmlFile,
} from "./route-performance-budget-config.mjs";
import { collectInitialAssetReferences } from "./route-performance-budget-html.mjs";

const modulePath = fileURLToPath(import.meta.url);
const scriptDir = dirname(modulePath);
export const webRoot = resolve(scriptDir, "..");
const defaultBudgetPath = resolve(webRoot, "route-performance-budget.json");

function isInside(root, target) {
  const pathFromRoot = relative(root, target);
  return (
    pathFromRoot === "" ||
    (!pathFromRoot.startsWith(".." + sep) &&
      pathFromRoot !== ".." &&
      !isAbsolute(pathFromRoot))
  );
}

function resolveWithinBuild(buildDir, reference, baseDirectory = buildDir) {
  let decoded;
  try {
    decoded = decodeURIComponent(reference);
  } catch {
    throw new Error(
      "Route asset reference is not valid URI encoding: " + reference,
    );
  }
  const target = decoded.startsWith("/")
    ? resolve(buildDir, decoded.slice(1))
    : resolve(baseDirectory, decoded.replace(/^\.\//, ""));
  if (!isInside(buildDir, target)) {
    throw new Error("Route asset escapes build directory: " + reference);
  }
  return target;
}

function regularFileExists(path) {
  try {
    return lstatSync(path).isFile();
  } catch {
    return false;
  }
}

function assertResolvedInside(root, path, label) {
  let resolvedRoot;
  let resolvedPath;
  try {
    resolvedRoot = realpathSync(root);
    resolvedPath = realpathSync(path);
  } catch (error) {
    throw new Error(
      label +
        " cannot be resolved: " +
        path +
        " (" +
        (error instanceof Error ? error.message : String(error)) +
        ")",
    );
  }
  if (!isInside(resolvedRoot, resolvedPath)) {
    throw new Error(label + " resolves outside build directory: " + path);
  }
}

function readRegularFile(path, label, root = dirname(path)) {
  let metadata;
  try {
    metadata = lstatSync(path);
  } catch (error) {
    throw new Error(
      label +
        " does not exist: " +
        path +
        " (" +
        (error instanceof Error ? error.message : String(error)) +
        ")",
    );
  }
  if (!metadata.isFile()) {
    throw new Error(label + " is not a regular file: " + path);
  }
  assertResolvedInside(root, path, label);
  return readFileSync(path);
}

export function resolveBuildDirectory({
  root = webRoot,
  routeFiles,
  candidates,
}) {
  if (!Array.isArray(routeFiles) || routeFiles.length === 0) {
    throw new Error("Build selection requires at least one route file");
  }
  if (!Array.isArray(candidates) || candidates.length === 0) {
    throw new Error("Build selection requires at least one output directory");
  }

  const absoluteCandidates = candidates.map((candidate) => {
    assertSafeRelativeDirectory(candidate, "output directory");
    return resolveWithinBuild(root, candidate);
  });
  const complete = absoluteCandidates.filter((candidate) => {
    try {
      if (!lstatSync(candidate).isDirectory()) return false;
      assertResolvedInside(root, candidate, "Build output directory");
    } catch {
      return false;
    }
    return routeFiles.every((routeFile) =>
      regularFileExists(resolveWithinBuild(candidate, routeFile)),
    );
  });
  if (complete.length === 1) return complete[0];
  if (complete.length > 1) {
    throw new Error(
      "Multiple complete route build directories found; remove stale output or pass --build-dir explicitly: " +
        complete.join(", "),
    );
  }
  throw new Error(
    "No complete route build directory found for " +
      routeFiles.join(", ") +
      ". Checked: " +
      absoluteCandidates.join(", "),
  );
}

export function measureRoute({ buildDir, routeId, routeFile }) {
  const routePath = resolveWithinBuild(buildDir, routeFile);
  const html = readRegularFile(routePath, "Route HTML", buildDir).toString(
    "utf8",
  );
  const metrics = {
    route: routeId,
    route_file: routeFile,
    initial_js_asset_count: 0,
    initial_js_raw_bytes: 0,
    initial_js_gzip_bytes: 0,
    initial_css_asset_count: 0,
    initial_css_raw_bytes: 0,
    initial_css_gzip_bytes: 0,
    stylesheet_contents: [],
    assets: [],
  };

  for (const href of collectInitialAssetReferences(html)) {
    const assetPath = resolveWithinBuild(buildDir, href, dirname(routePath));
    const bytes = readRegularFile(
      assetPath,
      "Initial route asset " + href,
      buildDir,
    );
    const extension = extname(assetPath).toLowerCase();
    const kind =
      extension === ".js" ? "js" : extension === ".css" ? "css" : "other";
    const gzipBytes = gzipSync(bytes, { level: 9, mtime: 0 }).byteLength;
    metrics.assets.push({
      href,
      kind,
      raw_bytes: bytes.byteLength,
      gzip_bytes: gzipBytes,
    });
    if (kind === "js") {
      metrics.initial_js_asset_count += 1;
      metrics.initial_js_raw_bytes += bytes.byteLength;
      metrics.initial_js_gzip_bytes += gzipBytes;
    } else if (kind === "css") {
      metrics.initial_css_asset_count += 1;
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

function assetContext(metrics, kind) {
  return metrics.assets
    .filter((asset) => asset.kind === kind)
    .map((asset) => asset.href + "=" + asset.gzip_bytes + "B")
    .join(", ");
}

export function validateRouteBudget(metrics, budget) {
  const errors = [];
  const minima = {
    initial_js_asset_count: budget.min_initial_js_assets,
    initial_css_asset_count: budget.min_initial_css_assets,
  };
  for (const [key, minimum] of Object.entries(minima)) {
    if (metrics[key] < minimum) {
      errors.push(
        metrics.route +
          ": " +
          key +
          " " +
          metrics[key] +
          " is below " +
          minimum,
      );
    }
  }

  const maxima = {
    initial_js_gzip_bytes: [budget.max_initial_js_gzip_bytes, "js"],
    initial_css_gzip_bytes: [budget.max_initial_css_gzip_bytes, "css"],
  };
  for (const [key, [maximum, kind]] of Object.entries(maxima)) {
    if (metrics[key] > maximum) {
      errors.push(
        metrics.route +
          ": " +
          key +
          " " +
          metrics[key] +
          " exceeds " +
          maximum +
          "; assets: " +
          assetContext(metrics, kind),
      );
    }
  }

  for (const marker of budget.forbid_css_markers) {
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

  for (const marker of budget.require_css_markers) {
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

export function validateEmittedAssetBudgets({ buildDir, budgets }) {
  const errors = [];
  for (const [label, budget] of Object.entries(budgets)) {
    const assetDirectory = resolveWithinBuild(buildDir, budget.directory);
    let filenames;
    try {
      if (!lstatSync(assetDirectory).isDirectory()) {
        throw new Error("not a regular directory");
      }
      assertResolvedInside(
        buildDir,
        assetDirectory,
        label + " asset directory",
      );
      filenames = readdirSync(assetDirectory);
    } catch (error) {
      errors.push(
        label +
          ": cannot read emitted asset directory " +
          assetDirectory +
          ": " +
          (error instanceof Error ? error.message : String(error)),
      );
      continue;
    }

    const candidates = filenames.filter((filename) =>
      filename.startsWith(budget.filename_prefix),
    );
    for (const extension of budget.forbid_extensions) {
      for (const filename of candidates.filter((name) =>
        name.endsWith(extension),
      )) {
        errors.push(label + ": forbidden emitted asset " + filename);
      }
    }

    const matches = candidates.filter((filename) =>
      filename.endsWith(budget.required_extension),
    );
    if (matches.length !== 1) {
      errors.push(
        label +
          ": expected exactly one emitted " +
          budget.required_extension +
          " asset, found " +
          matches.length,
      );
      continue;
    }

    const assetPath = resolveWithinBuild(assetDirectory, matches[0]);
    let metadata;
    try {
      metadata = lstatSync(assetPath);
    } catch (error) {
      errors.push(
        label +
          ": cannot stat emitted asset " +
          matches[0] +
          ": " +
          (error instanceof Error ? error.message : String(error)),
      );
      continue;
    }
    if (!metadata.isFile()) {
      errors.push(
        label + ": emitted asset is not a regular file: " + matches[0],
      );
      continue;
    }
    if (metadata.size > budget.max_bytes) {
      errors.push(
        label +
          ": emitted asset " +
          matches[0] +
          " is " +
          metadata.size +
          " bytes, exceeds " +
          budget.max_bytes,
      );
    }
  }
  return errors;
}

export function runBudgetCheck({
  buildDir,
  budgetPath = defaultBudgetPath,
  reportOnly = false,
} = {}) {
  const parsed = parsePerformanceBudget(
    readRegularFile(
      budgetPath,
      "Route performance budget",
      dirname(budgetPath),
    ).toString("utf8"),
  );
  const routeEntries = Object.entries(parsed.routes).map(
    ([routeId, budget]) => ({
      routeId,
      routeFile: routeIdToHtmlFile(routeId),
      budget,
    }),
  );
  const resolvedBuildDir = buildDir
    ? resolve(buildDir)
    : resolveBuildDirectory({
        root: webRoot,
        routeFiles: routeEntries.map((entry) => entry.routeFile),
        candidates: parsed.output_directories,
      });
  const reports = [];
  const errors = [];
  for (const { routeId, routeFile, budget } of routeEntries) {
    const metrics = measureRoute({
      buildDir: resolvedBuildDir,
      routeId,
      routeFile,
    });
    reports.push({
      route: routeId,
      route_file: routeFile,
      initial_js_asset_count: metrics.initial_js_asset_count,
      initial_js_raw_bytes: metrics.initial_js_raw_bytes,
      initial_js_gzip_bytes: metrics.initial_js_gzip_bytes,
      initial_css_asset_count: metrics.initial_css_asset_count,
      initial_css_raw_bytes: metrics.initial_css_raw_bytes,
      initial_css_gzip_bytes: metrics.initial_css_gzip_bytes,
      assets: metrics.assets,
    });
    if (!reportOnly) errors.push(...validateRouteBudget(metrics, budget));
  }
  if (!reportOnly) {
    errors.push(
      ...validateEmittedAssetBudgets({
        buildDir: resolvedBuildDir,
        budgets: parsed.emitted_assets,
      }),
    );
  }
  if (errors.length > 0) throw new Error(errors.join("\n"));
  return {
    schema_version: 1,
    build_directory: resolvedBuildDir,
    measurement: parsed.measurement,
    report_only: reportOnly,
    routes: reports,
  };
}

export function formatTextReport(result) {
  const lines = ["build directory: " + result.build_directory];
  for (const report of result.routes) {
    lines.push(
      report.route +
        " (" +
        report.route_file +
        "): JS " +
        report.initial_js_gzip_bytes +
        " B gzip (" +
        report.initial_js_asset_count +
        " assets) / CSS " +
        report.initial_css_gzip_bytes +
        " B gzip (" +
        report.initial_css_asset_count +
        " assets)",
    );
  }
  return lines.join("\n");
}
