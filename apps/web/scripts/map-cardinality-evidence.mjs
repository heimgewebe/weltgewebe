import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

export const MAP_CARDINALITY_PAGE_SIZE = 1000;

export const MAP_CARDINALITY_BUDGETS = Object.freeze({
  1000: Object.freeze({
    readiness_ms: 5000,
    interaction_to_next_paint_ms: 200,
    max_dom_markers: 250,
    max_api_response_bytes: 1_000_000,
  }),
  10000: Object.freeze({
    readiness_ms: 9000,
    interaction_to_next_paint_ms: 200,
    max_dom_markers: 1,
    max_api_response_bytes: 10_000_000,
  }),
  100000: Object.freeze({
    readiness_ms: 30000,
    interaction_to_next_paint_ms: 250,
    max_dom_markers: 1,
    max_api_response_bytes: 100_000_000,
  }),
});

function finite(value, label) {
  if (!Number.isFinite(value) || value < 0) {
    throw new Error(`${label} must be a finite number >= 0`);
  }
  return value;
}

function integer(value, label, minimum = 0) {
  if (!Number.isInteger(value) || value < minimum) {
    throw new Error(`${label} must be an integer >= ${minimum}`);
  }
  return value;
}

export function expectedMapCardinalityPages(cardinality) {
  integer(cardinality, "cardinality", 1);
  return Math.ceil(cardinality / MAP_CARDINALITY_PAGE_SIZE);
}

export function validateMapCardinalitySample(sample) {
  if (!sample || typeof sample !== "object" || Array.isArray(sample)) {
    throw new Error("sample must be an object");
  }
  const cardinality = integer(sample.cardinality, "sample.cardinality", 1);
  const budget = MAP_CARDINALITY_BUDGETS[cardinality];
  if (!budget) throw new Error(`unsupported cardinality ${cardinality}`);

  integer(sample.api_request_count, "sample.api_request_count", 1);
  integer(sample.api_response_bytes, "sample.api_response_bytes", 1);
  integer(sample.dom_marker_count, "sample.dom_marker_count", 0);
  integer(sample.page_size, "sample.page_size", 1);
  finite(sample.readiness_ms, "sample.readiness_ms");
  finite(
    sample.interaction_to_next_paint_ms,
    "sample.interaction_to_next_paint_ms",
  );
  if (sample.page_size !== MAP_CARDINALITY_PAGE_SIZE) {
    throw new Error(
      `page size ${sample.page_size} does not match ${MAP_CARDINALITY_PAGE_SIZE}`,
    );
  }
  const expectedPages = expectedMapCardinalityPages(cardinality);
  if (sample.api_request_count !== expectedPages) {
    throw new Error(
      `cardinality ${cardinality}: expected ${expectedPages} node pages, observed ${sample.api_request_count}`,
    );
  }
  if (sample.readiness_ms > budget.readiness_ms) {
    throw new Error(
      `cardinality ${cardinality}: readiness ${sample.readiness_ms}ms exceeds ${budget.readiness_ms}ms`,
    );
  }
  if (
    sample.interaction_to_next_paint_ms > budget.interaction_to_next_paint_ms
  ) {
    throw new Error(
      `cardinality ${cardinality}: interaction ${sample.interaction_to_next_paint_ms}ms exceeds ${budget.interaction_to_next_paint_ms}ms`,
    );
  }
  if (sample.dom_marker_count > budget.max_dom_markers) {
    throw new Error(
      `cardinality ${cardinality}: DOM marker count ${sample.dom_marker_count} exceeds ${budget.max_dom_markers}`,
    );
  }
  if (sample.api_response_bytes > budget.max_api_response_bytes) {
    throw new Error(
      `cardinality ${cardinality}: API response bytes ${sample.api_response_bytes} exceeds ${budget.max_api_response_bytes}`,
    );
  }
  const nativeExpected = cardinality > MAP_CARDINALITY_PAGE_SIZE;
  if (sample.native_layer_expected !== nativeExpected) {
    throw new Error(
      `cardinality ${cardinality}: native layer expectation is inconsistent`,
    );
  }
  return { cardinality, budget };
}

export function buildMapCardinalityEvidence({
  sourceRevision,
  browser,
  generatedAt,
  samples,
}) {
  if (
    typeof sourceRevision !== "string" ||
    !/^[0-9a-f]{40}$/.test(sourceRevision)
  ) {
    throw new Error("sourceRevision must be a 40-character Git SHA");
  }
  if (!Array.isArray(samples) || samples.length !== 3) {
    throw new Error("samples must contain exactly the 1k/10k/100k scenarios");
  }
  const seen = samples.map(
    (sample) => validateMapCardinalitySample(sample).cardinality,
  );
  if (seen.join(",") !== "1000,10000,100000") {
    throw new Error(`unexpected cardinality sequence: ${seen.join(",")}`);
  }
  return {
    schema_version: 1,
    kind: "commonthing_map_cardinality_browser_evidence",
    source_revision: sourceRevision,
    generated_at: generatedAt,
    browser,
    page_size: MAP_CARDINALITY_PAGE_SIZE,
    budgets: MAP_CARDINALITY_BUDGETS,
    samples,
    verdict: "PASS",
    limitations: [
      "Node payloads are served by a deterministic Playwright HTTP fixture so this proof isolates browser pagination and rendering from backend/database capacity.",
      "Backend and PostgreSQL scale remain separate evidence lanes; this proof does not claim production network latency or database throughput.",
      "Timing budgets are regression guards on the pinned CI runner class, not user-facing service-level objectives.",
    ],
  };
}

export function writeMapCardinalityEvidence(evidence, outputPath = null) {
  const destination =
    outputPath ??
    resolve(
      process.cwd(),
      "../../build/proofs/web-runtime/map-cardinality.json",
    );
  mkdirSync(resolve(destination, ".."), { recursive: true });
  writeFileSync(destination, `${JSON.stringify(evidence, null, 2)}\n`, "utf8");
  return destination;
}
