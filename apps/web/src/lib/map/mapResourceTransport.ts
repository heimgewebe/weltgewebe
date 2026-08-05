import type { MapResourceTransport } from "./cursorPagination";

/**
 * Choose how the map page loads domain resources.
 *
 * Empty PUBLIC_GEWEBE_API_BASE means the prerendered same-origin demo API,
 * which returns bare arrays and must use static-list (including in the browser).
 * A configured remote API base remains cursor-paginated.
 */
export function selectMapResourceTransport(
  apiBase: string | undefined | null,
): MapResourceTransport {
  const base = typeof apiBase === "string" ? apiBase : "";
  return base.length === 0 ? "static-list" : "cursor";
}
