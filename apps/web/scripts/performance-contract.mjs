import { lstatSync, readFileSync, realpathSync } from "node:fs";
import { dirname, isAbsolute, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { validatePerformanceBudget } from "./route-performance-budget-config.mjs";

const modulePath = fileURLToPath(import.meta.url);
export const repositoryRoot = resolve(dirname(modulePath), "../../..");
export const defaultPerformanceContractPath = resolve(
  repositoryRoot,
  "policies/performance.v1.json",
);

const ROOT_FIELDS = [
  "schema_version",
  "contract_id",
  "authority",
  "measurements",
  "legacy_contracts",
];
const MEASUREMENT_FIELDS = [
  "web_build",
  "web_runtime",
  "api_runtime",
  "database_scale",
  "api_replica_resources",
];
const WEB_RUNTIME_METRICS = [
  "largest_contentful_paint_ms",
  "interaction_to_next_paint_ms",
  "usable_map_ms",
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

function string(value, label) {
  if (typeof value !== "string" || value.length === 0) {
    throw new Error(`${label} must be a non-empty string`);
  }
  return value;
}

function boolean(value, label) {
  if (typeof value !== "boolean") {
    throw new Error(`${label} must be a boolean`);
  }
  return value;
}

function integer(value, label, minimum = 0) {
  if (!Number.isInteger(value) || value < minimum) {
    throw new Error(`${label} must be an integer >= ${minimum}`);
  }
}

function strings(value, label) {
  if (
    !Array.isArray(value) ||
    value.length === 0 ||
    value.some((entry) => typeof entry !== "string" || entry.length === 0)
  ) {
    throw new Error(`${label} must contain non-empty strings`);
  }
  if (new Set(value).size !== value.length) {
    throw new Error(`${label} must not contain duplicates`);
  }
  return value;
}

function safePath(value, label) {
  const path = string(value, label);
  if (
    isAbsolute(path) ||
    path.includes("\\") ||
    path
      .split("/")
      .some((segment) => segment === "" || segment === "." || segment === "..")
  ) {
    throw new Error(`${label} must be a safe repository-relative path`);
  }
}

function replacementReference(value, label) {
  const reference = string(value, label);
  const separator = reference.indexOf("#");
  const path = separator >= 0 ? reference.slice(0, separator) : reference;
  const fragment = separator >= 0 ? reference.slice(separator + 1) : null;
  safePath(path, label);
  if (fragment !== null && fragment.length === 0) {
    throw new Error(`${label} fragment must not be empty`);
  }
  return { reference, path, fragment };
}

function status(record, expected, label) {
  if (record.status !== expected) {
    throw new Error(`${label}.status must remain ${expected}`);
  }
}

function metric(value, label) {
  const record = object(value, label);
  const allowed = new Set(["percentile", "max"]);
  for (const key of Object.keys(record)) {
    if (!allowed.has(key)) {
      throw new Error(`${label}: unsupported field ${JSON.stringify(key)}`);
    }
  }
  if (!Number.isFinite(record.max) || record.max < 0) {
    throw new Error(`${label}: max must be a finite number >= 0`);
  }
  if ("percentile" in record) {
    integer(record.percentile, `${label}: percentile`, 1);
    if (record.percentile > 100) {
      throw new Error(`${label}: percentile must be <= 100`);
    }
  }
}

function metrics(value, label, requiredFields = null) {
  const record = requiredFields
    ? exact(value, requiredFields, label)
    : object(value, label);
  if (Object.keys(record).length === 0) {
    throw new Error(`${label} must not be empty`);
  }
  for (const [name, metricValue] of Object.entries(record)) {
    metric(metricValue, `${label}.${name}`);
  }
}

function calibratedLater(value, fields, label) {
  const record = exact(value, fields, label);
  status(record, "calibration_required", label);
  strings(record.limitations, `${label}.limitations`);
  string(record.artifact_kind, `${label}.artifact_kind`);
  return record;
}

function validateNetworkConditions(value, label) {
  const conditions = exact(
    value,
    [
      "throttled",
      "latency_ms",
      "download_kbps",
      "upload_kbps",
      "connection_type",
    ],
    label,
  );
  boolean(conditions.throttled, `${label}.throttled`);
  integer(conditions.latency_ms, `${label}.latency_ms`);
  integer(conditions.download_kbps, `${label}.download_kbps`);
  integer(conditions.upload_kbps, `${label}.upload_kbps`);
  string(conditions.connection_type, `${label}.connection_type`);
  if (
    conditions.throttled &&
    (conditions.download_kbps === 0 || conditions.upload_kbps === 0)
  ) {
    throw new Error(`${label} throttled profiles require non-zero throughput`);
  }
  if (
    !conditions.throttled &&
    (conditions.latency_ms !== 0 ||
      conditions.download_kbps !== 0 ||
      conditions.upload_kbps !== 0)
  ) {
    throw new Error(
      `${label} unthrottled profiles must use zero network limits`,
    );
  }
}

function validateWebRuntime(value) {
  const label = "measurements.web_runtime";
  const record = calibratedLater(
    value,
    [
      "status",
      "runner",
      "artifact_kind",
      "profiles",
      "scenarios",
      "limitations",
    ],
    label,
  );
  safePath(record.runner, `${label}.runner`);

  const profiles = object(record.profiles, `${label}.profiles`);
  if (Object.keys(profiles).length === 0) {
    throw new Error(`${label}.profiles must not be empty`);
  }
  for (const [name, value] of Object.entries(profiles)) {
    const profileLabel = `${label}.profiles.${name}`;
    const profile = exact(
      value,
      ["viewport", "network_profile", "network_conditions", "runs"],
      profileLabel,
    );
    const viewport = exact(
      profile.viewport,
      ["width", "height"],
      `${profileLabel}.viewport`,
    );
    integer(viewport.width, `${profileLabel}.viewport.width`, 1);
    integer(viewport.height, `${profileLabel}.viewport.height`, 1);
    string(profile.network_profile, `${profileLabel}.network_profile`);
    validateNetworkConditions(
      profile.network_conditions,
      `${profileLabel}.network_conditions`,
    );
    integer(profile.runs, `${profileLabel}.runs`, 1);
  }

  const scenarios = object(record.scenarios, `${label}.scenarios`);
  if (Object.keys(scenarios).length === 0) {
    throw new Error(`${label}.scenarios must not be empty`);
  }
  for (const [name, value] of Object.entries(scenarios)) {
    const scenarioLabel = `${label}.scenarios.${name}`;
    const scenario = exact(
      value,
      ["path", "readiness", "interaction", "metrics"],
      scenarioLabel,
    );
    if (typeof scenario.path !== "string" || !scenario.path.startsWith("/")) {
      throw new Error(`${scenarioLabel}.path must be absolute`);
    }
    const readiness = exact(
      scenario.readiness,
      ["required_selectors", "timeout_ms"],
      `${scenarioLabel}.readiness`,
    );
    strings(
      readiness.required_selectors,
      `${scenarioLabel}.readiness.required_selectors`,
    );
    integer(readiness.timeout_ms, `${scenarioLabel}.readiness.timeout_ms`, 1);
    const interaction = exact(
      scenario.interaction,
      ["test_ids", "expected_test_id", "settle_frames"],
      `${scenarioLabel}.interaction`,
    );
    strings(interaction.test_ids, `${scenarioLabel}.interaction.test_ids`);
    string(
      interaction.expected_test_id,
      `${scenarioLabel}.interaction.expected_test_id`,
    );
    integer(
      interaction.settle_frames,
      `${scenarioLabel}.interaction.settle_frames`,
      1,
    );
    metrics(scenario.metrics, `${scenarioLabel}.metrics`, WEB_RUNTIME_METRICS);
  }
}

function validateApiRuntime(value) {
  const label = "measurements.api_runtime";
  const record = calibratedLater(
    value,
    ["status", "runner", "artifact_kind", "scenario", "metrics", "limitations"],
    label,
  );
  string(record.runner, `${label}.runner`);
  const scenario = exact(
    record.scenario,
    [
      "virtual_users",
      "duration_seconds",
      "dataset_profile",
      "concurrency_profile",
    ],
    `${label}.scenario`,
  );
  integer(scenario.virtual_users, `${label}.scenario.virtual_users`, 1);
  integer(scenario.duration_seconds, `${label}.scenario.duration_seconds`, 1);
  string(scenario.dataset_profile, `${label}.scenario.dataset_profile`);
  string(scenario.concurrency_profile, `${label}.scenario.concurrency_profile`);
  metrics(record.metrics, `${label}.metrics`);
}

function validateDatabaseScale(value) {
  const label = "measurements.database_scale";
  const record = exact(
    value,
    ["status", "runner", "artifact_kind", "config", "profiles", "limitations"],
    label,
  );
  status(record, "blocking_plan_shape", label);
  safePath(record.runner, `${label}.runner`);
  string(record.artifact_kind, `${label}.artifact_kind`);
  safePath(record.config, `${label}.config`);
  strings(record.profiles, `${label}.profiles`);
  strings(record.limitations, `${label}.limitations`);
}

function validateResources(value) {
  const label = "measurements.api_replica_resources";
  const record = calibratedLater(
    value,
    ["status", "artifact_kind", "metrics", "limitations"],
    label,
  );
  strings(record.metrics, `${label}.metrics`);
}

export function validatePerformanceContract(value) {
  const contract = exact(value, ROOT_FIELDS, "performance contract");
  if (contract.schema_version !== 1) {
    throw new Error("performance contract must use schema_version 1");
  }
  if (contract.contract_id !== "weltgewebe-performance-v1") {
    throw new Error(
      "performance contract must use contract_id weltgewebe-performance-v1",
    );
  }

  const authority = exact(
    contract.authority,
    ["status", "replaces", "does_not_establish"],
    "authority",
  );
  if (authority.status !== "canonical") {
    throw new Error("authority.status must be canonical");
  }
  const replacements = strings(authority.replaces, "authority.replaces").map(
    (value) => replacementReference(value, "authority.replaces entry"),
  );
  strings(authority.does_not_establish, "authority.does_not_establish");

  const measurementsRecord = exact(
    contract.measurements,
    MEASUREMENT_FIELDS,
    "measurements",
  );
  const webBuild = exact(
    measurementsRecord.web_build,
    ["status", "runner", "artifact_kind", "budget"],
    "measurements.web_build",
  );
  status(webBuild, "blocking", "measurements.web_build");
  safePath(webBuild.runner, "measurements.web_build.runner");
  string(webBuild.artifact_kind, "measurements.web_build.artifact_kind");
  validatePerformanceBudget(webBuild.budget);
  validateWebRuntime(measurementsRecord.web_runtime);
  validateApiRuntime(measurementsRecord.api_runtime);
  validateDatabaseScale(measurementsRecord.database_scale);
  validateResources(measurementsRecord.api_replica_resources);

  const legacy = exact(
    contract.legacy_contracts,
    ["must_not_exist", "slo_reference"],
    "legacy_contracts",
  );
  const absentPaths = strings(
    legacy.must_not_exist,
    "legacy_contracts.must_not_exist",
  );
  for (const path of absentPaths) {
    safePath(path, "legacy_contracts.must_not_exist entry");
  }
  const replacedFiles = replacements
    .filter((replacement) => replacement.fragment === null)
    .map((replacement) => replacement.path);
  const absentSet = new Set(absentPaths);
  const replacedSet = new Set(replacedFiles);
  const missingAbsenceRules = replacedFiles.filter(
    (path) => !absentSet.has(path),
  );
  if (missingAbsenceRules.length > 0) {
    throw new Error(
      `authority.replaces file paths must be enforced by legacy_contracts.must_not_exist: ${missingAbsenceRules.join(", ")}`,
    );
  }
  const undeclaredAbsenceRules = absentPaths.filter(
    (path) => !replacedSet.has(path),
  );
  if (undeclaredAbsenceRules.length > 0) {
    throw new Error(
      `legacy_contracts.must_not_exist paths must be declared by authority.replaces: ${undeclaredAbsenceRules.join(", ")}`,
    );
  }
  safePath(legacy.slo_reference, "legacy_contracts.slo_reference");
  return contract;
}

export function parsePerformanceContract(text) {
  try {
    return validatePerformanceContract(JSON.parse(text));
  } catch (error) {
    if (error instanceof SyntaxError) {
      throw new Error(
        `Performance contract is not valid JSON: ${error.message}`,
      );
    }
    throw error;
  }
}

export function assertLegacyContractsAbsent(contract, root = repositoryRoot) {
  const resolvedRoot = realpathSync(resolve(root));
  for (const relativePath of contract.legacy_contracts.must_not_exist) {
    const target = resolve(resolvedRoot, relativePath);
    const fromRoot = relative(resolvedRoot, target);
    if (
      fromRoot === "" ||
      fromRoot === ".." ||
      fromRoot.startsWith(`..${sep}`) ||
      isAbsolute(fromRoot)
    ) {
      throw new Error(
        `Legacy contract path escapes repository: ${relativePath}`,
      );
    }

    const components = fromRoot.split(sep);
    let current = resolvedRoot;
    for (let index = 0; index < components.length; index += 1) {
      current = resolve(current, components[index]);
      let metadata;
      try {
        metadata = lstatSync(current);
      } catch (error) {
        if (error && typeof error === "object" && error.code === "ENOENT") {
          break;
        }
        throw new Error(
          `Cannot inspect legacy performance contract ${relativePath}: ${error instanceof Error ? error.message : String(error)}`,
        );
      }
      if (metadata.isSymbolicLink()) {
        const component = relative(resolvedRoot, current);
        throw new Error(
          `Legacy contract path contains symbolic link: ${relativePath} (${component})`,
        );
      }
      const isLeaf = index === components.length - 1;
      if (!isLeaf && !metadata.isDirectory()) {
        const component = relative(resolvedRoot, current);
        throw new Error(
          `Legacy contract path has non-directory ancestor: ${relativePath} (${component})`,
        );
      }
      if (isLeaf) {
        const kind = metadata.isFile() ? "file" : "non-file";
        throw new Error(
          `Legacy performance contract still exists: ${relativePath} (${kind})`,
        );
      }
    }
  }
}

function readPerformanceContractFile(contractPath, root) {
  const resolvedRoot = realpathSync(resolve(root));
  const resolvedContract = resolve(contractPath);
  const lexicalFromRoot = relative(resolvedRoot, resolvedContract);
  if (
    lexicalFromRoot === "" ||
    lexicalFromRoot === ".." ||
    lexicalFromRoot.startsWith(`..${sep}`) ||
    isAbsolute(lexicalFromRoot)
  ) {
    throw new Error("Performance contract escapes repository root");
  }

  const components = lexicalFromRoot.split(sep);
  let current = resolvedRoot;
  for (let index = 0; index < components.length; index += 1) {
    current = resolve(current, components[index]);
    const metadata = lstatSync(current);
    const component = relative(resolvedRoot, current);
    if (metadata.isSymbolicLink()) {
      throw new Error(
        `Performance contract path contains symbolic link: ${component}`,
      );
    }
    const isLeaf = index === components.length - 1;
    if (!isLeaf && !metadata.isDirectory()) {
      throw new Error(
        `Performance contract path has non-directory ancestor: ${component}`,
      );
    }
    if (isLeaf && !metadata.isFile()) {
      throw new Error("Performance contract must be a regular file");
    }
  }

  const realContract = realpathSync(resolvedContract);
  const fromRoot = relative(resolvedRoot, realContract);
  if (
    fromRoot === "" ||
    fromRoot === ".." ||
    fromRoot.startsWith(`..${sep}`) ||
    isAbsolute(fromRoot)
  ) {
    throw new Error("Performance contract escapes repository root");
  }
  return readFileSync(resolvedContract, "utf8");
}

export function loadPerformanceContract({
  contractPath = defaultPerformanceContractPath,
  enforceLegacyAbsence = false,
  root = repositoryRoot,
} = {}) {
  const contract = parsePerformanceContract(
    readPerformanceContractFile(contractPath, root),
  );
  if (enforceLegacyAbsence) assertLegacyContractsAbsent(contract, root);
  return contract;
}
