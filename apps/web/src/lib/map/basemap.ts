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
      throw new Error(
        "Basemap mode 'local-sovereign' is prepared but not yet supported: missing local style asset integration",
      );
    default:
      return assertNever(config);
  }
}
