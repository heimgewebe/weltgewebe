import type { PageLoad } from "./$types";
import type {
  Account,
  Edge,
  Node,
  MapLoadState,
  MapResourceStatus,
} from "$lib/map/types";

type ResourceName = "nodes" | "accounts" | "edges";

export const load: PageLoad = async ({ fetch }) => {
  // Fallback to local dev/test default if not configured
  const apiUrl = import.meta.env.PUBLIC_GEWEBE_API_BASE ?? "";

  const resourceStatuses: MapResourceStatus[] = [];

  /**
   * Helper to fetch a resource with consistent error handling and logging.
   * Tracks per-resource success/failure for explicit load state reporting.
   */
  async function fetchResource<T>(
    resource: ResourceName,
    fallback: T[] = [],
  ): Promise<T[]> {
    try {
      const res = await fetch(`${apiUrl}/api/${resource}`);
      if (res.ok) {
        resourceStatuses.push({ resource, status: "ok" });
        return await res.json();
      } else {
        const errorText = await res.text();
        console.error(`Failed to fetch ${resource} from`, apiUrl, res.status);
        console.error(errorText);
        resourceStatuses.push({
          resource,
          status: "failed",
          error: `HTTP ${res.status}`,
        });
      }
    } catch (e) {
      console.error(`Error fetching ${resource}:`, e);
      resourceStatuses.push({
        resource,
        status: "failed",
        error: e instanceof Error ? e.message : String(e),
      });
    }
    return fallback;
  }

  const [nodes, accounts, edges] = await Promise.all([
    fetchResource<Node>("nodes"),
    fetchResource<Account>("accounts"),
    fetchResource<Edge>("edges"),
  ]);

  const failedCount = resourceStatuses.filter(
    (s) => s.status === "failed",
  ).length;
  const loadState: MapLoadState =
    failedCount === 0
      ? "ok"
      : failedCount === resourceStatuses.length
        ? "failed"
        : "partial";

  return {
    nodes,
    accounts,
    edges,
    loadState,
    resourceStatus: resourceStatuses,
  };
};
