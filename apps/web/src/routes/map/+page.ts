import type { PageLoad } from "./$types";
import type { Account, Edge, Node } from "$lib/map/types";

export const load: PageLoad = async ({ fetch }) => {
  // Fallback to local dev/test default if not configured
  const apiUrl = import.meta.env.PUBLIC_GEWEBE_API_BASE ?? "";

  /**
   * Helper to fetch a resource with consistent error handling and logging.
   */
  async function fetchResource<T>(
    resource: string,
    fallback: T[] = [],
  ): Promise<T[]> {
    try {
      const res = await fetch(`${apiUrl}/api/${resource}`);
      if (res.ok) {
        return await res.json();
      } else {
        console.error(`Failed to fetch ${resource} from`, apiUrl, res.status);
        console.error(await res.text());
      }
    } catch (e) {
      console.error(`Error fetching ${resource}:`, e);
    }
    return fallback;
  }

  const [nodes, accounts, edges] = await Promise.all([
    fetchResource<Node>("nodes"),
    fetchResource<Account>("accounts"),
    fetchResource<Edge>("edges"),
  ]);

  return { nodes, accounts, edges };
};
