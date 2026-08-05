import type { PageLoad } from "./$types";
import { selectMapResourceTransport } from "$lib/map/mapResourceTransport";

export const load: PageLoad = async ({ fetch, depends }) => {
  depends("weltgewebe:domain-data");
  const apiUrl = import.meta.env.PUBLIC_GEWEBE_API_BASE ?? "";
  // Keep the cursor loader split from the initial map chunk; the build enforces this startup budget.
  const { loadMapResources } = await import("$lib/map/cursorPagination");
  // Empty PUBLIC_GEWEBE_API_BASE is the prerendered same-origin demo API (bare arrays).
  // Use static-list in the browser too; only a configured remote base stays on cursor.
  const transport = selectMapResourceTransport(apiUrl);
  return loadMapResources((url) => fetch(url), apiUrl, transport);
};
