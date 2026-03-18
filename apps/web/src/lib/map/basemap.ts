import type { BasemapConfig } from "./config/basemap.current";

function assertNever(x: never): never {
  throw new Error(`Unsupported basemap mode: ${JSON.stringify(x)}`);
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
