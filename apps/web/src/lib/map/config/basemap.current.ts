// "local-sovereign" mode uses the locally served map style and PMTiles artifact.
// Assets (glyphs/sprites) might still be incomplete, but the runtime pipeline is unblocked.
export type BasemapMode = "remote-style" | "local-sovereign";

type BaseBasemapConfig = {
  center: [number, number];
  zoom: number;
  minZoom?: number;
  maxZoom?: number;
  pitch?: number;
  bearing?: number;
};

export type RemoteStyleBasemapConfig = BaseBasemapConfig & {
  mode: "remote-style";
  styleUrl: string;
};

export type LocalSovereignBasemapConfig = BaseBasemapConfig & {
  mode: "local-sovereign";
  styleUrl?: never;
};

export type BasemapConfig =
  | RemoteStyleBasemapConfig
  | LocalSovereignBasemapConfig;

export const HAMMER_PARK_CENTER = {
  lat: 53.5585,
  lon: 10.058,
};

// Safely access env vars in test context
const isLocal =
  typeof import.meta !== "undefined" && import.meta.env
    ? import.meta.env.DEV || import.meta.env.MODE === "test"
    : false;

// Allow explicitly overriding the basemap mode for production deployments (like Caddyfile.heim)
export function resolveBasemapMode(
  envMode: string | undefined,
  isLocalContext: boolean,
): BasemapMode {
  if (envMode === "local-sovereign" || envMode === "remote-style") {
    return envMode;
  }
  return isLocalContext ? "local-sovereign" : "remote-style";
}

const envMode =
  typeof import.meta !== "undefined" && import.meta.env
    ? import.meta.env.PUBLIC_BASEMAP_MODE
    : undefined;
const resolvedMode = resolveBasemapMode(envMode, isLocal);

const baseConfig: BaseBasemapConfig = {
  center: [HAMMER_PARK_CENTER.lon, HAMMER_PARK_CENTER.lat], // Hammer Park, Hamm
  zoom: 15,
  minZoom: 10,
  maxZoom: 18,
};

export const currentBasemap: BasemapConfig =
  resolvedMode === "local-sovereign"
    ? {
        ...baseConfig,
        mode: "local-sovereign",
      }
    : {
        ...baseConfig,
        mode: "remote-style",
        styleUrl:
          "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
      };
