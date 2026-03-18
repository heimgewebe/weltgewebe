import type { BasemapConfig } from "./config/basemap.current";

function assertNever(x: never): never {
  throw new Error(`Unsupported basemap mode: ${JSON.stringify(x)}`);
}

/**
 * Rewrites bare PMTiles aliases (e.g. pmtiles://basemap-hamburg.pmtiles)
 * to point to the local Vite dev-server proxy (/local-basemap/).
 * Fully qualified URLs (containing a host/path) remain unchanged.
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
      // Dev infrastructure exists, but real local artifact proof is missing,
      // therefore mode stays blocked.
      throw new Error(
        "Basemap mode 'local-sovereign' is prepared but not yet enabled: a real local .pmtiles artifact is required.",
      );
    default:
      return assertNever(config);
  }
}
