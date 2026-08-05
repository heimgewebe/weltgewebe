/**
 * Fail-closed map startup decisions. Only failures that prevent the first
 * successful MapLibre `load` may mark the map as unrecoverably failed for this
 * mount. Errors after a successful load stay local and must not tear the map
 * down wholesale.
 */

export type MapInitFailureReason =
  | "import"
  | "constructor"
  | "timeout"
  | "maplibre-error"
  | "post-load-error"
  | "auth-camera";

export type MapInitFailureDecision = "fail" | "ignore";

/** Wall-clock deadline for the whole map init path, including dynamic imports. */
export const MAP_INIT_TIMEOUT_MS = 10_000;

/**
 * Arms the init deadline. Call immediately in the mount path *before* the first
 * `await`/`import()` so a hung chunk load still fails closed.
 */
export function scheduleMapInitTimeout(
  onTimeout: () => void,
  schedule: typeof setTimeout = setTimeout,
  timeoutMs: number = MAP_INIT_TIMEOUT_MS,
): ReturnType<typeof setTimeout> {
  return schedule(onTimeout, timeoutMs);
}

/**
 * Returns whether a failure should set `mapInitFailed` for the current mount.
 * `hasLoaded` means MapLibre already emitted `load` successfully.
 */
export function resolveMapInitFailure(
  hasLoaded: boolean,
  reason: MapInitFailureReason,
): MapInitFailureDecision {
  if (hasLoaded) return "ignore";
  // Secondary auth convergence never owns the map mount lifecycle.
  if (reason === "auth-camera" || reason === "post-load-error") return "ignore";
  return "fail";
}
