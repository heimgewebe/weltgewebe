import assert from "node:assert/strict";
import {
  mkdirSync,
  readFileSync,
  rmSync,
  symlinkSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { mkdtempSync } from "node:fs";
import test from "node:test";
import {
  assertLegacyContractsAbsent,
  loadPerformanceContract,
  parsePerformanceContract,
  repositoryRoot,
  validatePerformanceContract,
} from "./performance-contract.mjs";

function validRouteBudget() {
  return {
    schema_version: 2,
    measurement: "test route assets",
    output_directories: ["build"],
    routes: {
      "/map": {
        max_initial_js_gzip_bytes: 100,
        max_initial_css_gzip_bytes: 100,
        forbid_css_markers: [],
        require_css_markers: [],
        min_initial_js_assets: 1,
        min_initial_css_assets: 1,
      },
    },
    emitted_assets: {},
  };
}

function validContract(overrides = {}) {
  return {
    schema_version: 1,
    contract_id: "weltgewebe-performance-v1",
    authority: {
      status: "canonical",
      replaces: ["ci/budget.json"],
      does_not_establish: ["production capacity"],
    },
    measurements: {
      web_build: {
        status: "blocking",
        runner: "apps/web/scripts/assert-route-performance-budget.mjs",
        artifact_kind: "generated-route-assets",
        budget: validRouteBudget(),
      },
      web_runtime: {
        status: "calibration_required",
        runner: "playwright",
        artifact_kind: "browser-runtime-samples",
        profiles: {
          mobile: {
            viewport: { width: 390, height: 844 },
            network_profile: "fast-3g",
            runs: 5,
          },
        },
        scenarios: {
          map: {
            path: "/map",
            metrics: {
              largest_contentful_paint_ms: { percentile: 75, max: 2500 },
            },
          },
        },
        limitations: ["not production field data"],
      },
      api_runtime: {
        status: "calibration_required",
        runner: "k6",
        artifact_kind: "api-load-samples",
        scenario: {
          virtual_users: 10,
          duration_seconds: 30,
          dataset_profile: "ci",
          concurrency_profile: "mixed-read",
        },
        metrics: {
          http_request_duration_ms: { percentile: 95, max: 300 },
          http_request_failed_rate: { max: 0.01 },
        },
        limitations: ["not production capacity"],
      },
      database_scale: {
        status: "blocking_plan_shape",
        runner: "scripts/performance/domain_scale.py",
        artifact_kind: "postgresql-plan-evidence",
        config: "configs/performance/domain-scale.v1.json",
        profiles: ["ci"],
        limitations: ["not end-to-end latency"],
      },
      api_replica_resources: {
        status: "calibration_required",
        artifact_kind: "container-resource-samples",
        metrics: ["cpu_seconds", "max_rss_bytes"],
        limitations: ["not calibrated"],
      },
    },
    legacy_contracts: {
      must_not_exist: ["ci/budget.json"],
      slo_reference: "policies/slo.yaml",
    },
    ...overrides,
  };
}

function temporaryDirectory(t) {
  const root = mkdtempSync(join(tmpdir(), "performance-contract-"));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  return root;
}

test("loads the repository canonical contract", () => {
  const contract = loadPerformanceContract();
  assert.equal(contract.contract_id, "weltgewebe-performance-v1");
  assert.equal(contract.authority.status, "canonical");
  assert.equal(contract.measurements.web_build.status, "blocking");
  assert.equal(
    contract.measurements.web_runtime.status,
    "calibration_required",
  );
});

test("packages the canonical contract before the Docker web build", () => {
  const dockerfile = readFileSync(
    resolve(repositoryRoot, "apps/web/Dockerfile"),
    "utf8",
  );
  const contractCopy =
    "COPY policies/performance.v1.json /policies/performance.v1.json";
  const copyIndex = dockerfile.indexOf(contractCopy);
  const buildIndex = dockerfile.indexOf("pnpm build");
  assert.ok(copyIndex >= 0, "Docker builder must copy the canonical contract");
  assert.ok(
    buildIndex >= 0 && copyIndex < buildIndex,
    "Docker builder must copy the canonical contract before pnpm build",
  );
});

test("rejects magic fields, missing measurements and invalid percentiles", () => {
  assert.throws(
    () => validatePerformanceContract(validContract({ typo: true })),
    /unsupported field "typo"/,
  );
  const missing = validContract();
  delete missing.measurements.api_runtime;
  assert.throws(
    () => validatePerformanceContract(missing),
    /must define api_runtime/,
  );
  const percentile = validContract();
  percentile.measurements.web_runtime.scenarios.map.metrics.largest_contentful_paint_ms.percentile = 101;
  assert.throws(
    () => validatePerformanceContract(percentile),
    /percentile must be <= 100/,
  );
  assert.throws(() => parsePerformanceContract("{broken"), /not valid JSON/);
});

test("rejects blocking claims for uncalibrated measurement classes", () => {
  const webRuntime = validContract();
  webRuntime.measurements.web_runtime.status = "blocking";
  assert.throws(
    () => validatePerformanceContract(webRuntime),
    /web_runtime\.status must remain calibration_required/,
  );

  const apiRuntime = validContract();
  apiRuntime.measurements.api_runtime.status = "blocking";
  assert.throws(
    () => validatePerformanceContract(apiRuntime),
    /api_runtime\.status must remain calibration_required/,
  );

  const resources = validContract();
  resources.measurements.api_replica_resources.status = "blocking";
  assert.throws(
    () => validatePerformanceContract(resources),
    /api_replica_resources\.status must remain calibration_required/,
  );
});

test("requires explicit limitations for uncalibrated measurements", () => {
  const contract = validContract();
  contract.measurements.web_runtime.limitations = [];
  assert.throws(
    () => validatePerformanceContract(contract),
    /limitations must contain non-empty strings/,
  );
});

test("fails when a replaced legacy contract still exists", (t) => {
  const root = temporaryDirectory(t);
  mkdirSync(join(root, "ci"));
  writeFileSync(join(root, "ci/budget.json"), "{}\n");
  assert.throws(
    () => assertLegacyContractsAbsent(validContract(), root),
    /Legacy performance contract still exists: ci\/budget.json/,
  );
  rmSync(join(root, "ci/budget.json"));
  assert.doesNotThrow(() => assertLegacyContractsAbsent(validContract(), root));

  symlinkSync("missing.json", join(root, "ci/budget.json"));
  assert.throws(
    () => assertLegacyContractsAbsent(validContract(), root),
    /Legacy performance contract still exists: ci\/budget.json \(symbolic link\)/,
  );
});

test("ties replaced files to explicit absence enforcement", () => {
  const missingAbsence = validContract();
  missingAbsence.authority.replaces.push("policies/perf.json");
  assert.throws(
    () => validatePerformanceContract(missingAbsence),
    /must be enforced by legacy_contracts\.must_not_exist: policies\/perf\.json/,
  );

  const undeclaredAbsence = validContract();
  undeclaredAbsence.legacy_contracts.must_not_exist.push("policies/perf.json");
  assert.throws(
    () => validatePerformanceContract(undeclaredAbsence),
    /must be declared by authority\.replaces: policies\/perf\.json/,
  );

  const fragmentReference = validContract();
  fragmentReference.authority.replaces.push(
    "policies/slo.yaml#/services/web/latency",
  );
  assert.doesNotThrow(() => validatePerformanceContract(fragmentReference));
});

test("fails closed on unsafe legacy paths", () => {
  const contract = validContract();
  contract.legacy_contracts.must_not_exist = ["../outside.json"];
  assert.throws(
    () => validatePerformanceContract(contract),
    /safe repository-relative path/,
  );
});

test("rejects a canonical contract reached through a symlinked parent", (t) => {
  const root = temporaryDirectory(t);
  const outside = temporaryDirectory(t);
  writeFileSync(
    join(outside, "performance.v1.json"),
    JSON.stringify(validContract()),
  );
  symlinkSync(outside, join(root, "redirect"), "dir");

  assert.throws(
    () =>
      loadPerformanceContract({
        contractPath: join(root, "redirect/performance.v1.json"),
        root,
      }),
    /escapes repository root/,
  );
});

test("rejects a symlinked canonical contract", (t) => {
  const root = temporaryDirectory(t);
  const policies = join(root, "policies");
  mkdirSync(policies);
  const outside = join(root, "outside.json");
  writeFileSync(outside, JSON.stringify(validContract()));
  const contractPath = join(policies, "performance.v1.json");
  symlinkSync(outside, contractPath);

  assert.throws(
    () => loadPerformanceContract({ contractPath, root }),
    /must be a regular file/,
  );
});
