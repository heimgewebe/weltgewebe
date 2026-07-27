import { execFileSync } from "node:child_process";
import {
  existsSync,
  lstatSync,
  mkdirSync,
  readFileSync,
  realpathSync,
  renameSync,
  writeFileSync,
} from "node:fs";
import { dirname, isAbsolute, relative, resolve, sep } from "node:path";
import { isDeepStrictEqual } from "node:util";
import {
  loadPerformanceContract,
  repositoryRoot,
} from "./performance-contract.mjs";

const SOURCE_REVISION_RE = /^[0-9a-f]{40}$/;
const METRICS = [
  "largest_contentful_paint_ms",
  "interaction_to_next_paint_ms",
  "usable_map_ms",
];
const EXTRA_LIMITATIONS = [
  "API responses and the local basemap style are deterministic Playwright fixtures.",
  "Interaction latency uses the slower of Chromium Event Timing and a two-animation-frame next-paint fallback; fallback coverage must include every scripted click.",
];
const VALIDITY_ESTABLISHES = [
  "synthetic browser runtime samples for the exact source revision",
  "repeatable profile-level LCP, interaction-to-next-paint and usable-map distributions",
];
const VALIDITY_DOES_NOT_ESTABLISH = [
  "production field performance",
  "real user network performance",
  "API or database capacity",
  "blocking runtime thresholds while the contract remains calibration_required",
];

function object(value, label) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${label} must be an object`);
  }
  return value;
}

function exact(value, fields, label) {
  const record = object(value, label);
  const allowed = new Set(fields);
  for (const key of Object.keys(record)) {
    if (!allowed.has(key)) {
      throw new Error(`${label}: unsupported field ${JSON.stringify(key)}`);
    }
  }
  for (const key of fields) {
    if (!(key in record)) throw new Error(`${label} must define ${key}`);
  }
  return record;
}

function nonEmptyString(value, label) {
  if (typeof value !== "string" || value.length === 0) {
    throw new Error(`${label} must be a non-empty string`);
  }
  return value;
}

function stringList(value, label) {
  if (!Array.isArray(value)) throw new Error(`${label} must be an array`);
  const items = value.map((item, index) =>
    nonEmptyString(item, `${label}[${index}]`),
  );
  if (new Set(items).size !== items.length) {
    throw new Error(`${label} must not contain duplicates`);
  }
  return items;
}

function finite(value, label, minimum = 0) {
  if (!Number.isFinite(value) || value < minimum) {
    throw new Error(`${label} must be a finite number >= ${minimum}`);
  }
  return value;
}

function integer(value, label, minimum = 0) {
  if (!Number.isInteger(value) || value < minimum) {
    throw new Error(`${label} must be an integer >= ${minimum}`);
  }
  return value;
}

function sourceRevision(value) {
  const revision = nonEmptyString(value, "source_revision");
  if (!SOURCE_REVISION_RE.test(revision)) {
    throw new Error("source_revision must be a lowercase 40-character Git SHA");
  }
  return revision;
}

export function resolveExactSourceRevision(environment = process.env) {
  const explicitRevision = environment.WELTGEWEBE_EXACT_REVISION;
  const gitRevision = environment.GIT_COMMIT_SHA;
  const githubRevision = environment.GITHUB_SHA;
  if (explicitRevision !== undefined) {
    const revision = sourceRevision(explicitRevision);
    if (gitRevision !== undefined && sourceRevision(gitRevision) !== revision) {
      throw new Error(
        "GIT_COMMIT_SHA does not match WELTGEWEBE_EXACT_REVISION",
      );
    }
    return revision;
  }
  const candidates = [gitRevision, githubRevision].filter(
    (value) => value !== undefined,
  );
  if (candidates.length === 0) {
    throw new Error(
      "WELTGEWEBE_EXACT_REVISION, GIT_COMMIT_SHA or GITHUB_SHA must define the exact source revision",
    );
  }
  const revisions = candidates.map((value) => sourceRevision(value));
  if (new Set(revisions).size !== 1) {
    throw new Error(
      "GIT_COMMIT_SHA and GITHUB_SHA conflict without WELTGEWEBE_EXACT_REVISION",
    );
  }
  return revisions[0];
}

export function buildExactRevisionAliases(environment = process.env) {
  const revision = resolveExactSourceRevision(environment);
  return {
    WELTGEWEBE_EXACT_REVISION: revision,
    GIT_COMMIT_SHA: revision,
    GITHUB_SHA: revision,
  };
}

export function assertExactRevisionEnvironment(environment = process.env) {
  const revision = resolveExactSourceRevision(environment);
  for (const variable of ["GIT_COMMIT_SHA", "GITHUB_SHA"]) {
    const value = environment[variable];
    if (value !== undefined && sourceRevision(value) !== revision) {
      throw new Error(
        `${variable} does not match the exact source revision ${revision}`,
      );
    }
  }
  return revision;
}

function isoTimestamp(value, label) {
  const timestamp = nonEmptyString(value, label);
  const parsed = new Date(timestamp);
  if (
    !Number.isFinite(parsed.valueOf()) ||
    parsed.toISOString() !== timestamp
  ) {
    throw new Error(`${label} must be an exact ISO-8601 UTC timestamp`);
  }
  return timestamp;
}

function gitOutput(root, args, label) {
  try {
    return execFileSync("git", ["-C", root, ...args], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
    }).trim();
  } catch (error) {
    const detail =
      error && typeof error === "object" && "stderr" in error
        ? String(error.stderr).trim()
        : "";
    throw new Error(`${label} failed${detail ? `: ${detail}` : ""}`);
  }
}

export function assertExactGitCheckout({
  revision,
  root = repositoryRoot,
} = {}) {
  const expectedRevision = sourceRevision(revision);
  const resolvedRoot = realpathSync(resolve(root));
  const actualRevision = sourceRevision(
    gitOutput(resolvedRoot, ["rev-parse", "HEAD"], "git HEAD read"),
  );
  if (actualRevision !== expectedRevision) {
    throw new Error(
      `Git HEAD ${actualRevision} does not match expected source revision ${expectedRevision}`,
    );
  }
  const status = gitOutput(
    resolvedRoot,
    ["status", "--porcelain=v1", "--untracked-files=all"],
    "git status read",
  );
  if (status !== "") {
    throw new Error(
      "exact-revision web runtime evidence requires a clean Git checkout",
    );
  }
  return actualRevision;
}

export function nearestRankPercentile(values, percentile) {
  if (!Array.isArray(values) || values.length === 0) {
    throw new Error("percentile values must not be empty");
  }
  const sorted = values
    .map((value, index) => finite(value, `values[${index}]`))
    .sort((a, b) => a - b);
  integer(percentile, "percentile", 1);
  if (percentile > 100) throw new Error("percentile must be <= 100");
  return sorted[Math.ceil((percentile / 100) * sorted.length) - 1];
}

function validateSample(sample, label, expectedInteractionTestIds) {
  const record = exact(
    sample,
    [
      "run_index",
      "largest_contentful_paint_ms",
      "interaction_to_next_paint_ms",
      "usable_map_ms",
      "interaction_metric_source",
      "observed_interactions",
      "observed_event_entries",
      "observed_fallback_samples",
      "observed_fallback_test_ids",
      "observed_event_timing_test_ids",
      "lcp_entry_count",
    ],
    label,
  );
  integer(record.run_index, `${label}.run_index`, 1);
  for (const metric of METRICS) finite(record[metric], `${label}.${metric}`);
  if (record.interaction_to_next_paint_ms <= 0) {
    throw new Error(`${label}.interaction_to_next_paint_ms must be > 0`);
  }
  if (
    !new Set([
      "event-timing-and-next-paint-fallback",
      "next-paint-fallback",
    ]).has(record.interaction_metric_source)
  ) {
    throw new Error(`${label}.interaction_metric_source is unsupported`);
  }
  const requiredTestIds = stringList(
    expectedInteractionTestIds,
    "expected interaction test ids",
  );
  if (requiredTestIds.length === 0) {
    throw new Error("expected interaction test ids must not be empty");
  }
  const fallbackTestIds = stringList(
    record.observed_fallback_test_ids,
    `${label}.observed_fallback_test_ids`,
  );
  if (!isDeepStrictEqual(fallbackTestIds, requiredTestIds)) {
    throw new Error(
      `${label}.observed_fallback_test_ids must exactly match the scripted interactions`,
    );
  }
  const eventTimingTestIds = stringList(
    record.observed_event_timing_test_ids,
    `${label}.observed_event_timing_test_ids`,
  );
  if (eventTimingTestIds.some((testId) => !requiredTestIds.includes(testId))) {
    throw new Error(
      `${label}.observed_event_timing_test_ids contains an unscripted interaction`,
    );
  }
  const observedInteractions = integer(
    record.observed_interactions,
    `${label}.observed_interactions`,
    0,
  );
  const observedEventEntries = integer(
    record.observed_event_entries,
    `${label}.observed_event_entries`,
    0,
  );
  const observedFallbackSamples = integer(
    record.observed_fallback_samples,
    `${label}.observed_fallback_samples`,
    0,
  );
  if (
    observedFallbackSamples !== requiredTestIds.length ||
    observedFallbackSamples !== fallbackTestIds.length
  ) {
    throw new Error(
      `${label}.observed_fallback_samples must equal the scripted interaction count`,
    );
  }
  if (
    observedInteractions !== eventTimingTestIds.length ||
    observedInteractions > requiredTestIds.length
  ) {
    throw new Error(
      `${label}.observed_interactions must match the scripted Event Timing identities`,
    );
  }
  if (record.interaction_metric_source === "next-paint-fallback") {
    if (
      observedInteractions !== 0 ||
      observedEventEntries !== 0 ||
      eventTimingTestIds.length !== 0
    ) {
      throw new Error(
        `${label} fallback-only samples must not claim Event Timing observations`,
      );
    }
  } else if (
    observedInteractions < 1 ||
    observedEventEntries < observedInteractions
  ) {
    throw new Error(
      `${label} combined interaction samples require coherent Event Timing observations`,
    );
  }
  integer(record.lcp_entry_count, `${label}.lcp_entry_count`, 1);
  return record;
}

function aggregateMetric(samples, metricName, metricContract) {
  const values = samples.map((sample) => sample[metricName]);
  const value = nearestRankPercentile(values, metricContract.percentile);
  return {
    percentile: metricContract.percentile,
    value_ms: value,
    configured_threshold_ms: metricContract.max,
    comparison:
      value <= metricContract.max
        ? "within_configured_threshold"
        : "above_configured_threshold",
    enforcement: "report_only_calibration_required",
  };
}

export function buildWebRuntimeEvidence({
  contract,
  sourceRevision: revision,
  generatedAt,
  browser,
  samplesByProfile,
}) {
  const source = sourceRevision(revision);
  const runtime = contract.measurements.web_runtime;
  if (runtime.status !== "calibration_required") {
    throw new Error(
      "web runtime evidence builder only supports calibration_required",
    );
  }
  const scenarioEntries = Object.entries(runtime.scenarios);
  if (scenarioEntries.length !== 1 || scenarioEntries[0][0] !== "public_map") {
    throw new Error(
      "web runtime evidence requires the canonical public_map scenario",
    );
  }
  const [scenarioId, scenario] = scenarioEntries[0];
  const expectedInteractionTestIds = stringList(
    scenario.interaction.test_ids,
    "public_map scripted interaction test ids",
  );
  if (expectedInteractionTestIds.length === 0) {
    throw new Error("public_map must define scripted interactions");
  }
  const profileEvidence = {};
  for (const [profileId, profile] of Object.entries(runtime.profiles)) {
    const samples = samplesByProfile[profileId];
    if (!Array.isArray(samples) || samples.length !== profile.runs) {
      throw new Error(
        `${profileId} must contain exactly ${profile.runs} measured runs`,
      );
    }
    const validated = samples.map((sample, index) =>
      validateSample(
        sample,
        `profiles.${profileId}.samples[${index}]`,
        expectedInteractionTestIds,
      ),
    );
    const runIndexes = validated.map((sample) => sample.run_index);
    if (new Set(runIndexes).size !== runIndexes.length) {
      throw new Error(`${profileId} run_index values must be unique`);
    }
    const expectedRunIndexes = Array.from(
      { length: profile.runs },
      (_, index) => index + 1,
    );
    if (
      !isDeepStrictEqual(
        [...runIndexes].sort((a, b) => a - b),
        expectedRunIndexes,
      )
    ) {
      throw new Error(
        `${profileId} run_index values must cover 1 through ${profile.runs}`,
      );
    }
    profileEvidence[profileId] = {
      viewport: profile.viewport,
      network_profile: profile.network_profile,
      network_conditions: profile.network_conditions,
      runs: profile.runs,
      samples: validated,
      aggregates: Object.fromEntries(
        METRICS.map((metric) => [
          metric,
          aggregateMetric(validated, metric, scenario.metrics[metric]),
        ]),
      ),
    };
  }
  return {
    schema_version: 1,
    kind: "weltgewebe-web-runtime-evidence",
    contract_id: contract.contract_id,
    contract_status: runtime.status,
    source_revision: source,
    generated_at: isoTimestamp(generatedAt, "generated_at"),
    runner: runtime.runner,
    browser: exact(browser, ["name", "version", "headless"], "browser"),
    scenario: {
      id: scenarioId,
      path: scenario.path,
      readiness: scenario.readiness,
      interaction: scenario.interaction,
    },
    profiles: profileEvidence,
    limitations: [...runtime.limitations, ...EXTRA_LIMITATIONS],
    validity: {
      establishes: [...VALIDITY_ESTABLISHES],
      does_not_establish: [...VALIDITY_DOES_NOT_ESTABLISH],
    },
  };
}

export function validateWebRuntimeEvidence(
  evidence,
  { contract = loadPerformanceContract(), expectedRevision } = {},
) {
  const record = exact(
    evidence,
    [
      "schema_version",
      "kind",
      "contract_id",
      "contract_status",
      "source_revision",
      "generated_at",
      "runner",
      "browser",
      "scenario",
      "profiles",
      "limitations",
      "validity",
    ],
    "web runtime evidence",
  );
  if (record.schema_version !== 1)
    throw new Error("unsupported evidence schema");
  if (record.kind !== "weltgewebe-web-runtime-evidence") {
    throw new Error("unsupported evidence kind");
  }
  if (record.contract_id !== contract.contract_id) {
    throw new Error(
      "evidence contract_id does not match the canonical contract",
    );
  }
  if (record.contract_status !== "calibration_required") {
    throw new Error(
      "evidence contract_status must remain calibration_required",
    );
  }
  const revision = sourceRevision(record.source_revision);
  if (
    expectedRevision !== undefined &&
    revision !== sourceRevision(expectedRevision)
  ) {
    throw new Error(
      "evidence source_revision does not match the expected revision",
    );
  }
  isoTimestamp(record.generated_at, "generated_at");
  if (record.runner !== contract.measurements.web_runtime.runner) {
    throw new Error("evidence runner does not match the canonical contract");
  }
  const browser = exact(
    record.browser,
    ["name", "version", "headless"],
    "browser",
  );
  if (browser.name !== "chromium") {
    throw new Error("browser.name must be chromium");
  }
  nonEmptyString(browser.version, "browser.version");
  if (browser.headless !== true) {
    throw new Error("browser.headless must be true");
  }
  const scenario = exact(
    record.scenario,
    ["id", "path", "readiness", "interaction"],
    "scenario",
  );
  const contractScenario =
    contract.measurements.web_runtime.scenarios.public_map;
  if (scenario.id !== "public_map" || scenario.path !== contractScenario.path) {
    throw new Error("evidence scenario does not match public_map");
  }
  if (
    !isDeepStrictEqual(scenario.readiness, contractScenario.readiness) ||
    !isDeepStrictEqual(scenario.interaction, contractScenario.interaction)
  ) {
    throw new Error(
      "evidence scenario execution metadata does not match the contract",
    );
  }
  const profiles = object(record.profiles, "profiles");
  const expectedProfiles = Object.keys(
    contract.measurements.web_runtime.profiles,
  );
  if (
    Object.keys(profiles).length !== expectedProfiles.length ||
    expectedProfiles.some((profileId) => !(profileId in profiles))
  ) {
    throw new Error("evidence profiles do not match the canonical contract");
  }
  for (const profileId of expectedProfiles) {
    const contractProfile =
      contract.measurements.web_runtime.profiles[profileId];
    const profile = exact(
      profiles[profileId],
      [
        "viewport",
        "network_profile",
        "network_conditions",
        "runs",
        "samples",
        "aggregates",
      ],
      `profiles.${profileId}`,
    );
    if (
      !isDeepStrictEqual(profile.viewport, contractProfile.viewport) ||
      profile.network_profile !== contractProfile.network_profile ||
      !isDeepStrictEqual(
        profile.network_conditions,
        contractProfile.network_conditions,
      )
    ) {
      throw new Error(
        `${profileId} execution profile does not match the contract`,
      );
    }
    if (
      !Array.isArray(profile.samples) ||
      profile.runs !== contractProfile.runs ||
      profile.samples.length !== contractProfile.runs
    ) {
      throw new Error(
        `${profileId} measured run count does not match the contract`,
      );
    }
    const validatedSamples = profile.samples.map((sample, index) =>
      validateSample(
        sample,
        `profiles.${profileId}.samples[${index}]`,
        contractScenario.interaction.test_ids,
      ),
    );
    const runIndexes = validatedSamples.map((sample) => sample.run_index);
    const expectedRunIndexes = Array.from(
      { length: contractProfile.runs },
      (_, index) => index + 1,
    );
    if (
      !isDeepStrictEqual(
        [...runIndexes].sort((a, b) => a - b),
        expectedRunIndexes,
      )
    ) {
      throw new Error(
        `${profileId} run_index values must cover 1 through ${contractProfile.runs}`,
      );
    }
    const aggregates = exact(
      profile.aggregates,
      METRICS,
      `profiles.${profileId}.aggregates`,
    );
    for (const metric of METRICS) {
      const aggregate = exact(
        aggregates[metric],
        [
          "percentile",
          "value_ms",
          "configured_threshold_ms",
          "comparison",
          "enforcement",
        ],
        `profiles.${profileId}.aggregates.${metric}`,
      );
      const expectedMetric = contractScenario.metrics[metric];
      if (
        aggregate.percentile !== expectedMetric.percentile ||
        aggregate.configured_threshold_ms !== expectedMetric.max ||
        aggregate.enforcement !== "report_only_calibration_required"
      ) {
        throw new Error(
          `${profileId}.${metric} aggregate is not contract-bound`,
        );
      }
      const expectedValue = nearestRankPercentile(
        profile.samples.map((sample) => sample[metric]),
        expectedMetric.percentile,
      );
      const expectedComparison =
        expectedValue <= expectedMetric.max
          ? "within_configured_threshold"
          : "above_configured_threshold";
      if (
        aggregate.value_ms !== expectedValue ||
        aggregate.comparison !== expectedComparison
      ) {
        throw new Error(
          `${profileId}.${metric} aggregate does not match samples`,
        );
      }
    }
  }
  const expectedLimitations = [
    ...contract.measurements.web_runtime.limitations,
    ...EXTRA_LIMITATIONS,
  ];
  if (!isDeepStrictEqual(record.limitations, expectedLimitations)) {
    throw new Error("evidence limitations do not match the canonical contract");
  }
  const validity = exact(
    record.validity,
    ["establishes", "does_not_establish"],
    "validity",
  );
  if (
    !isDeepStrictEqual(validity.establishes, VALIDITY_ESTABLISHES) ||
    !isDeepStrictEqual(validity.does_not_establish, VALIDITY_DOES_NOT_ESTABLISH)
  ) {
    throw new Error("evidence validity boundaries are not canonical");
  }
  return record;
}

function repositoryPath(path, label) {
  const root = realpathSync(repositoryRoot);
  const target = resolve(path);
  const fromRoot = relative(root, target);
  if (
    fromRoot === "" ||
    fromRoot === ".." ||
    fromRoot.startsWith(`..${sep}`) ||
    isAbsolute(fromRoot)
  ) {
    throw new Error(`${label} must be inside the repository`);
  }
  return { root, target, components: fromRoot.split(sep) };
}

function inspectRepositoryPath(
  path,
  label,
  { leafKind, allowMissing = false } = {},
) {
  const resolved = repositoryPath(path, label);
  let current = resolved.root;
  for (let index = 0; index < resolved.components.length; index += 1) {
    current = resolve(current, resolved.components[index]);
    let metadata;
    try {
      metadata = lstatSync(current);
    } catch (error) {
      if (
        allowMissing &&
        error &&
        typeof error === "object" &&
        error.code === "ENOENT"
      ) {
        return resolved;
      }
      throw new Error(
        `${label} cannot be inspected: ${error instanceof Error ? error.message : String(error)}`,
      );
    }
    if (metadata.isSymbolicLink()) {
      throw new Error(`${label} must not contain symbolic links`);
    }
    const isLeaf = index === resolved.components.length - 1;
    if (!isLeaf && !metadata.isDirectory()) {
      throw new Error(`${label} contains a non-directory ancestor`);
    }
    if (isLeaf && leafKind === "directory" && !metadata.isDirectory()) {
      throw new Error(`${label} must be a directory`);
    }
    if (isLeaf && leafKind === "file" && !metadata.isFile()) {
      throw new Error(`${label} must be a regular file`);
    }
  }
  const realTarget = realpathSync(resolved.target);
  const realFromRoot = relative(resolved.root, realTarget);
  if (
    realFromRoot === "" ||
    realFromRoot === ".." ||
    realFromRoot.startsWith(`..${sep}`) ||
    isAbsolute(realFromRoot)
  ) {
    throw new Error(`${label} escapes the repository`);
  }
  return resolved;
}

function prepareRepositoryDirectory(path, label) {
  inspectRepositoryPath(path, label, {
    leafKind: "directory",
    allowMissing: true,
  });
  mkdirSync(resolve(path), { recursive: true });
  return inspectRepositoryPath(path, label, {
    leafKind: "directory",
  }).target;
}

export function writeWebRuntimeEvidence(
  evidence,
  outputDirectory = resolve(repositoryRoot, "build/proofs/web-runtime"),
) {
  const validated = validateWebRuntimeEvidence(evidence, {
    expectedRevision: evidence.source_revision,
  });
  const directory = prepareRepositoryDirectory(
    outputDirectory,
    "output directory",
  );
  const filename = `web-runtime-${validated.source_revision}.json`;
  const destination = resolve(directory, filename);
  if (existsSync(destination) && lstatSync(destination).isSymbolicLink()) {
    throw new Error("evidence destination must not be a symbolic link");
  }
  const temporary = resolve(
    directory,
    `.${filename}.${process.pid}.${Date.now()}.tmp`,
  );
  const payload = `${JSON.stringify(validated, null, 2)}\n`;
  writeFileSync(temporary, payload, {
    encoding: "utf8",
    flag: "wx",
    mode: 0o600,
  });
  renameSync(temporary, destination);
  return destination;
}

export function readAndValidateWebRuntimeEvidence(path, expectedRevision) {
  const resolved = inspectRepositoryPath(path, "evidence path", {
    leafKind: "file",
  }).target;
  return validateWebRuntimeEvidence(
    JSON.parse(readFileSync(resolved, "utf8")),
    {
      expectedRevision,
    },
  );
}

export function defaultEvidencePath(revision) {
  return resolve(
    repositoryRoot,
    "build/proofs/web-runtime",
    `web-runtime-${sourceRevision(revision)}.json`,
  );
}
