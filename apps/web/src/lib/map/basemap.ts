import type { BasemapConfig } from "./config/basemap.current";

export function resolveBasemapStyle(config: BasemapConfig): string {
  return config.styleUrl;
}
