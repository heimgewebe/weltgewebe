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
import { readBuildArtifactEvidence } from "./build-artifact-evidence.mjs";
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
const DECLARED_REVISION_VARIABLES = [
  "GIT_COMMIT_SHA",
  "GITHUB_SHA",
  "VERCEL_GIT_COMMIT_SHA",
  "VITE_VERCEL_GIT_COMMIT_SHA",
  "PUBLIC_VERCEL_GIT_COMMIT_SHA",
  "CF_PAGES_COMMIT_SHA",
];
const PLATFORM_REVISION_FLAGS = new Map([
  ["VERCEL_GIT_COMMIT_SHA", "VERCEL"],
  ["VITE_VERCEL_GIT_COMMIT_SHA", "VERCEL"],
  ["PUBLIC_VERCEL_GIT_COMMIT_SHA", "VERCEL"],
  ["CF_PAGES_COMMIT_SHA", "CF_PAGES"],
]);

export function readBuildRevisionEvidence(buildDir) {
  return readBuildArtifactEvidence(buildDir).revision;
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
  artifactEvidence,
  artifactRevision,
  artifactTreeVerified,
} = {}) {
  const declared = [];
  const platformDeclared = [];
  const invalidVariables = [];
  for (const name of DECLARED_REVISION_VARIABLES) {
    const raw = env[name];
    if (typeof raw !== "string" || raw.trim() === "") continue;
    const value = raw.trim().toLowerCase();
    const providerFlag = PLATFORM_REVISION_FLAGS.get(name);
    if (providerFlag && env[providerFlag] !== "1") {
      invalidVariables.push(name);
      continue;
    }
    if (!SOURCE_REVISION_PATTERN.test(value)) {
      invalidVariables.push(name);
      continue;
    }
    declared.push(value);
    if (providerFlag) {
      platformDeclared.push(value);
    }
  }

  const suppliedArtifactEvidence =
    artifactEvidence &&
    typeof artifactEvidence === "object" &&
    !Array.isArray(artifactEvidence)
      ? artifactEvidence
      : {
          revision: artifactRevision,
          verified: artifactTreeVerified === true,
          status:
            artifactTreeVerified === true
              ? "verified"
              : "artifact_unverifiable",
        };
  const observedArtifact =
    typeof suppliedArtifactEvidence.revision === "string" &&
    SOURCE_REVISION_PATTERN.test(
      suppliedArtifactEvidence.revision.trim().toLowerCase(),
    )
      ? suppliedArtifactEvidence.revision.trim().toLowerCase()
      : null;
  const artifactStatus =
    typeof suppliedArtifactEvidence.status === "string"
      ? suppliedArtifactEvidence.status
      : "artifact_unverifiable";

  const distinct = [...new Set(declared)];
  const distinctPlatform = [...new Set(platformDeclared)];
  const platformRevision =
    distinctPlatform.length === 1 ? distinctPlatform[0] : null;
  if (invalidVariables.length > 0) {
    return {
      sourceRevision: distinct.length === 1 ? distinct[0] : null,
      checkoutRevision: null,
      verified: false,
      status: "invalid",
    };
  }
  if (distinct.length > 1) {
    return {
      sourceRevision: null,
      checkoutRevision: null,
      verified: false,
      status: "conflicting",
    };
  }
  const sourceRevision = distinct.length === 1 ? distinct[0] : observedArtifact;

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

  if (!sourceRevision) {
    return {
      sourceRevision: null,
      checkoutRevision: observedCheckout,
      verified: false,
      status: "missing",
    };
  }
  if (!observedCheckout) {
    if (!platformRevision || platformRevision !== sourceRevision) {
      return {
        sourceRevision,
        checkoutRevision: null,
        verified: false,
        status: "unverifiable",
      };
    }
    if (!observedArtifact) {
      return {
        sourceRevision,
        checkoutRevision: null,
        verified: false,
        status: artifactStatus,
      };
    }
    if (observedArtifact !== sourceRevision) {
      return {
        sourceRevision,
        checkoutRevision: null,
        verified: false,
        status: "artifact_mismatch",
      };
    }
    if (suppliedArtifactEvidence.verified !== true) {
      return {
        sourceRevision,
        checkoutRevision: null,
        verified: false,
        status: artifactStatus,
      };
    }
    return {
      sourceRevision,
      checkoutRevision: null,
      verified: false,
      status: "platform_artifact_consistent_unattested",
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
      status: artifactStatus,
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
  if (suppliedArtifactEvidence.verified !== true) {
    return {
      sourceRevision,
      checkoutRevision: observedCheckout,
      verified: false,
      status: artifactStatus,
    };
  }
  return {
    sourceRevision,
    checkoutRevision: observedCheckout,
    verified: false,
    status: "artifact_consistent_unattested",
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

export function resolveConfiguredBuildDirectory({
  root = webRoot,
  budgetPath = defaultBudgetPath,
  contractRoot = performanceRepositoryRoot,
} = {}) {
  const contract = loadPerformanceContract({
    contractPath: budgetPath,
    root: contractRoot,
    enforceLegacyAbsence: true,
  });
  const budget = contract.measurements.web_build.budget;
  return resolveBuildDirectory({
    root,
    routeFiles: Object.keys(budget.routes).map(routeIdToHtmlFile),
    candidates: budget.output_directories,
  });
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
      path: relative(buildDir, assetPath).split(sep).join("/"),
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

function summarizeAssets(assets) {
  const ordered = [...assets].sort((left, right) =>
    left.path < right.path ? -1 : left.path > right.path ? 1 : 0,
  );
  return {
    asset_count: ordered.length,
    raw_bytes: ordered.reduce((sum, asset) => sum + asset.raw_bytes, 0),
    gzip_bytes: ordered.reduce((sum, asset) => sum + asset.gzip_bytes, 0),
    assets: ordered.map(({ href, path, kind, raw_bytes, gzip_bytes }) => ({
      href,
      path,
      kind,
      raw_bytes,
      gzip_bytes,
    })),
  };
}

export function collectSharedInitialAssets(routeMetrics) {
  const sharedForKind = (kind) => {
    if (routeMetrics.length === 0) return summarizeAssets([]);
    const [first, ...rest] = routeMetrics;
    const shared = first.assets.filter(
      (asset) =>
        asset.kind === kind &&
        rest.every((metrics) =>
          metrics.assets.some(
            (candidate) =>
              candidate.kind === kind &&
              candidate.path === asset.path &&
              candidate.raw_bytes === asset.raw_bytes &&
              candidate.gzip_bytes === asset.gzip_bytes,
          ),
        ),
    );
    return summarizeAssets(shared);
  };
  return { js: sharedForKind("js"), css: sharedForKind("css") };
}

export function evaluateRouteHeadroom(metrics, budget, warningPolicy) {
  const observed = metrics.initial_js_gzip_bytes;
  const maximum = budget.max_initial_js_gzip_bytes;
  const remainingBytes = maximum - observed;
  if (remainingBytes < 0) return [];
  const remainingRatio = maximum === 0 ? 1 : remainingBytes / maximum;
  if (
    remainingBytes >= warningPolicy.minimum_remaining_bytes &&
    remainingRatio >= warningPolicy.minimum_remaining_ratio
  ) {
    return [];
  }
  return [
    {
      route: metrics.route,
      kind: "js",
      observed_gzip_bytes: observed,
      maximum_gzip_bytes: maximum,
      remaining_bytes: remainingBytes,
      remaining_ratio: remainingRatio,
      minimum_remaining_bytes: warningPolicy.minimum_remaining_bytes,
      minimum_remaining_ratio: warningPolicy.minimum_remaining_ratio,
    },
  ];
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
  requireRevisionEvidence = true,
  revisionEnvironment = process.env,
  checkoutRevision,
  checkoutClean,
  buildEvidence,
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
    : resolveConfiguredBuildDirectory({
        root: webRoot,
        budgetPath,
        contractRoot,
      });
  const measuredRoutes = routeEntries.map(({ routeId, routeFile, budget }) => ({
    budget,
    metrics: measureRoute({
      buildDir: resolvedBuildDir,
      routeId,
      routeFile,
    }),
  }));
  const sharedInitialAssets = collectSharedInitialAssets(
    measuredRoutes.map(({ metrics }) => metrics),
  );
  const sharedPaths = {
    js: new Set(sharedInitialAssets.js.assets.map((asset) => asset.path)),
    css: new Set(sharedInitialAssets.css.assets.map((asset) => asset.path)),
  };
  const reports = [];
  const warnings = [];
  const errors = [];
  for (const { budget, metrics } of measuredRoutes) {
    const routeWarnings = evaluateRouteHeadroom(
      metrics,
      budget,
      parsed.initial_js_headroom_warning,
    );
    warnings.push(...routeWarnings);
    const routeSpecificJs = summarizeAssets(
      metrics.assets.filter(
        (asset) => asset.kind === "js" && !sharedPaths.js.has(asset.path),
      ),
    );
    const routeSpecificCss = summarizeAssets(
      metrics.assets.filter(
        (asset) => asset.kind === "css" && !sharedPaths.css.has(asset.path),
      ),
    );
    reports.push({
      route: metrics.route,
      route_file: metrics.route_file,
      initial_js_asset_count: metrics.initial_js_asset_count,
      initial_js_raw_bytes: metrics.initial_js_raw_bytes,
      initial_js_gzip_bytes: metrics.initial_js_gzip_bytes,
      initial_js_budget_bytes: budget.max_initial_js_gzip_bytes,
      initial_js_headroom_bytes:
        budget.max_initial_js_gzip_bytes - metrics.initial_js_gzip_bytes,
      initial_js_headroom_ratio:
        budget.max_initial_js_gzip_bytes === 0
          ? 1
          : (budget.max_initial_js_gzip_bytes - metrics.initial_js_gzip_bytes) /
            budget.max_initial_js_gzip_bytes,
      route_specific_js: routeSpecificJs,
      initial_css_asset_count: metrics.initial_css_asset_count,
      initial_css_raw_bytes: metrics.initial_css_raw_bytes,
      initial_css_gzip_bytes: metrics.initial_css_gzip_bytes,
      initial_css_budget_bytes: budget.max_initial_css_gzip_bytes,
      initial_css_headroom_bytes:
        budget.max_initial_css_gzip_bytes - metrics.initial_css_gzip_bytes,
      initial_css_headroom_ratio:
        budget.max_initial_css_gzip_bytes === 0
          ? 1
          : (budget.max_initial_css_gzip_bytes -
              metrics.initial_css_gzip_bytes) /
            budget.max_initial_css_gzip_bytes,
      route_specific_css: routeSpecificCss,
      warnings: routeWarnings,
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
  const artifactEvidence =
    buildEvidence === undefined
      ? readBuildArtifactEvidence(resolvedBuildDir)
      : buildEvidence;
  const revisionEvidence = resolveSourceRevisionEvidence({
    env: revisionEnvironment,
    root: contractRoot,
    checkoutRevision,
    checkoutClean,
    artifactEvidence,
  });
  const revisionClaimEnforced = !reportOnly && requireRevisionEvidence;
  const reportedRevisionEvidence = revisionClaimEnforced
    ? revisionEvidence
    : { ...revisionEvidence, verified: false, status: "not_enforced" };
  const limitations = [...contract.authority.does_not_establish];
  if (!revisionClaimEnforced || !revisionEvidence.verified) {
    limitations.push("revision-bound performance evidence");
  }
  if (revisionClaimEnforced && !revisionEvidence.verified) {
    throw new Error(
      "Revision-bound performance evidence is required: " +
        revisionEvidence.status,
    );
  }
  return {
    schema_version: 3,
    contract_id: contract.contract_id,
    contract_status: contract.measurements.web_build.status,
    source_revision: revisionEvidence.sourceRevision,
    source_revision_verified: reportedRevisionEvidence.verified,
    revision_evidence_status: reportedRevisionEvidence.status,
    observed_revision_evidence_status: revisionEvidence.status,
    artifact_integrity_verified: artifactEvidence.verified === true,
    artifact_integrity_status:
      artifactEvidence.status ?? "artifact_unverifiable",
    artifact_provenance_verified: artifactEvidence.provenanceVerified === true,
    artifact_provenance_status:
      artifactEvidence.provenanceStatus ?? "unattested",
    artifact_tree_sha256: artifactEvidence.treeSha256 ?? null,
    artifact_file_count: artifactEvidence.fileCount ?? null,
    build_directory: resolvedBuildDir,
    measurement: parsed.measurement,
    initial_js_headroom_warning: parsed.initial_js_headroom_warning,
    shared_initial_assets: sharedInitialAssets,
    warnings,
    report_only: reportOnly,
    revision_evidence_required: requireRevisionEvidence,
    does_not_establish: [...new Set(limitations)],
    routes: reports,
  };
}

export function formatTextReport(result) {
  const sourceRevision = result.source_revision ?? "not available";
  const revisionStatus = result.source_revision_verified
    ? "verified by trusted provenance evidence"
    : result.revision_evidence_status;
  const lines = [
    "build directory: " + result.build_directory,
    "source revision: " + sourceRevision + " (" + revisionStatus + ")",
  ];
  for (const limitation of result.does_not_establish) {
    lines.push("does not establish: " + limitation);
  }
  if (result.shared_initial_assets) {
    lines.push(
      "shared initial shell: JS " +
        result.shared_initial_assets.js.gzip_bytes +
        " B gzip (" +
        result.shared_initial_assets.js.asset_count +
        " assets) / CSS " +
        result.shared_initial_assets.css.gzip_bytes +
        " B gzip (" +
        result.shared_initial_assets.css.asset_count +
        " assets)",
    );
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
        " assets) / headroom JS " +
        report.initial_js_headroom_bytes +
        " B / route delta JS " +
        report.route_specific_js.gzip_bytes +
        " B gzip",
    );
  }
  for (const warning of result.warnings ?? []) {
    lines.push(
      "warning: " +
        warning.route +
        " " +
        warning.kind.toUpperCase() +
        " headroom " +
        warning.remaining_bytes +
        " B (" +
        (warning.remaining_ratio * 100).toFixed(2) +
        "%)",
    );
  }
  return lines.join("\n");
}
