import type { MapResourceTransport } from "./cursorPagination";

export interface MapResourceRuntimeSignals {
  isDevelopment: boolean;
  isProduction: boolean;
  testProxyEnabled: boolean;
}

/**
 * Choose how the map page loads domain resources.
 *
 * A configured API base is always cursor-paginated. An empty same-origin base
 * needs an explicit runtime contract: production/prerender data uses bare
 * arrays, while development and the E2E proxy keep the cursor envelope.
 */
export function selectMapResourceTransport(
  apiBase: string | undefined | null,
  runtime: MapResourceRuntimeSignals,
): MapResourceTransport {
  if (
    typeof runtime?.isDevelopment !== "boolean" ||
    typeof runtime?.isProduction !== "boolean" ||
    typeof runtime?.testProxyEnabled !== "boolean"
  ) {
    throw new Error(
      "Map resource transport requires isDevelopment, isProduction and testProxyEnabled booleans",
    );
  }
  if (runtime.isDevelopment === runtime.isProduction) {
    throw new Error(
      "Map resource transport requires exactly one development or production runtime",
    );
  }

  const base = typeof apiBase === "string" ? apiBase.trim() : "";
  if (base.length > 0) return "cursor";

  if (runtime.testProxyEnabled || runtime.isDevelopment) return "cursor";
  return "static-list";
}
