import type { PageLoad } from "./$types";
import type { Account } from "$lib/map/types";

export const load: PageLoad = async ({ fetch }) => {
  const apiUrl = import.meta.env.PUBLIC_GEWEBE_API_BASE ?? "";

  try {
    const response = await fetch(`${apiUrl}/api/accounts`);
    if (!response.ok) {
      return {
        accounts: [] as Account[],
        accountsLoadError: `HTTP ${response.status}`,
      };
    }
    const accounts = (await response.json()) as Account[];
    return { accounts, accountsLoadError: null };
  } catch (error) {
    return {
      accounts: [] as Account[],
      accountsLoadError: error instanceof Error ? error.message : String(error),
    };
  }
};
