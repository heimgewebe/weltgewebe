import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import {
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  symlinkSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import test from "node:test";
import {
  loadPerformanceContract,
  repositoryRoot,
} from "./performance-contract.mjs";
import {
  assertExactGitCheckout,
  buildWebRuntimeEvidence,
  defaultEvidencePath,
  nearestRankPercentile,
  readAndValidateWebRuntimeEvidence,
  validateWebRuntimeEvidence,
  writeWebRuntimeEvidence,
} from "./web-runtime-evidence.mjs";

const REVISION = "a".repeat(40);

function sample(runIndex, offset = 0) {
  return {
    run_index: runIndex,
    largest_contentful_paint_ms: 1000 + offset,
    interaction_to_next_paint_ms: 40 + offset,
    usable_map_ms: 1500 + offset,
    interaction_metric_source: "event-timing",
    observed_interactions: 2,
    observed_event_entries: 6,
    lcp_entry_count: 1,
  };
}

function git(root, args) {
  return execFileSync("git", ["-C", root, ...args], {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  }).trim();
}

function evidence(overrides = {}) {
  const contract = loadPerformanceContract();
  const samplesByProfile = Object.fromEntries(
    Object.entries(contract.measurements.web_runtime.profiles).map(
      ([profileId, profile]) => [
        profileId,
        Array.from({ length: profile.runs }, (_, index) =>
          sample(index + 1, index * 10),
        ),
      ],
    ),
  );
  return buildWebRuntimeEvidence({
    contract,
    sourceRevision: REVISION,
    generatedAt: "2026-07-26T13:00:00.000Z",
    browser: { name: "chromium", version: "test", headless: true },
    samplesByProfile,
    ...overrides,
  });
}

test("binds evidence to the exact clean Git checkout", (t) => {
  const root = mkdtempSync(join(tmpdir(), "web-runtime-git-binding-"));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  git(root, ["init", "--quiet"]);
  writeFileSync(join(root, "tracked.txt"), "bound\n");
  git(root, ["add", "tracked.txt"]);
  git(root, [
    "-c",
    "user.name=weltgewebe-test",
    "-c",
    "user.email=weltgewebe-test@example.invalid",
    "commit",
    "--quiet",
    "-m",
    "test binding",
  ]);
  const revision = git(root, ["rev-parse", "HEAD"]);
  assert.equal(assertExactGitCheckout({ revision, root }), revision);
  assert.throws(
    () => assertExactGitCheckout({ revision: "b".repeat(40), root }),
    /does not match expected source revision/,
  );
  writeFileSync(join(root, "untracked.txt"), "untracked\n");
  assert.throws(
    () => assertExactGitCheckout({ revision, root }),
    /requires a clean Git checkout/,
  );
});

test("rejects evidence paths through symbolic-link ancestors", (t) => {
  const proofsRoot = resolve(repositoryRoot, "build/proofs");
  const linkedDirectory = resolve(proofsRoot, "web-runtime-symlink-test");
  const outside = mkdtempSync(join(tmpdir(), "web-runtime-outside-"));
  rmSync(linkedDirectory, { recursive: true, force: true });
  mkdirSync(proofsRoot, { recursive: true });
  symlinkSync(outside, linkedDirectory, "dir");
  t.after(() => {
    rmSync(linkedDirectory, { recursive: true, force: true });
    rmSync(outside, { recursive: true, force: true });
  });
  assert.throws(
    () =>
      writeWebRuntimeEvidence(evidence(), resolve(linkedDirectory, "nested")),
    /must not contain symbolic links/,
  );
});

test("uses deterministic nearest-rank percentiles", () => {
  assert.equal(nearestRankPercentile([5, 1, 4, 2, 3], 75), 4);
  assert.equal(nearestRankPercentile([5, 1, 4, 2, 3], 95), 5);
  assert.throws(() => nearestRankPercentile([], 75), /must not be empty/);
});

test("builds report-only evidence from the canonical profiles", () => {
  const result = evidence();
  assert.equal(result.source_revision, REVISION);
  assert.deepEqual(Object.keys(result.profiles).sort(), ["desktop", "mobile"]);
  assert.equal(
    result.profiles.desktop.aggregates.largest_contentful_paint_ms.value_ms,
    1030,
  );
  assert.equal(
    result.profiles.desktop.aggregates.largest_contentful_paint_ms.enforcement,
    "report_only_calibration_required",
  );
  assert.ok(
    result.validity.does_not_establish.includes("production field performance"),
  );
});

test("rejects missing runs, stale revisions and manipulated aggregates", () => {
  const contract = loadPerformanceContract();
  const samplesByProfile = {
    desktop: [sample(1)],
    mobile: Array.from({ length: 5 }, (_, index) => sample(index + 1)),
  };
  assert.throws(
    () =>
      buildWebRuntimeEvidence({
        contract,
        sourceRevision: REVISION,
        generatedAt: "2026-07-26T13:00:00.000Z",
        browser: { name: "chromium", version: "test", headless: true },
        samplesByProfile,
      }),
    /desktop must contain exactly 5 measured runs/,
  );

  const result = evidence();
  assert.throws(
    () =>
      validateWebRuntimeEvidence(result, { expectedRevision: "b".repeat(40) }),
    /does not match the expected revision/,
  );
  result.profiles.desktop.aggregates.usable_map_ms.value_ms = 1;
  assert.throws(
    () => validateWebRuntimeEvidence(result, { expectedRevision: REVISION }),
    /aggregate does not match samples/,
  );
});

test("rejects incomplete run indexes and rewritten evidence boundaries", () => {
  const contract = loadPerformanceContract();
  const shiftedSamples = Object.fromEntries(
    Object.entries(contract.measurements.web_runtime.profiles).map(
      ([profileId, profile]) => [
        profileId,
        Array.from({ length: profile.runs }, (_, index) =>
          sample(index + 2, index * 10),
        ),
      ],
    ),
  );
  assert.throws(
    () =>
      buildWebRuntimeEvidence({
        contract,
        sourceRevision: REVISION,
        generatedAt: "2026-07-26T13:00:00.000Z",
        browser: { name: "chromium", version: "test", headless: true },
        samplesByProfile: shiftedSamples,
      }),
    /run_index values must cover 1 through 5/,
  );

  const rewrittenLimitations = evidence();
  rewrittenLimitations.limitations = ["all production limits are proven"];
  assert.throws(
    () =>
      validateWebRuntimeEvidence(rewrittenLimitations, {
        expectedRevision: REVISION,
      }),
    /limitations do not match the canonical contract/,
  );

  const rewrittenValidity = evidence();
  rewrittenValidity.validity.does_not_establish = [];
  assert.throws(
    () =>
      validateWebRuntimeEvidence(rewrittenValidity, {
        expectedRevision: REVISION,
      }),
    /validity boundaries are not canonical/,
  );

  const invalidTimestamp = evidence();
  invalidTimestamp.generated_at = "not-a-timestamp";
  assert.throws(
    () =>
      validateWebRuntimeEvidence(invalidTimestamp, {
        expectedRevision: REVISION,
      }),
    /exact ISO-8601 UTC timestamp/,
  );

  const wrongBrowser = evidence();
  wrongBrowser.browser.name = "firefox";
  assert.throws(
    () =>
      validateWebRuntimeEvidence(wrongBrowser, {
        expectedRevision: REVISION,
      }),
    /browser.name must be chromium/,
  );
});

test("writes and reads one commit-bound evidence artifact", (t) => {
  const outputDirectory = resolve(
    repositoryRoot,
    "build/proofs/web-runtime-test",
  );
  rmSync(outputDirectory, { recursive: true, force: true });
  t.after(() => rmSync(outputDirectory, { recursive: true, force: true }));
  const path = writeWebRuntimeEvidence(evidence(), outputDirectory);
  assert.equal(path, resolve(outputDirectory, `web-runtime-${REVISION}.json`));
  assert.equal(
    JSON.parse(readFileSync(path, "utf8")).source_revision,
    REVISION,
  );
  assert.equal(
    readAndValidateWebRuntimeEvidence(path, REVISION).kind,
    "weltgewebe-web-runtime-evidence",
  );
  assert.equal(
    defaultEvidencePath(REVISION).endsWith(`web-runtime-${REVISION}.json`),
    true,
  );
});
