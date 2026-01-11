import type { PageLoad } from "./$types";
import { readDrawerParam } from "./drawerDefaults";
import type { Account, Edge, Node } from "./types";

export const load: PageLoad = async ({ url, fetch }) => {
  const params = url.searchParams;

  const leftOpen = readDrawerParam(params, "l");
  const rightOpen = readDrawerParam(params, "r");
  const topOpen = readDrawerParam(params, "t");

  // Fallback to local dev/test default if not configured
  const apiUrl = import.meta.env.PUBLIC_GEWEBE_API_BASE ?? "";

  let nodes: Node[] = [];
  let accounts: Account[] = [];
  let edges: Edge[] = [];

  try {
    const res = await fetch(`${apiUrl}/api/nodes`);
    if (res.ok) {
      nodes = await res.json();
    } else {
      console.error("Failed to fetch nodes from", apiUrl, res.status);
      console.error(await res.text());
    }
  } catch (e) {
    console.error("Error fetching nodes:", e);
  }

  try {
    const res = await fetch(`${apiUrl}/api/accounts`);
    if (res.ok) {
      accounts = await res.json();
    } else {
      console.error("Failed to fetch accounts from", apiUrl, res.status);
      console.error(await res.text());
    }
  } catch (e) {
    console.error("Error fetching accounts:", e);
  }

  try {
    const res = await fetch(`${apiUrl}/api/edges`);
    if (res.ok) {
      edges = await res.json();
    } else {
      console.error("Failed to fetch edges from", apiUrl, res.status);
      console.error(await res.text());
    }
  } catch (e) {
    console.error("Error fetching edges:", e);
  }

  return { leftOpen, rightOpen, topOpen, nodes, accounts, edges };
};
