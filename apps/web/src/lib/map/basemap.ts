import type { BasemapConfig } from "./config/basemap.current";

export function resolveBasemapStyle(config: BasemapConfig): string {
  switch (config.mode) {
    case "remote-style":
      if (!config.styleUrl)
        throw new Error("styleUrl required for remote-style");
      return config.styleUrl;
    case "local-sovereign":
      return "/local-style/style.json";
    default:
      throw new Error(`Unsupported basemap mode: ${config.mode}`);
  }
}
