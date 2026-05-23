// "local-sovereign" mode uses the locally served map style and PMTiles artifact.
// Assets (glyphs/sprites) might still be incomplete, but the runtime pipeline is unblocked.
//
// PUBLIC_BASEMAP_MODE must be read via SvelteKit's $env module so the value is
// inlined into the client bundle at build time. `import.meta.env.PUBLIC_*` does
// NOT work here: Vite only exposes vars matching its envPrefix (default VITE_),
// so PUBLIC_-prefixed vars are always `undefined` there, silently leaking the
// remote CARTO default into every build.
//
// We read it via a namespace import of $env/static/public (not a named import):
// a named `import { PUBLIC_BASEMAP_MODE }` hard-fails the build whenever the
// variable is unset (CI, local dev, vitest), which would break the documented
// "unset is a valid default" contract. The namespace form yields `undefined`
// when unset while still being statically inlined to a string literal when set —
// which lets the bundler dead-code-eliminate the remote (CARTO) branch below in
// local-sovereign builds. That elimination is what the deploy leak-guard relies on.
import * as publicEnv from "$env/static/public";

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
// `undefined` when unset (see import note above). The cast is required because
// the generated $env/static/public type only declares variables present at
// `svelte-kit sync` time; it is erased at build, so folding is unaffected.
const compileTimeMode: string | undefined = (
  publicEnv as Record<string, string | undefined>
).PUBLIC_BASEMAP_MODE;
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
