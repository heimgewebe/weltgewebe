import { BUILD_VERSION } from "$lib/generated/buildVersion";
import { LOCAL_BASEMAP_STYLE_VERSION } from "./basemapStyleVersion";
import type { BasemapConfig } from "./config/basemap.current";
import { normalizeColorScheme, type ColorScheme } from "./colorScheme";

export type { ColorScheme };

export { LOCAL_BASEMAP_STYLE_VERSION } from "./basemapStyleVersion";
const LOCAL_BASEMAP_BUILD_VERSION = encodeURIComponent(BUILD_VERSION);

export const REMOTE_VOYAGER_STYLE_URL =
  "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json";
export const REMOTE_DARK_MATTER_STYLE_URL =
  "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

function localBasemapStyleUrl(fileName: string): string {
  return `/local-basemap/${fileName}?v=${LOCAL_BASEMAP_STYLE_VERSION}&build=${LOCAL_BASEMAP_BUILD_VERSION}`;
}

export const LOCAL_BASEMAP_STYLE_URL = localBasemapStyleUrl("style.json");
export const LOCAL_BASEMAP_STYLE_DARK_URL =
  localBasemapStyleUrl("style-dark.json");
export const LOCAL_BASEMAP_GERMANY_STYLE_URL =
  localBasemapStyleUrl("style-germany.json");
export const LOCAL_BASEMAP_GERMANY_STYLE_DARK_URL = localBasemapStyleUrl(
  "style-germany-dark.json",
);

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

function resolveLocalSovereignStyle(
  variant: "regional" | "germany" | undefined,
  scheme: ColorScheme,
): string {
  if (variant === "regional") {
    return scheme === "dark"
      ? LOCAL_BASEMAP_STYLE_DARK_URL
      : LOCAL_BASEMAP_STYLE_URL;
  }
  // Germany is the sovereign default. Undefined is retained only for legacy
  // callers and must never silently downgrade nationwide coverage.
  return scheme === "dark"
    ? LOCAL_BASEMAP_GERMANY_STYLE_DARK_URL
    : LOCAL_BASEMAP_GERMANY_STYLE_URL;
}

function resolveRemoteStyle(
  config: Extract<BasemapConfig, { mode: "remote-style" }>,
  scheme: ColorScheme,
): string {
  if (!config.styleUrl) {
    throw new Error("styleUrl required for remote-style");
  }
  if (scheme === "dark") {
    if (config.darkStyleUrl) return config.darkStyleUrl;
    // Known Voyager light default maps to Dark Matter; other explicit light
    // URLs remain on their explicitly configured host.
    if (
      config.styleUrl === REMOTE_VOYAGER_STYLE_URL ||
      config.styleUrl.includes("/voyager-gl-style/")
    ) {
      return REMOTE_DARK_MATTER_STYLE_URL;
    }
    // Custom remote light URL without darkStyleUrl: do not invent a second host.
    return config.styleUrl;
  }
  return config.styleUrl;
}

/**
 * Resolve the basemap style URL for the active mode and color scheme.
 *
 * local-sovereign always stays on same-origin `/local-basemap/*` paths
 * (no remote style host). remote-style uses Voyager/Dark Matter or the
 * explicit URLs carried on the config.
 */
export function resolveBasemapStyle(
  config: BasemapConfig,
  scheme: ColorScheme | string = "light",
): string {
  const resolvedScheme = normalizeColorScheme(scheme);
  switch (config.mode) {
    case "remote-style":
      return resolveRemoteStyle(config, resolvedScheme);
    case "local-sovereign":
      return resolveLocalSovereignStyle(config.variant, resolvedScheme);
    default:
      return assertNever(config);
  }
}
