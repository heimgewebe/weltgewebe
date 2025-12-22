import type { PageLoad } from "./$types";
import { readDrawerParam } from "./drawerDefaults";
import type { Node } from "./types";

export const load: PageLoad = async ({ url, fetch }) => {
  const params = url.searchParams;

  const leftOpen = readDrawerParam(params, "l");
  const rightOpen = readDrawerParam(params, "r");
  const topOpen = readDrawerParam(params, "t");

  // Robust API URL handling
  const apiBase = (import.meta.env.PUBLIC_GEWEBE_API_BASE ?? "").replace(/\/$/, "");
  const apiPrefix = apiBase.endsWith("/api") ? "" : "/api";

  const getApiUrl = (endpoint: string) =>
    apiBase ? `${apiBase}${apiPrefix}/${endpoint}` : `/api/${endpoint}`;

  let nodes: Node[] = [];
  let accounts: any[] = [];
  let edges: any[] = [];

  try {
    const url = getApiUrl("nodes");
    const res = await fetch(url);
    if (res.ok) {
      nodes = await res.json();
    } else {
      console.error("Failed to fetch nodes from", url, res.status);
      console.error(await res.text());
    }
  } catch (e) {
    console.error("Error fetching nodes:", e);
  }

  try {
    const url = getApiUrl("accounts");
    const res = await fetch(url);
    if (res.ok) {
      accounts = await res.json();
    } else {
      console.error("Failed to fetch accounts from", url, res.status);
      console.error(await res.text());
    }
  } catch (e) {
    console.error("Error fetching accounts:", e);
  }

  try {
    const url = getApiUrl("edges");
    const res = await fetch(url);
    if (res.ok) {
      edges = await res.json();
    } else {
      console.error("Failed to fetch edges from", url, res.status);
      console.error(await res.text());
    }
  } catch (e) {
    console.error("Error fetching edges:", e);
  }

  return { leftOpen, rightOpen, topOpen, nodes, accounts, edges };
};
