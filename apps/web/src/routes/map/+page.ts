import type { PageLoad } from "./$types";
import { readDrawerParam } from "./drawerDefaults";
import type { Node } from "./types";

export const load: PageLoad = async ({ url, fetch }) => {
  const apiBase = (import.meta.env.PUBLIC_GEWEBE_API_BASE ?? "").replace(
    /\/$/,
    "",
  );
  const apiPrefix = apiBase.endsWith("/api") ? "" : "/api";
  const apiUrl = (endpoint: string) =>
    apiBase ? `${apiBase}${apiPrefix}/${endpoint}` : `${apiPrefix}/${endpoint}`;
  const params = url.searchParams;

  const leftOpen = readDrawerParam(params, "l");
  const rightOpen = readDrawerParam(params, "r");
  const topOpen = readDrawerParam(params, "t");

  let nodes: Node[] = [];
  let accounts: any[] = [];
  let edges: any[] = [];

  try {
    const res = await fetch(apiUrl("nodes"));
    if (res.ok) {
      nodes = await res.json();
    } else {
      console.error(
        "Failed to fetch nodes from",
        apiBase || "/api",
        res.status,
      );
      console.error(await res.text());
    }
  } catch (e) {
    console.error("Error fetching nodes:", e);
  }

  try {
    const res = await fetch(apiUrl("accounts"));
    if (res.ok) {
      accounts = await res.json();
    } else {
      console.error(
        "Failed to fetch accounts from",
        apiBase || "/api",
        res.status,
      );
      console.error(await res.text());
    }
  } catch (e) {
    console.error("Error fetching accounts:", e);
  }

  try {
    const res = await fetch(apiUrl("edges"));
    if (res.ok) {
      edges = await res.json();
    } else {
      console.error(
        "Failed to fetch edges from",
        apiBase || "/api",
        res.status,
      );
      console.error(await res.text());
    }
  } catch (e) {
    console.error("Error fetching edges:", e);
  }

  return { leftOpen, rightOpen, topOpen, nodes, accounts, edges };
};
