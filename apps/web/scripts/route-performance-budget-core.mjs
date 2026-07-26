import { spawnSync } from "node:child_process";
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
  routeIdToHtmlFile,
} from "./route-performance-budget-config.mjs";
import {
  loadPerformanceContract,
  repositoryRoot as performanceRepositoryRoot,
} from "./performance-contract.mjs";
import { collectInitialAssetReferences } from "./route-performance-budget-html.mjs";

const modulePath = fileURLToPath(import.meta.url);
const scriptDir = dirname(modulePath);
export const webRoot = resolve(scriptDir, "..");
const defaultBudgetPath = resolve(
  webRoot,
  "../../policies/performance.v1.json",
);
const SOURCE_REVISION_PATTERN = /^[0-9a-f]{40}$/;

export function readBuildRevisionEvidence(buildDir) {
  try {
    const payload = JSON.parse(
      readRegularFile(
        resolve(buildDir, "_app/version.json"),
        "Build revision evidence",
        buildDir,
      ).toString("utf8"),
    );
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
      return null;
    }
    const revision =
      typeof payload.commit === "string"
        ? payload.commit.trim().toLowerCase()
        : "";
    return SOURCE_REVISION_PATTERN.test(revision) ? revision : null;
  } catch {
    return null;
  }
}

function readCheckoutState(root) {
  const options = {
    encoding: "utf8",
    timeout: 5000,
    windowsHide: true,
  };
  const revisionResult = spawnSync(
    "git",
    ["-C", root, "rev-parse", "--verify", "HEAD"],
    options,
  );
  if (revisionResult.status !== 0) {
    return { revision: null, clean: null };
  }
  const revision = revisionResult.stdout.trim().toLowerCase();
  if (!SOURCE_REVISION_PATTERN.test(revision)) {
    return { revision: null, clean: null };
  }
  const statusResult = spawnSync(
    "git",
    ["-C", root, "status", "--porcelain=v1", "--untracked-files=all"],
    options,
  );
  return {
    revision,
    clean: statusResult.status === 0 ? statusResult.stdout === "" : null,
  };
}

export function resolveSourceRevisionEvidence({
  env = process.env,
  root = performanceRepositoryRoot,
  checkoutRevision,
  checkoutClean,
  artifactRevision,
} = {}) {
  const declared = [];
  const invalidVariables = [];
  for (const name of ["GIT_COMMIT_SHA", "GITHUB_SHA"]) {
    const raw = env[name];
    if (typeof raw !== "string" || raw.trim() === "") continue;
    const value = raw.trim().toLowerCase();
    if (!SOURCE_REVISION_PATTERN.test(value)) {
      invalidVariables.push(name);
      continue;
    }
    declared.push(value);
  }

  const distinct = [...new Set(declared)];
  const sourceRevision = distinct.length === 1 ? distinct[0] : null;
  const observedState =
    checkoutRevision === undefined || checkoutClean === undefined
      ? readCheckoutState(root)
      : null;
  const observedCheckout =
    checkoutRevision === undefined
      ? observedState.revision
      : typeof checkoutRevision === "string" &&
          SOURCE_REVISION_PATTERN.test(checkoutRevision.trim().toLowerCase())
        ? checkoutRevision.trim().toLowerCase()
        : null;
  const observedClean =
    checkoutClean === undefined
      ? observedState.clean
      : typeof checkoutClean === "boolean"
        ? checkoutClean
        : null;
  const artifactWasProvided = artifactRevision !== undefined;
  const observedArtifact =
    typeof artifactRevision === "string" &&
    SOURCE_REVISION_PATTERN.test(artifactRevision.trim().toLowerCase())
      ? artifactRevision.trim().toLowerCase()
      : null;

  if (invalidVariables.length > 0) {
    return {
      sourceRevision,
      checkoutRevision: observedCheckout,
      verified: false,
      status: "invalid",
    };
  }
  if (distinct.length > 1) {
    return {
      sourceRevision: null,
      checkoutRevision: observedCheckout,
      verified: false,
      status: "conflicting",
    };
  }
  if (!sourceRevision) {
    return {
      sourceRevision: null,
      checkoutRevision: observedCheckout,
      verified: false,
      status: "missing",
    };
  }
  if (!observedCheckout) {
    return {
      sourceRevision,
      checkoutRevision: null,
      verified: false,
      status: "unverifiable",
    };
  }
  if (sourceRevision !== observedCheckout) {
    return {
      sourceRevision,
      checkoutRevision: observedCheckout,
      verified: false,
      status: "mismatch",
    };
  }
  if (observedClean !== true) {
    return {
      sourceRevision,
      checkoutRevision: observedCheckout,
      verified: false,
      status: observedClean === false ? "dirty" : "unverifiable",
    };
  }
  if (!observedArtifact) {
    return {
      sourceRevision,
      checkoutRevision: observedCheckout,
      verified: false,
      status:
        artifactWasProvided && artifactRevision !== null
          ? "artifact_invalid"
          : "artifact_unverifiable",
    };
  }
  if (observedArtifact !== sourceRevision) {
    return {
      sourceRevision,
      checkoutRevision: observedCheckout,
      verified: false,
      status: "artifact_mismatch",
    };
  }
  return {
    sourceRevision,
    checkoutRevision: observedCheckout,
    verified: true,
    status: "verified",
  };
}

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
  contractRoot = performanceRepositoryRoot,
  reportOnly = false,
  revisionEnvironment = process.env,
  checkoutRevision,
  checkoutClean,
  buildRevision,
} = {}) {
  const contract = loadPerformanceContract({
    contractPath: budgetPath,
    root: contractRoot,
    enforceLegacyAbsence: true,
  });
  const parsed = contract.measurements.web_build.budget;
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
  const revisionEvidence = resolveSourceRevisionEvidence({
    env: revisionEnvironment,
    root: contractRoot,
    checkoutRevision,
    checkoutClean,
    artifactRevision:
      buildRevision === undefined
        ? readBuildRevisionEvidence(resolvedBuildDir)
        : buildRevision,
  });
  const limitations = [...contract.authority.does_not_establish];
  if (!revisionEvidence.verified) {
    limitations.push("revision-bound performance evidence");
  }
  return {
    schema_version: 2,
    contract_id: contract.contract_id,
    contract_status: contract.measurements.web_build.status,
    source_revision: revisionEvidence.sourceRevision,
    source_revision_verified: revisionEvidence.verified,
    revision_evidence_status: revisionEvidence.status,
    build_directory: resolvedBuildDir,
    measurement: parsed.measurement,
    report_only: reportOnly,
    does_not_establish: [...new Set(limitations)],
    routes: reports,
  };
}

export function formatTextReport(result) {
  const sourceRevision = result.source_revision ?? "not available";
  const revisionStatus = result.source_revision_verified
    ? "verified against checkout"
    : result.revision_evidence_status;
  const lines = [
    "build directory: " + result.build_directory,
    "source revision: " + sourceRevision + " (" + revisionStatus + ")",
  ];
  for (const limitation of result.does_not_establish) {
    lines.push("does not establish: " + limitation);
  }
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
