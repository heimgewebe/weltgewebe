import type { PageLoad } from "./$types";
import { readDrawerParam } from "./drawerDefaults";
import type { Node } from "./types";

// Disable SSR for this page to ensure API calls happen client-side
// where Playwright mocking can intercept them
export const ssr = false;

export const load: PageLoad = async ({ url, fetch }) => {
  const params = url.searchParams;

  const leftOpen = readDrawerParam(params, "l");
  const rightOpen = readDrawerParam(params, "r");
  const topOpen = readDrawerParam(params, "t");

  // Fallback to local dev/test default if not configured
  const apiUrl = import.meta.env.PUBLIC_GEWEBE_API_BASE ?? "";

  let nodes: Node[] = [];
  try {
    const res = await fetch(`${apiUrl}/api/nodes`);
    if (res.ok) {
      nodes = await res.json();
    } else {
      console.error("Failed to fetch nodes from", apiUrl, res.status);
    }
  } catch (e) {
    console.error("Error fetching nodes:", e);
  }

  return { leftOpen, rightOpen, topOpen, nodes };
};
