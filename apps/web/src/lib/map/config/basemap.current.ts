// "local-sovereign" mode uses the locally served map style and PMTiles artifact.
// Assets (glyphs/sprites) might still be incomplete, but the runtime pipeline is unblocked.
//
// PUBLIC_BASEMAP_MODE is read via import.meta.env.PUBLIC_BASEMAP_MODE, which is
// exposed by SvelteKit's Vite plugin and inlined into the client bundle at build time.
// When unset, it defaults to undefined, which is then resolved by resolveBasemapMode()
// based on the isLocal context. This allows the bundler to dead-code-eliminate the
// remote (CARTO) branch in local-sovereign builds, which is what the deploy leak-guard
// relies on.

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

// The remote basemap is CARTO Voyager. Only ever reached via an explicit
// remote-style choice; never the silent default for the Heimserver/Edge deploy.
export const REMOTE_STYLE_URL =
  "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json";

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

// Statically inlined to a string literal when PUBLIC_BASEMAP_MODE is set,
// `undefined` when unset. This allows the bundler to dead-code-eliminate the
// remote (CARTO) branch below in local-sovereign builds.
const compileTimeMode: string | undefined =
  typeof import.meta !== "undefined" && import.meta.env
    ? import.meta.env.PUBLIC_BASEMAP_MODE
    : undefined;
const resolvedMode = resolveBasemapMode(compileTimeMode, isLocal);

const baseConfig: BaseBasemapConfig = {
  center: [HAMMER_PARK_CENTER.lon, HAMMER_PARK_CENTER.lat], // Hammer Park, Hamm
  zoom: 15,
  minZoom: 10,
  maxZoom: 18,
};

const localSovereignConfig: LocalSovereignBasemapConfig = {
  ...baseConfig,
  mode: "local-sovereign",
};

// The first comparison is against the compile-time literal so that, in a
// local-sovereign build, the bundler folds it to `true` and eliminates the
// remote branch (and its CARTO URL literal) entirely. The runtime fallback
// branches only survive when the mode is not statically local-sovereign.
export const currentBasemap: BasemapConfig =
  compileTimeMode === "local-sovereign"
    ? localSovereignConfig
    : resolvedMode === "remote-style"
      ? {
          ...baseConfig,
          mode: "remote-style",
          styleUrl: REMOTE_STYLE_URL,
        }
      : localSovereignConfig;
