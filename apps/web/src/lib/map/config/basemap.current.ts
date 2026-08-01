// The active basemap mode and sovereign variant are decided at build time by
// scripts/generate-basemap-config.js. A local-sovereign generated module carries
// no remote (CARTO) URL. The Germany variant remains opt-in until its real
// artifact and production proof are complete.

import {
  BUILD_BASEMAP_CONFIG,
  type LocalBasemapVariant,
} from "../../generated/basemapConfig";
import {
  BASEMAP_MODE_POLICY,
  type BasemapMode,
} from "../../generated/basemapModePolicy";
import { MAP_MIN_ZOOM } from "../markerScale";

export type { BasemapMode, LocalBasemapVariant };

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
  variant: LocalBasemapVariant;
  styleUrl?: never;
};

export type BasemapConfig =
  | RemoteStyleBasemapConfig
  | LocalSovereignBasemapConfig;

export const HAMMER_PARK_CENTER = {
  lat: 53.5585,
  lon: 10.058,
};

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
  center: [HAMMER_PARK_CENTER.lon, HAMMER_PARK_CENTER.lat],
  zoom: 15,
  minZoom: MAP_MIN_ZOOM,
  maxZoom: 18,
};

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
        variant: BUILD_BASEMAP_CONFIG.variant,
      };
