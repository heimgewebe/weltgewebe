export interface WebRuntimeNetworkConditions {
  throttled: boolean;
  latency_ms: number;
  download_kbps: number;
  upload_kbps: number;
  connection_type: string;
}

export interface WebRuntimeProfile {
  viewport: { width: number; height: number };
  network_profile: string;
  network_conditions: WebRuntimeNetworkConditions;
  runs: number;
}

export interface WebRuntimeScenario {
  path: string;
  readiness: {
    required_selectors: string[];
    timeout_ms: number;
  };
  interaction: {
    test_ids: string[];
    expected_test_id: string;
    settle_frames: number;
  };
  metrics: Record<string, { percentile: number; max: number }>;
}

export interface PerformanceContract {
  schema_version: number;
  contract_id: string;
  authority: Record<string, unknown>;
  measurements: {
    web_runtime: {
      status: "calibration_required";
      runner: string;
      artifact_kind: string;
      profiles: Record<string, WebRuntimeProfile>;
      scenarios: { public_map: WebRuntimeScenario };
      limitations: string[];
    };
    [key: string]: unknown;
  };
  legacy_contracts: Record<string, unknown>;
}

export const repositoryRoot: string;
export const defaultPerformanceContractPath: string;
export function loadPerformanceContract(options?: {
  contractPath?: string;
  enforceLegacyAbsence?: boolean;
  root?: string;
}): PerformanceContract;
export function parsePerformanceContract(text: string): PerformanceContract;
export function validatePerformanceContract(
  value: unknown,
): PerformanceContract;
export function assertLegacyContractsAbsent(
  contract: PerformanceContract,
  root?: string,
): void;
