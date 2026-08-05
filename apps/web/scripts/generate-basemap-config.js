import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import {
  assertVercelLocalBasemapDelivery,
  resolveBasemapModeForBuild,
} from "./basemap-mode-resolve.mjs";

// Build-time basemap configuration generator.
//
// PUBLIC_BASEMAP_MODE selects the external-vs-sovereign policy. For a
// local-sovereign build, PUBLIC_BASEMAP_VARIANT selects which independently
// published style/PMTiles contract is used:
//
//   regional (default) -> style.json (+ style-dark.json), Hamburg + SH aliases
//   germany            -> style-germany.json (+ style-germany-dark.json)
//
// When PUBLIC_BASEMAP_MODE is unset/empty and VERCEL=1, the generator selects
// remote-style because Vercel does not ship the local basemap middleware or
// static local style/PMTiles files. Outside Vercel the policy default remains.
//
// The public build identity also binds the generated frontend to the exact
// source commit and style bytes (light + dark) used during its build.

const REMOTE_STYLE_URL =
  "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json";
const REMOTE_DARK_STYLE_URL =
  "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";
const LOCAL_BASEMAP_VARIANTS = ["regional", "germany"];
const DEFAULT_LOCAL_BASEMAP_VARIANT = "regional";
const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(scriptDir, "..");
const repoRoot = path.resolve(webRoot, "..", "..");

const policyPath = path.join(webRoot, "basemap-mode.policy.json");
const policy = JSON.parse(fs.readFileSync(policyPath, "utf8"));

const validModes = new Set(["local-sovereign", "remote-style"]);
if (!validModes.has(policy.defaultMode)) {
  console.error(
    `ERROR: Invalid basemap-mode.policy.json: defaultMode='${policy.defaultMode}' is not in validModes.`,
  );
  process.exit(1);
}
if (
  !Array.isArray(policy.allowedModes) ||
  policy.allowedModes.some((mode) => !validModes.has(mode)) ||
  !policy.allowedModes.includes(policy.defaultMode)
) {
  console.error(
    "ERROR: Invalid basemap-mode.policy.json: allowedModes must be an array of valid modes and must include defaultMode.",
  );
  process.exit(1);
}

const rawMode = process.env.PUBLIC_BASEMAP_MODE;
const isVercel = process.env.VERCEL === "1";
const modeResolution = resolveBasemapModeForBuild({
  rawMode,
  defaultMode: policy.defaultMode,
  allowedModes: policy.allowedModes,
  isVercel,
});
if (!modeResolution.ok) {
  console.error(`ERROR: ${modeResolution.error}`);
  process.exit(1);
}
const mode = modeResolution.mode;

const rawVariant = process.env.PUBLIC_BASEMAP_VARIANT;
let variant = DEFAULT_LOCAL_BASEMAP_VARIANT;
if (rawVariant !== undefined && rawVariant !== "") {
  if (!LOCAL_BASEMAP_VARIANTS.includes(rawVariant)) {
    console.error(`ERROR: Invalid PUBLIC_BASEMAP_VARIANT='${rawVariant}'.`);
    console.error(
      `       Allowed values: ${LOCAL_BASEMAP_VARIANTS.join(", ")} (or unset for default: ${DEFAULT_LOCAL_BASEMAP_VARIANT}).`,
    );
    process.exit(1);
  }
  variant = rawVariant;
}
if (mode === "remote-style" && rawVariant) {
  console.error(
    "ERROR: PUBLIC_BASEMAP_VARIANT is only valid with PUBLIC_BASEMAP_MODE=local-sovereign.",
  );
  process.exit(1);
}

function localStyleFileNames(selectedVariant) {
  if (selectedVariant === "germany") {
    return {
      light: "style-germany.json",
      dark: "style-germany-dark.json",
    };
  }
  return {
    light: "style.json",
    dark: "style-dark.json",
  };
}

// Build/artifact contract: never let a Vercel build claim local-sovereign
// without delivered static style files (light + dark; Vercel has no middleware).
if (mode === "local-sovereign") {
  const files = localStyleFileNames(variant);
  for (const styleFileName of [files.light, files.dark]) {
    const deliveredStylePath = path.join(
      webRoot,
      "static",
      "local-basemap",
      styleFileName,
    );
    const delivery = assertVercelLocalBasemapDelivery({
      mode,
      isVercel,
      styleDelivered: fs.existsSync(deliveredStylePath),
      stylePath: `/local-basemap/${styleFileName}`,
    });
    if (!delivery.ok) {
      console.error(`ERROR: ${delivery.error}`);
      process.exit(1);
    }
  }
}

const requireCanonicalCommit = (value, source) => {
  if (!/^[0-9a-f]{40}$/.test(value)) {
    throw new Error(`${source} must be a full lowercase Git SHA`);
  }
  return value;
};

const resolveSourceCommit = () => {
  const explicitCommit = process.env.PUBLIC_SOURCE_COMMIT?.trim();
  if (explicitCommit) {
    return requireCanonicalCommit(explicitCommit, "PUBLIC_SOURCE_COMMIT");
  }

  const buildCommit = process.env.GIT_COMMIT_SHA?.trim();
  if (buildCommit) {
    return requireCanonicalCommit(buildCommit, "GIT_COMMIT_SHA");
  }

  const commit = execFileSync("git", ["-C", repoRoot, "rev-parse", "HEAD"], {
    encoding: "utf8",
  }).trim();
  return requireCanonicalCommit(commit, "resolved source commit");
};

const sha256File = (filePath) =>
  crypto.createHash("sha256").update(fs.readFileSync(filePath)).digest("hex");

const header = `// AUTO-GENERATED by scripts/generate-basemap-config.js — do not edit.
// In local-sovereign mode this module contains no remote (CARTO) URL.

export type LocalBasemapVariant = "regional" | "germany";

export type BuildBasemapConfig =
  | { mode: "local-sovereign"; variant: LocalBasemapVariant }
  | { mode: "remote-style"; styleUrl: string; darkStyleUrl: string };
`;

const body =
  mode === "remote-style"
    ? `
export const BUILD_BASEMAP_CONFIG: BuildBasemapConfig = {
  mode: "remote-style",
  styleUrl: "${REMOTE_STYLE_URL}",
  darkStyleUrl: "${REMOTE_DARK_STYLE_URL}",
};
`
    : `
export const BUILD_BASEMAP_CONFIG: BuildBasemapConfig = {
  mode: "local-sovereign",
  variant: "${variant}",
};
`;

const outDir = path.join(webRoot, "src/lib/generated");
fs.mkdirSync(outDir, { recursive: true });
const outFile = path.join(outDir, "basemapConfig.ts");
fs.writeFileSync(outFile, header + body, "utf8");
console.log(
  `Generated basemap config: mode=${mode}${mode === "local-sovereign" ? ` variant=${variant}` : ""} at ${outFile}`,
);

const policyHeader = `// AUTO-GENERATED by scripts/generate-basemap-config.js — do not edit.
// Basemap mode policy derived from basemap-mode.policy.json.

export type BasemapMode = "remote-style" | "local-sovereign";

export const BASEMAP_MODE_ALLOWED_MODES = ${JSON.stringify(policy.allowedModes)} as const satisfies readonly BasemapMode[];

export const BASEMAP_MODE_DEFAULT = "${policy.defaultMode}" as const satisfies BasemapMode;

export const BASEMAP_MODE_POLICY = {
  defaultMode: BASEMAP_MODE_DEFAULT,
  allowedModes: BASEMAP_MODE_ALLOWED_MODES,
} as const;
`;

const policyOutFile = path.join(outDir, "basemapModePolicy.ts");
fs.writeFileSync(policyOutFile, policyHeader, "utf8");
console.log(`Generated basemap mode policy: ${policyOutFile}`);

const staticIdentityDir = path.join(webRoot, "static", "_app");
fs.mkdirSync(staticIdentityDir, { recursive: true });
const sourceCommit = resolveSourceCommit();
const buildIdentity =
  mode === "local-sovereign"
    ? (() => {
        const files = localStyleFileNames(variant);
        const lightPath = path.join(repoRoot, "map-style", files.light);
        const darkPath = path.join(repoRoot, "map-style", files.dark);
        if (!fs.existsSync(lightPath)) {
          throw new Error(`Missing basemap style file: ${lightPath}`);
        }
        if (!fs.existsSync(darkPath)) {
          throw new Error(`Missing basemap dark style file: ${darkPath}`);
        }
        return {
          schema_version: 1,
          mode,
          variant,
          style_path: `/local-basemap/${files.light}`,
          style_dark_path: `/local-basemap/${files.dark}`,
          source_commit: sourceCommit,
          style_sha256: sha256File(lightPath),
          style_dark_sha256: sha256File(darkPath),
        };
      })()
    : {
        schema_version: 1,
        mode,
        style_url: REMOTE_STYLE_URL,
        style_dark_url: REMOTE_DARK_STYLE_URL,
        source_commit: sourceCommit,
      };
const buildIdentityPath = path.join(staticIdentityDir, "basemap-build.json");
fs.writeFileSync(
  buildIdentityPath,
  `${JSON.stringify(buildIdentity, null, 2)}\n`,
  "utf8",
);
console.log(`Generated basemap build identity: ${buildIdentityPath}`);
