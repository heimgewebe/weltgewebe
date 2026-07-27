import type { PerformanceContract } from "./performance-contract.mjs";

export interface WebRuntimeSample {
  run_index: number;
  largest_contentful_paint_ms: number;
  interaction_to_next_paint_ms: number;
  usable_map_ms: number;
  interaction_metric_source:
    | "event-timing-and-next-paint-fallback"
    | "next-paint-fallback";
  observed_interactions: number;
  observed_event_entries: number;
  observed_fallback_samples: number;
  observed_fallback_test_ids: string[];
  observed_event_timing_test_ids: string[];
  lcp_entry_count: number;
}

export interface WebRuntimeEvidence {
  schema_version: 1;
  kind: "weltgewebe-web-runtime-evidence";
  contract_id: string;
  contract_status: "calibration_required";
  source_revision: string;
  generated_at: string;
  runner: string;
  browser: { name: string; version: string; headless: boolean };
  scenario: Record<string, unknown>;
  profiles: Record<string, unknown>;
  limitations: string[];
  validity: {
    establishes: string[];
    does_not_establish: string[];
  };
}

export function resolveExactSourceRevision(
  environment?: Record<string, string | undefined>,
): string;
export function buildExactRevisionAliases(
  environment?: Record<string, string | undefined>,
): Record<string, string>;
export function assertExactRevisionEnvironment(
  environment?: Record<string, string | undefined>,
): string;
export function assertExactGitCheckout(options: {
  revision: string;
  root?: string;
}): string;
export function buildWebRuntimeEvidence(options: {
  contract: PerformanceContract;
  sourceRevision: string;
  generatedAt: string;
  browser: { name: string; version: string; headless: boolean };
  samplesByProfile: Record<string, WebRuntimeSample[]>;
}): WebRuntimeEvidence;
export function writeWebRuntimeEvidence(
  evidence: WebRuntimeEvidence,
  outputDirectory?: string,
): string;
export function validateWebRuntimeEvidence(
  evidence: unknown,
  options?: { contract?: PerformanceContract; expectedRevision?: string },
): WebRuntimeEvidence;
export function readAndValidateWebRuntimeEvidence(
  path: string,
  expectedRevision: string,
): WebRuntimeEvidence;
export function defaultEvidencePath(revision: string): string;
export function nearestRankPercentile(
  values: number[],
  percentile: number,
): number;
