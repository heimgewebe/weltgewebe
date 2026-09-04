import assert from "node:assert/strict";
import test from "node:test";
import {
  MAP_CARDINALITY_BUDGETS,
  expectedMapCardinalityItems,
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
      expectedMapCardinalityItems(cardinality) * 256,
    ),
    loaded_item_count: expectedMapCardinalityItems(cardinality),
    truncated_by_client_limit: cardinality > 10_000,
    source_has_more_after_last_client_page: cardinality > 10_000,
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

test("page and item counts follow the production client safety ceiling", () => {
  assert.equal(expectedMapCardinalityPages(1000), 1);
  assert.equal(expectedMapCardinalityPages(10000), 10);
  assert.equal(expectedMapCardinalityPages(100000), 10);
  assert.equal(expectedMapCardinalityItems(1000), 1000);
  assert.equal(expectedMapCardinalityItems(10000), 10000);
  assert.equal(expectedMapCardinalityItems(100000), 10000);
});

test("all three source-cardinality budgets accept bounded browser samples", () => {
  for (const cardinality of [1000, 10000, 100000]) {
    assert.equal(
      validateMapCardinalitySample(sample(cardinality)).cardinality,
      cardinality,
    );
  }
});

test("budget and client-limit violations fail closed", () => {
  assert.throws(
    () => validateMapCardinalitySample(sample(10000, { dom_marker_count: 2 })),
    /DOM marker count/,
  );
  assert.throws(
    () =>
      validateMapCardinalitySample(sample(100000, { api_request_count: 9 })),
    /expected 10 consumed node pages/,
  );
  assert.throws(
    () =>
      validateMapCardinalitySample(
        sample(100000, { truncated_by_client_limit: false }),
      ),
    /client truncation expectation/,
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

test("evidence is exact-revision bound and distinguishes source from browser cardinality", () => {
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
  assert.deepEqual(evidence.client_limits, { max_pages: 10, max_items: 10000 });
  assert.match(
    evidence.limitations[0],
    /deterministic Playwright HTTP fixture/,
  );
  assert.match(evidence.limitations[1], /100,000-item source dataset/);
});
