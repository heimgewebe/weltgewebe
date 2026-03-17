import type { BasemapConfig } from "./config/basemap.current";

export function resolveBasemapStyle(config: BasemapConfig): string {
  switch (config.mode) {
    case "remote-style":
      return config.styleUrl;
    default:
      throw new Error(`Unsupported basemap mode: ${config.mode}`);
  }
}
