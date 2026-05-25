// The active basemap mode is decided at build time by
// scripts/generate-basemap-config.js, which reads PUBLIC_BASEMAP_MODE and
// writes $lib/generated/basemapConfig.ts. In a local-sovereign build that
// generated module carries no remote (CARTO) URL, so this module — and the
// whole client bundle — contains no CARTO string literal at all. The remote
// URL only ever exists in the generated module of an explicit remote-style
// build. The deploy leak-guard (scripts/weltgewebe-up) enforces this.

import { BUILD_BASEMAP_CONFIG } from "../../generated/basemapConfig";

export type BasemapMode = "remote-style" | "local-sovereign";

// Mirrors basemap-mode.policy.json (canonical source for the build-time generator).
// Keep in sync manually until the generator emits a TS policy artifact.
// TODO: generate this from basemap-mode.policy.json to eliminate drift risk.
const BASEMAP_MODE_POLICY = {
  defaultMode: "local-sovereign",
  allowedModes: ["local-sovereign", "remote-style"],
} as const satisfies {
  defaultMode: BasemapMode;
  allowedModes: readonly BasemapMode[];
};

type BaseBasemapConfig = {
  center: [number, number];
  zoom: number;
  minZoom?: number;
  maxZoom?: number;
  pitch?: number;
  bearing?: number;
};

export type RemoteStyleBasemapConfig = BaseBasemapConfig & {
  mode: "remote-style";
  styleUrl: string;
};

export type LocalSovereignBasemapConfig = BaseBasemapConfig & {
  mode: "local-sovereign";
  styleUrl?: never;
};

export type BasemapConfig =
  | RemoteStyleBasemapConfig
  | LocalSovereignBasemapConfig;

export const HAMMER_PARK_CENTER = {
  lat: 53.5585,
  lon: 10.058,
};

// Context-aware basemap mode resolver. Maps a raw env mode string to a
// concrete basemap mode, with context-specific fallback behavior.
//
// Allowed modes are defined in basemap-mode.policy.json. When envMode is
// explicitly set to an allowed value, it is always honored regardless of context.
// When envMode is absent or invalid, the fallback depends on context:
//
// isLocalContext: true  → fall back to "local-sovereign" (local dev default)
// isLocalContext: false → fall back to "remote-style" (production default)
//
// Note: The build-time generator (scripts/generate-basemap-config.js) is stricter
// — it always uses basemap-mode.policy.json's defaultMode ("local-sovereign") for
// unset PUBLIC_BASEMAP_MODE. This resolver is a runtime fallback for test/runtime
// scenarios where context matters.
export function resolveBasemapMode(
  envMode: string | undefined,
  isLocalContext: boolean,
): BasemapMode {
  if (BASEMAP_MODE_POLICY.allowedModes.includes(envMode as BasemapMode)) {
    return envMode as BasemapMode;
  }
  return isLocalContext ? "local-sovereign" : "remote-style";
}

const baseConfig: BaseBasemapConfig = {
  center: [HAMMER_PARK_CENTER.lon, HAMMER_PARK_CENTER.lat], // Hammer Park, Hamm
  zoom: 15,
  minZoom: 10,
  maxZoom: 18,
};

// Assembled from the generated build-time config. The remote branch reads the
// URL from BUILD_BASEMAP_CONFIG (a property access, not a string literal), so
// no CARTO URL is hardcoded here. In a local-sovereign build the generated
// config has mode "local-sovereign" and no styleUrl.
export const currentBasemap: BasemapConfig =
  BUILD_BASEMAP_CONFIG.mode === "remote-style"
    ? {
        ...baseConfig,
        mode: "remote-style",
        styleUrl: BUILD_BASEMAP_CONFIG.styleUrl,
      }
    : {
        ...baseConfig,
        mode: "local-sovereign",
      };
