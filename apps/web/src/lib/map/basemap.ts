import { BUILD_VERSION } from "$lib/generated/buildVersion";
import type { BasemapConfig } from "./config/basemap.current";

export const LOCAL_BASEMAP_STYLE_VERSION = "0.4.0";
const LOCAL_BASEMAP_BUILD_VERSION = encodeURIComponent(BUILD_VERSION);

const LOCAL_BASEMAP_STYLE_PATHS = {
  regional: "style.json",
  germany: "style-germany.json",
} as const;

function localBasemapStyleUrl(
  variant: keyof typeof LOCAL_BASEMAP_STYLE_PATHS,
): string {
  const stylePath = LOCAL_BASEMAP_STYLE_PATHS[variant];
  return `/local-basemap/${stylePath}?v=${LOCAL_BASEMAP_STYLE_VERSION}&build=${LOCAL_BASEMAP_BUILD_VERSION}`;
}

export const LOCAL_BASEMAP_STYLE_URL = localBasemapStyleUrl("regional");
export const LOCAL_BASEMAP_GERMANY_STYLE_URL =
  localBasemapStyleUrl("germany");

function assertNever(x: never): never {
  throw new Error(`Unsupported basemap mode: ${JSON.stringify(x)}`);
}

/**
 * Rewrites bare PMTiles aliases (for example pmtiles://basemap-germany.pmtiles)
 * to point to the local Vite dev-server proxy (/local-basemap/).
 * Fully qualified URLs remain unchanged.
 */
export function rewritePmtilesUrl(url: string, origin: string): string {
  if (url.startsWith("pmtiles://")) {
    const remainder = url.slice("pmtiles://".length);
    if (!remainder.includes("/")) {
      return `pmtiles://${origin}/local-basemap/${remainder}`;
    }
  }
  return url;
}

export function resolveBasemapStyle(config: BasemapConfig): string {
  switch (config.mode) {
    case "remote-style":
      if (!config.styleUrl)
        throw new Error("styleUrl required for remote-style");
      return config.styleUrl;
    case "local-sovereign":
      return localBasemapStyleUrl(config.variant ?? "regional");
    default:
      return assertNever(config);
  }
}
