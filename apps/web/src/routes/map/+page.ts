import type { PageLoad } from "./$types";

export const load: PageLoad = async ({ fetch, depends }) => {
  depends("weltgewebe:domain-data");
  const apiUrl = import.meta.env.PUBLIC_GEWEBE_API_BASE ?? "";
  const { loadMapResources } = await import("$lib/map/cursorPagination");
  return loadMapResources((url) => fetch(url), apiUrl);
};
