import type { BasemapConfig } from "./config/basemap.current";

export function resolveBasemapStyle(config: BasemapConfig): string {
  switch (config.mode) {
    case "remote-style":
      if (!config.styleUrl)
        throw new Error("styleUrl required for remote-style");
      return config.styleUrl;
    case "local-sovereign":
      throw new Error(
        "Basemap mode 'local-sovereign' is prepared but not yet supported: missing local style asset integration",
      );
    default:
      throw new Error(`Unsupported basemap mode: ${(config as any).mode}`);
  }
}
