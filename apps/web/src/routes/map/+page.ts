import { building } from "$app/environment";
import type { PageLoad } from "./$types";

export const load: PageLoad = async ({ fetch, depends }) => {
  depends("weltgewebe:domain-data");
  const apiUrl = import.meta.env.PUBLIC_GEWEBE_API_BASE ?? "";
  // Keep the cursor loader split from the initial map chunk; the build enforces this startup budget.
  const { loadMapResources } = await import("$lib/map/cursorPagination");
  const transport = building && apiUrl.length === 0 ? "static-list" : "cursor";
  return loadMapResources((url) => fetch(url), apiUrl, transport);
};
