import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import {
  mkdtempSync,
  mkdirSync,
  readFileSync,
  rmSync,
  symlinkSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import test from "node:test";
import { parseCliArguments } from "./assert-route-performance-budget.mjs";
import {
  computeBuildArtifactTree,
  readBuildArtifactEvidence,
} from "./build-artifact-evidence.mjs";
import { defaultPerformanceContractPath } from "./performance-contract.mjs";
import {
  parsePerformanceBudget,
  routeIdToHtmlFile,
  validatePerformanceBudget,
} from "./route-performance-budget-config.mjs";
import {
  formatTextReport,
  measureRoute,
  readBuildRevisionEvidence,
  resolveBuildDirectory,
  resolveSourceRevisionEvidence,
  runBudgetCheck,
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
    <link rel=stylesheet href=./_app/self-closing.css/>
    <link href='./_app/a.js' rel='modulepreload'>
    <link rel="stylesheet" href="./_app/a>b.css?version=1">
    <link rel="icon" href="/favicon.svg">
  `;
  assert.deepEqual(collectInitialAssetReferences(html), [
    "./scripture.css",
    "./_app/a.js",
    "./_app/self-closing.css",
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

test("reports artifact consistency without claiming source provenance", () => {
  const revision = "a".repeat(40);
  const otherRevision = "b".repeat(40);
  const verifiedArtifact = (value = revision) => ({
    revision: value,
    verified: true,
    status: "verified",
    treeSha256: "c".repeat(64),
    fileCount: 3,
  });

  assert.deepEqual(
    resolveSourceRevisionEvidence({
      env: { GIT_COMMIT_SHA: "", GITHUB_SHA: revision },
      checkoutRevision: revision,
      checkoutClean: true,
      artifactEvidence: verifiedArtifact(),
    }),
    {
      sourceRevision: revision,
      checkoutRevision: revision,
      verified: false,
      status: "artifact_consistent_unattested",
    },
  );
  assert.equal(
    resolveSourceRevisionEvidence({
      env: {},
      checkoutRevision: revision,
      checkoutClean: true,
      artifactEvidence: verifiedArtifact(),
    }).status,
    "artifact_consistent_unattested",
  );
  assert.equal(
    resolveSourceRevisionEvidence({
      env: {},
      checkoutRevision: revision,
      checkoutClean: true,
    }).status,
    "missing",
  );
  assert.equal(
    resolveSourceRevisionEvidence({
      env: { GIT_COMMIT_SHA: "unknown", GITHUB_SHA: revision },
      checkoutRevision: revision,
      artifactEvidence: verifiedArtifact(),
    }).status,
    "invalid",
  );
  assert.equal(
    resolveSourceRevisionEvidence({
      env: { GIT_COMMIT_SHA: revision, GITHUB_SHA: otherRevision },
      checkoutRevision: revision,
      artifactEvidence: verifiedArtifact(),
    }).status,
    "conflicting",
  );
  assert.equal(
    resolveSourceRevisionEvidence({
      env: { GIT_COMMIT_SHA: revision },
      checkoutRevision: otherRevision,
      checkoutClean: true,
      artifactEvidence: verifiedArtifact(),
    }).status,
    "mismatch",
  );
  assert.equal(
    resolveSourceRevisionEvidence({
      env: { GIT_COMMIT_SHA: revision },
      checkoutRevision: null,
      checkoutClean: null,
      artifactEvidence: verifiedArtifact(),
    }).status,
    "unverifiable",
  );
  assert.equal(
    resolveSourceRevisionEvidence({
      env: { GIT_COMMIT_SHA: revision },
      checkoutRevision: revision,
      checkoutClean: false,
      artifactEvidence: verifiedArtifact(),
    }).status,
    "dirty",
  );
  assert.equal(
    resolveSourceRevisionEvidence({
      env: { GIT_COMMIT_SHA: revision },
      checkoutRevision: revision,
      checkoutClean: true,
      artifactEvidence: verifiedArtifact(otherRevision),
    }).status,
    "artifact_mismatch",
  );
  assert.equal(
    resolveSourceRevisionEvidence({
      env: { GIT_COMMIT_SHA: revision },
      checkoutRevision: revision,
      checkoutClean: true,
      artifactEvidence: {
        revision,
        verified: false,
        status: "artifact_tree_mismatch",
      },
    }).status,
    "artifact_tree_mismatch",
  );

  assert.equal(
    resolveSourceRevisionEvidence({
      env: { VERCEL_GIT_COMMIT_SHA: revision },
      checkoutRevision: null,
      checkoutClean: null,
      artifactEvidence: verifiedArtifact(),
    }).status,
    "invalid",
  );

  assert.deepEqual(
    resolveSourceRevisionEvidence({
      env: { VERCEL: "1", VERCEL_GIT_COMMIT_SHA: revision },
      checkoutRevision: null,
      checkoutClean: null,
      artifactEvidence: verifiedArtifact(),
    }),
    {
      sourceRevision: revision,
      checkoutRevision: null,
      verified: false,
      status: "platform_artifact_consistent_unattested",
    },
  );
  assert.equal(
    resolveSourceRevisionEvidence({
      env: { VERCEL: "1", VERCEL_GIT_COMMIT_SHA: revision },
      checkoutRevision: null,
      checkoutClean: null,
      artifactEvidence: verifiedArtifact(otherRevision),
    }).status,
    "artifact_mismatch",
  );
  assert.equal(
    resolveSourceRevisionEvidence({
      env: { VERCEL: "1", VERCEL_GIT_COMMIT_SHA: revision },
      checkoutRevision: null,
      checkoutClean: null,
      artifactEvidence: {
        revision,
        verified: false,
        status: "artifact_tree_mismatch",
      },
    }).status,
    "artifact_tree_mismatch",
  );
  assert.equal(
    resolveSourceRevisionEvidence({
      env: { VERCEL: "1", VERCEL_GIT_COMMIT_SHA: revision },
      checkoutRevision: revision,
      checkoutClean: false,
      artifactEvidence: verifiedArtifact(),
    }).status,
    "dirty",
  );
  assert.equal(
    resolveSourceRevisionEvidence({
      env: {
        GIT_COMMIT_SHA: revision,
        VERCEL: "1",
        VERCEL_GIT_COMMIT_SHA: otherRevision,
      },
      checkoutRevision: null,
      checkoutClean: null,
      artifactEvidence: verifiedArtifact(),
    }).status,
    "conflicting",
  );
});

test("refuses revision binding when the measured checkout is dirty", (t) => {
  const root = temporaryDirectory(t, "route-budget-git-");
  const input = join(root, "input.txt");
  writeFileSync(input, "committed\n");
  for (const arguments_ of [
    ["init", "--quiet"],
    ["config", "user.email", "ci@example.invalid"],
    ["config", "user.name", "CI"],
    ["add", "input.txt"],
    ["commit", "--quiet", "-m", "fixture"],
  ]) {
    const result = spawnSync("git", ["-C", root, ...arguments_], {
      encoding: "utf8",
    });
    assert.equal(result.status, 0, result.stderr);
  }
  const revision = spawnSync(
    "git",
    ["-C", root, "rev-parse", "--verify", "HEAD"],
    { encoding: "utf8" },
  ).stdout.trim();
  const artifactEvidence = {
    revision,
    verified: true,
    status: "verified",
  };
  assert.equal(
    resolveSourceRevisionEvidence({
      env: { GIT_COMMIT_SHA: revision },
      root,
      artifactEvidence,
    }).status,
    "artifact_consistent_unattested",
  );

  writeFileSync(input, "modified\n");
  assert.equal(
    resolveSourceRevisionEvidence({
      env: { GIT_COMMIT_SHA: revision },
      root,
      artifactEvidence,
    }).status,
    "dirty",
  );
});

test("binds embedded revision to the complete generated build tree", (t) => {
  const root = temporaryDirectory(t, "route-budget-version-");
  const appDirectory = join(root, "_app");
  mkdirSync(join(appDirectory, "immutable"), { recursive: true });
  const revision = "c".repeat(40);
  const versionPath = join(appDirectory, "version.json");
  const assetPath = join(appDirectory, "immutable/app.js");
  writeFileSync(join(root, "index.html"), "<main>Weltgewebe</main>\n");
  writeFileSync(assetPath, "export const build = 1;\n");
  writeFileSync(
    join(appDirectory, "compile-revision.json"),
    JSON.stringify({ schema_version: 1, compile_revision: revision }),
  );
  const tree = computeBuildArtifactTree(root);
  writeFileSync(
    versionPath,
    JSON.stringify({
      commit: revision,
      artifact_tree: {
        schema_version: tree.schemaVersion,
        sha256: tree.sha256,
        file_count: tree.fileCount,
        compile_revision: tree.compileRevision,
        provenance: "unattested",
      },
    }),
  );

  assert.match(tree.sha256, /^[0-9a-f]{64}$/);
  assert.equal(readBuildRevisionEvidence(root), revision);
  assert.deepEqual(readBuildArtifactEvidence(root), {
    revision,
    verified: true,
    status: "verified",
    treeSha256: tree.sha256,
    observedTreeSha256: tree.sha256,
    fileCount: tree.fileCount,
    observedFileCount: tree.fileCount,
    compileRevision: revision,
    observedCompileRevision: revision,
    provenanceVerified: false,
    provenanceStatus: "unattested",
  });

  writeFileSync(assetPath, "export const build = 2;\n");
  assert.equal(
    readBuildArtifactEvidence(root).status,
    "artifact_tree_mismatch",
  );

  writeFileSync(assetPath, "export const build = 1;\n");
  writeFileSync(
    join(appDirectory, "compile-revision.json"),
    JSON.stringify({
      schema_version: 1,
      compile_revision: "d".repeat(40),
    }),
  );
  assert.equal(
    readBuildArtifactEvidence(root).status,
    "artifact_compile_revision_mismatch",
  );
});

test("normal checks fail closed while report-only exposes revision gaps", (t) => {
  const root = temporaryDirectory(t, "route-budget-gate-");
  const buildDir = join(root, "build");
  mkdirSync(join(buildDir, "_app"), { recursive: true });
  writeFileSync(
    join(buildDir, "login.html"),
    '<link rel="modulepreload" href="./_app/app.js"><link rel="stylesheet" href="./_app/app.css">',
  );
  writeFileSync(join(buildDir, "_app/app.js"), "export const ok = true;\n");
  writeFileSync(join(buildDir, "_app/app.css"), ".login{display:block}\n");

  const contract = JSON.parse(readFileSync(defaultPerformanceContractPath));
  contract.measurements.web_build.budget = validBudget({
    output_directories: ["build"],
  });
  const budgetPath = join(root, "performance.v1.json");
  writeFileSync(budgetPath, JSON.stringify(contract));
  const revision = "d".repeat(40);
  const mismatchedEvidence = {
    revision,
    verified: false,
    status: "artifact_tree_mismatch",
  };
  const verifiedEvidence = {
    revision,
    verified: true,
    status: "verified",
    treeSha256: "e".repeat(64),
    fileCount: 3,
  };

  assert.throws(
    () =>
      runBudgetCheck({
        buildDir,
        budgetPath,
        contractRoot: root,
        revisionEnvironment: { GIT_COMMIT_SHA: revision },
        checkoutRevision: revision,
        checkoutClean: true,
        buildEvidence: mismatchedEvidence,
      }),
    /Revision-bound performance evidence is required: artifact_tree_mismatch/,
  );

  assert.throws(
    () =>
      runBudgetCheck({
        buildDir,
        budgetPath,
        contractRoot: root,
        revisionEnvironment: { GIT_COMMIT_SHA: revision },
        checkoutRevision: revision,
        checkoutClean: true,
        buildEvidence: verifiedEvidence,
      }),
    /Revision-bound performance evidence is required: artifact_consistent_unattested/,
  );

  const budgetOnly = runBudgetCheck({
    buildDir,
    budgetPath,
    contractRoot: root,
    requireRevisionEvidence: false,
    revisionEnvironment: { GIT_COMMIT_SHA: revision },
    checkoutRevision: revision,
    checkoutClean: true,
    buildEvidence: mismatchedEvidence,
  });
  assert.equal(budgetOnly.report_only, false);
  assert.equal(budgetOnly.revision_evidence_required, false);
  assert.equal(budgetOnly.source_revision_verified, false);
  assert.equal(budgetOnly.revision_evidence_status, "not_enforced");
  assert.equal(
    budgetOnly.observed_revision_evidence_status,
    "artifact_tree_mismatch",
  );
  assert.ok(
    budgetOnly.does_not_establish.includes(
      "revision-bound performance evidence",
    ),
  );

  const report = runBudgetCheck({
    buildDir,
    budgetPath,
    contractRoot: root,
    reportOnly: true,
    revisionEnvironment: { GIT_COMMIT_SHA: revision },
    checkoutRevision: revision,
    checkoutClean: true,
    buildEvidence: mismatchedEvidence,
  });
  assert.equal(report.source_revision_verified, false);
  assert.equal(report.revision_evidence_status, "not_enforced");
  assert.equal(
    report.observed_revision_evidence_status,
    "artifact_tree_mismatch",
  );
  assert.ok(
    report.does_not_establish.includes("revision-bound performance evidence"),
  );

  for (const options of [
    { reportOnly: true, requireRevisionEvidence: true },
    { reportOnly: false, requireRevisionEvidence: false },
  ]) {
    const nonGating = runBudgetCheck({
      buildDir,
      budgetPath,
      contractRoot: root,
      ...options,
      revisionEnvironment: { GIT_COMMIT_SHA: revision },
      checkoutRevision: revision,
      checkoutClean: true,
      buildEvidence: verifiedEvidence,
    });
    assert.equal(nonGating.source_revision_verified, false);
    assert.equal(nonGating.revision_evidence_status, "not_enforced");
    assert.equal(
      nonGating.observed_revision_evidence_status,
      "artifact_consistent_unattested",
    );
    assert.ok(
      nonGating.does_not_establish.includes(
        "revision-bound performance evidence",
      ),
    );
  }
});

test("prints revision and evidence limitations in the default report", () => {
  const text = formatTextReport({
    build_directory: "/tmp/build",
    source_revision: null,
    source_revision_verified: false,
    revision_evidence_status: "missing",
    does_not_establish: [
      "runtime performance from configured thresholds alone",
      "revision-bound performance evidence",
    ],
    routes: [],
  });
  assert.match(text, /source revision: not available \(missing\)/);
  assert.match(
    text,
    /does not establish: runtime performance from configured thresholds alone/,
  );
  assert.match(text, /does not establish: revision-bound performance evidence/);
});

test("route checks reject contracts reached through symlinked parents", (t) => {
  const root = temporaryDirectory(t, "route-budget-contract-root-");
  const outside = temporaryDirectory(t, "route-budget-contract-outside-");
  writeFileSync(
    join(outside, "performance.v1.json"),
    readFileSync(defaultPerformanceContractPath),
  );
  symlinkSync(outside, join(root, "redirect"), "dir");

  assert.throws(
    () =>
      runBudgetCheck({
        buildDir: root,
        budgetPath: join(root, "redirect/performance.v1.json"),
        contractRoot: root,
        revisionEnvironment: {},
        checkoutRevision: null,
      }),
    /path contains symbolic link: redirect/,
  );
});

test("parses CLI arguments without silent or duplicate options", () => {
  assert.deepEqual(
    parseCliArguments([
      "--budget-only",
      "--build-dir",
      "build",
      "--report-only",
      "--json",
    ]),
    {
      budgetOnly: true,
      buildDir: "build",
      json: true,
      reportOnly: true,
    },
  );
  assert.deepEqual(parseCliArguments(["--build-dir=build"]), {
    budgetOnly: false,
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
