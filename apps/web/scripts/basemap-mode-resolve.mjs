/**
 * Pure basemap mode selection for the build-time generator.
 *
 * Explicit PUBLIC_BASEMAP_MODE always wins when non-empty.
 * Only when unset/empty AND the build runs on Vercel (VERCEL=1) do we
 * choose remote-style, because Vercel does not ship the local basemap
 * middleware or static local style/PMTiles artifacts.
 * Outside Vercel the policy default (local-sovereign) remains.
 */

/**
 * @param {{
 *   rawMode: string | undefined | null,
 *   defaultMode: string,
 *   allowedModes: readonly string[],
 *   isVercel: boolean,
 * }} input
 * @returns {{ ok: true, mode: string } | { ok: false, error: string }}
 */
export function resolveBasemapModeForBuild(input) {
  const rawMode = input.rawMode;
  const allowed = input.allowedModes;
  if (rawMode !== undefined && rawMode !== null && rawMode !== "") {
    if (!allowed.includes(rawMode)) {
      return {
        ok: false,
        error: `Invalid PUBLIC_BASEMAP_MODE='${rawMode}'. Allowed values: ${allowed.join(", ")} (or unset for default: ${input.defaultMode}).`,
      };
    }
    return { ok: true, mode: rawMode };
  }
  if (input.isVercel) {
    return { ok: true, mode: "remote-style" };
  }
  return { ok: true, mode: input.defaultMode };
}

/**
 * Fail-closed artifact contract for Vercel: local-sovereign is only valid
 * when the local style file is present under apps/web/static/local-basemap/.
 * That directory is not part of the normal Git tree and is not shipped by
 * the Vite middleware path used in local dev/preview.
 *
 * @param {{
 *   mode: string,
 *   isVercel: boolean,
 *   styleDelivered: boolean,
 *   stylePath: string,
 * }} input
 * @returns {{ ok: true } | { ok: false, error: string }}
 */
export function assertVercelLocalBasemapDelivery(input) {
  if (input.mode !== "local-sovereign" || !input.isVercel) {
    return { ok: true };
  }
  if (input.styleDelivered) {
    return { ok: true };
  }
  return {
    ok: false,
    error: `Vercel build selected local-sovereign basemap mode but the local style is not delivered at ${input.stylePath}. Set PUBLIC_BASEMAP_MODE=remote-style, or ship the local style under apps/web/static/local-basemap/.`,
  };
}
