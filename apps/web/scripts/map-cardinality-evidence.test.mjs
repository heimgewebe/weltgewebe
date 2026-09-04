import assert from "node:assert/strict";
import test from "node:test";
import {
  MAP_CARDINALITY_BUDGETS,
  expectedMapCardinalityPages,
  buildMapCardinalityEvidence,
  validateMapCardinalitySample,
} from "./map-cardinality-evidence.mjs";

function sample(cardinality, overrides = {}) {
  const budget = MAP_CARDINALITY_BUDGETS[cardinality];
  return {
    cardinality,
    page_size: 1000,
    api_request_count: expectedMapCardinalityPages(cardinality),
    api_response_bytes: Math.min(
      budget.max_api_response_bytes,
      cardinality * 256,
    ),
    readiness_ms: Math.min(budget.readiness_ms, 1000),
    interaction_to_next_paint_ms: Math.min(
      50,
      budget.interaction_to_next_paint_ms,
    ),
    dom_marker_count: cardinality > 1000 ? 0 : 100,
    native_layer_expected: cardinality > 1000,
    ...overrides,
  };
}

test("page counts are fixed to the production cursor page size", () => {
  assert.equal(expectedMapCardinalityPages(1000), 1);
  assert.equal(expectedMapCardinalityPages(10000), 10);
  assert.equal(expectedMapCardinalityPages(100000), 100);
});

test("all three cardinality budgets accept bounded samples", () => {
  for (const cardinality of [1000, 10000, 100000]) {
    assert.equal(
      validateMapCardinalitySample(sample(cardinality)).cardinality,
      cardinality,
    );
  }
});

test("budget violations fail closed", () => {
  assert.throws(
    () => validateMapCardinalitySample(sample(10000, { dom_marker_count: 2 })),
    /DOM marker count/,
  );
  assert.throws(
    () =>
      validateMapCardinalitySample(sample(100000, { api_request_count: 99 })),
    /expected 100 node pages/,
  );
  assert.throws(
    () =>
      validateMapCardinalitySample(
        sample(1000, {
          readiness_ms: MAP_CARDINALITY_BUDGETS[1000].readiness_ms + 1,
        }),
      ),
    /readiness/,
  );
});

test("evidence is exact-revision bound and cardinality complete", () => {
  const evidence = buildMapCardinalityEvidence({
    sourceRevision: "a".repeat(40),
    generatedAt: "2026-09-04T00:00:00Z",
    browser: { name: "chromium", version: "test", headless: true },
    samples: [sample(1000), sample(10000), sample(100000)],
  });
  assert.equal(evidence.verdict, "PASS");
  assert.deepEqual(
    evidence.samples.map((entry) => entry.cardinality),
    [1000, 10000, 100000],
  );
  assert.match(
    evidence.limitations[0],
    /deterministic Playwright HTTP fixture/,
  );
});
