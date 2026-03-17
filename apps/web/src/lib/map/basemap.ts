import type { BasemapConfig } from "./config/basemap.current";

export function resolveBasemapStyle(config: BasemapConfig): string {
  switch (config.mode) {
    case "remote-style":
      return config.styleUrl;
    default:
      throw new Error(`Unsupported basemap mode: ${config.mode}`);
  }
}

/**
 * Resolves stable PMTiles aliases to their local runtime endpoints.
 * A bare alias (e.g., 'pmtiles://basemap-hamburg.pmtiles') without any slashes
 * is treated as a local alias and mapped to the basemap directory.
 * Fully qualified PMTiles URLs (e.g., 'pmtiles://tiles.domain.org/basemap.pmtiles')
 * are left unchanged.
 */
export function resolvePmtilesUrl(url: string, origin: string): string {
  if (url.startsWith("pmtiles://")) {
    const target = url.slice("pmtiles://".length);
    // Only bare aliases (without "/") are rewritten
    if (!target.includes("/")) {
      try {
        const normalizedHost = new URL(origin).host;
        return `pmtiles://${normalizedHost}/basemap/${target}`;
      } catch {
        // Fallback for malformed origins
        const fallbackHost = origin.replace(/^https?:\/\//, "");
        return `pmtiles://${fallbackHost}/basemap/${target}`;
      }
    }
  }
  return url;
}
