import type { BasemapConfig } from "./config/basemap.current";

function assertNever(x: never): never {
  throw new Error(`Unsupported basemap mode: ${JSON.stringify(x)}`);
}

/**
 * Rewrites bare PMTiles aliases (e.g. pmtiles://basemap-hamburg.pmtiles)
 * to point to the local Vite dev-server proxy (/local-basemap/).
 * Fully qualified URLs (containing a host/path) remain unchanged.
 *
 * Note: Intended exclusively for the prepared local dev flow.
 * The existence of this rewrite is not evidence of an active end-to-end supported mode.
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
      return "/local-basemap/style.json";
    default:
      return assertNever(config);
  }
}
