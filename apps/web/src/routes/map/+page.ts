import { browser } from "$app/environment";
import type { PageLoad } from "./$types";
import { selectMapResourceTransport } from "$lib/map/mapResourceTransport";

if (browser) {
  void import("maplibre-gl").catch(() => undefined);
}

export const load: PageLoad = async ({ fetch, depends }) => {
  depends("weltgewebe:domain-data");
  const apiUrl = import.meta.env.PUBLIC_GEWEBE_API_BASE ?? "";
  const runtime = {
    isDevelopment: import.meta.env.DEV,
    isProduction: import.meta.env.PROD,
    testProxyEnabled: import.meta.env.VITE_PUBLIC_ENABLE_TEST_MAP === "true",
  } as const;
  // Keep the cursor loader split from the initial map chunk; the build enforces this startup budget.
  const { loadMapResources } = await import("$lib/map/cursorPagination");
  const transport = selectMapResourceTransport(apiUrl, runtime);
  return loadMapResources((url) => fetch(url), apiUrl, transport);
};
