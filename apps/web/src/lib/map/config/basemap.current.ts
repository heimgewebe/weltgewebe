// The active basemap mode is decided at build time by
// scripts/generate-basemap-config.js, which reads PUBLIC_BASEMAP_MODE and
// writes $lib/generated/basemapConfig.ts. In a local-sovereign build that
// generated module carries no remote (CARTO) URL, so this module — and the
// whole client bundle — contains no CARTO string literal at all. The remote
// URL only ever exists in the generated module of an explicit remote-style
// build. The deploy leak-guard (scripts/weltgewebe-up) enforces this.

import { BUILD_BASEMAP_CONFIG } from "../../generated/basemapConfig";
import basemapModePolicy from "../../../../basemap-mode.policy.json";

export type BasemapMode = "remote-style" | "local-sovereign";

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

// Pure resolution policy. Documents how a raw env mode string maps to a
// concrete basemap mode. The basemap mode policy (allowed modes, default) is
// defined in basemap-mode.policy.json and enforced by the build-time
// generator. This resolver applies the same policy for consistency.
//
// Note: The build-time generator is stricter — it always uses the policy
// default for unset PUBLIC_BASEMAP_MODE. This resolver is kept as the
// independently tested reference for the resolution contract.
export function resolveBasemapMode(envMode: string | undefined): BasemapMode {
  if (basemapModePolicy.allowedModes.includes(envMode || "")) {
    return envMode as BasemapMode;
  }
  return basemapModePolicy.defaultMode as BasemapMode;
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
