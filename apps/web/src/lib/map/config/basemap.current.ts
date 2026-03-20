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

const isLocal = import.meta.env.DEV || import.meta.env.MODE === "test";

export const currentBasemap: BasemapConfig = isLocal
  ? {
      mode: "local-sovereign",
      center: [HAMMER_PARK_CENTER.lon, HAMMER_PARK_CENTER.lat], // Hammer Park, Hamm
      zoom: 15,
      minZoom: 10,
      maxZoom: 18,
    }
  : {
      mode: "remote-style",
      styleUrl: "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
      center: [HAMMER_PARK_CENTER.lon, HAMMER_PARK_CENTER.lat], // Hammer Park, Hamm
      zoom: 15,
      minZoom: 10,
      maxZoom: 18,
    };
