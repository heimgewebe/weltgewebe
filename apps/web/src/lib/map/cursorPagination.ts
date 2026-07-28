import type {
  Account,
  Edge,
  MapLoadState,
  MapResourceName,
  MapResourceStatus,
  Node,
} from "./types";

export const MAP_CURSOR_PAGE_SIZE = 1000;
export const MAP_CURSOR_MAX_PAGES = 10;
export const MAP_CURSOR_MAX_ITEMS = 10_000;

export type CursorTruncationReason = "page_limit" | "item_limit";

export type CursorPaginationResult<T> =
  | {
      items: T[];
      status: "complete";
      pages: number;
    }
  | {
      items: T[];
      status: "truncated";
      pages: number;
      reason: CursorTruncationReason;
    };

export type CursorPaginationOptions = {
  pageSize?: number;
  maxPages?: number;
  maxItems?: number;
};

type FetchLike = (input: string) => Promise<Response>;

type CursorEnvelope<T> = {
  items: T[];
  page: {
    limit: number;
    next_cursor: string | null;
    has_more: boolean;
  };
};

export class CursorPaginationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "CursorPaginationError";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function positiveInteger(value: number, label: string): number {
  if (!Number.isInteger(value) || value <= 0) {
    throw new CursorPaginationError(`${label} must be a positive integer`);
  }
  return value;
}

function parseEnvelope<T>(
  value: unknown,
  pageNumber: number,
): CursorEnvelope<T> {
  if (
    !isRecord(value) ||
    !Array.isArray(value.items) ||
    !isRecord(value.page)
  ) {
    throw new CursorPaginationError(
      `Invalid cursor response shape on page ${pageNumber}`,
    );
  }

  const limit = value.page.limit;
  const nextCursor = value.page.next_cursor;
  const hasMore = value.page.has_more;

  if (!Number.isInteger(limit) || (limit as number) <= 0) {
    throw new CursorPaginationError(`Invalid page limit on page ${pageNumber}`);
  }
  if (typeof hasMore !== "boolean") {
    throw new CursorPaginationError(
      `Invalid has_more flag on page ${pageNumber}`,
    );
  }
  if (nextCursor !== null && typeof nextCursor !== "string") {
    throw new CursorPaginationError(
      `Invalid next_cursor on page ${pageNumber}`,
    );
  }
  if (!hasMore && nextCursor !== null) {
    throw new CursorPaginationError(
      `Unexpected next_cursor on final page ${pageNumber}`,
    );
  }

  return {
    items: value.items as T[],
    page: {
      limit: limit as number,
      next_cursor: nextCursor as string | null,
      has_more: hasMore,
    },
  };
}

function cursorUrl(endpoint: string, cursor: string | null, pageSize: number) {
  const params = new URLSearchParams({
    pagination: "cursor",
    limit: String(pageSize),
  });
  if (cursor !== null) params.set("cursor", cursor);
  const separator = endpoint.includes("?") ? "&" : "?";
  return `${endpoint}${separator}${params.toString()}`;
}

/**
 * Walk a cursor endpoint until it is complete or a declared safety limit is hit.
 *
 * A safety-limit hit returns the bounded items with `status: "truncated"`.
 * Broken HTTP, JSON, envelope or cursor-progress contracts throw instead, so the
 * caller can mark the resource as failed rather than silently claim completeness.
 */
export async function fetchCursorPages<T>(
  fetcher: FetchLike,
  endpoint: string,
  options: CursorPaginationOptions = {},
): Promise<CursorPaginationResult<T>> {
  const pageSize = positiveInteger(
    options.pageSize ?? MAP_CURSOR_PAGE_SIZE,
    "pageSize",
  );
  const maxPages = positiveInteger(
    options.maxPages ?? MAP_CURSOR_MAX_PAGES,
    "maxPages",
  );
  const maxItems = positiveInteger(
    options.maxItems ?? MAP_CURSOR_MAX_ITEMS,
    "maxItems",
  );

  const items: T[] = [];
  const seenCursors = new Set<string>();
  let cursor: string | null = null;
  let pages = 0;

  while (true) {
    const pageNumber = pages + 1;
    const response = await fetcher(cursorUrl(endpoint, cursor, pageSize));
    if (!response.ok) {
      throw new CursorPaginationError(
        `HTTP ${response.status} while loading page ${pageNumber}`,
      );
    }

    let body: unknown;
    try {
      body = await response.json();
    } catch {
      throw new CursorPaginationError(`Invalid JSON on page ${pageNumber}`);
    }

    const envelope = parseEnvelope<T>(body, pageNumber);
    pages = pageNumber;

    let nextCursor: string | null = null;
    if (envelope.page.has_more) {
      if (envelope.items.length === 0) {
        throw new CursorPaginationError(
          `Cursor page ${pageNumber} claims more data without items`,
        );
      }
      nextCursor = envelope.page.next_cursor;
      if (nextCursor === null || nextCursor.length === 0) {
        throw new CursorPaginationError(
          `Missing next_cursor on page ${pageNumber}`,
        );
      }
      if (nextCursor === cursor || seenCursors.has(nextCursor)) {
        throw new CursorPaginationError(
          `Cursor did not advance on page ${pageNumber}`,
        );
      }
    }

    const remaining = maxItems - items.length;
    if (envelope.items.length > remaining) {
      items.push(...envelope.items.slice(0, remaining));
      return { items, status: "truncated", pages, reason: "item_limit" };
    }
    items.push(...envelope.items);

    if (!envelope.page.has_more) {
      return { items, status: "complete", pages };
    }
    if (items.length >= maxItems) {
      return { items, status: "truncated", pages, reason: "item_limit" };
    }
    if (pages >= maxPages) {
      return { items, status: "truncated", pages, reason: "page_limit" };
    }
    if (nextCursor === null) {
      throw new CursorPaginationError(
        `Missing next_cursor on page ${pageNumber}`,
      );
    }

    seenCursors.add(nextCursor);
    cursor = nextCursor;
  }
}

/**
 * Load one complete resource from the in-repository prerendered demo API.
 *
 * These same-origin endpoints intentionally expose their full static dataset as
 * a bare JSON array. Keeping this path explicit prevents remote cursor APIs from
 * silently falling back to the legacy response shape.
 */
async function fetchCompleteStaticList<T>(
  fetcher: FetchLike,
  endpoint: string,
): Promise<CursorPaginationResult<T>> {
  const response = await fetcher(endpoint);
  if (!response.ok) {
    throw new CursorPaginationError(
      `HTTP ${response.status} while loading static resource`,
    );
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new CursorPaginationError("Invalid JSON in static resource");
  }
  if (!Array.isArray(body)) {
    throw new CursorPaginationError("Invalid static resource response shape");
  }

  return { items: body as T[], status: "complete", pages: 1 };
}

export type MapResourceLoad = {
  nodes: Node[];
  accounts: Account[];
  edges: Edge[];
  loadState: MapLoadState;
  loadNotice: string | null;
  resourceStatus: MapResourceStatus[];
};

/** Load all map resources while preserving complete, truncated and failed truth. */
export async function loadMapResources(
  fetcher: FetchLike,
  apiUrl: string,
): Promise<MapResourceLoad> {
  const resourceStatus: MapResourceStatus[] = [];

  async function loadResource<T>(
    resource: MapResourceName,
    fallback: T[] = [],
  ): Promise<T[]> {
    try {
      const endpoint = `${apiUrl}/api/${resource}`;
      const result =
        apiUrl.length === 0
          ? await fetchCompleteStaticList<T>(fetcher, endpoint)
          : await fetchCursorPages<T>(fetcher, endpoint);
      resourceStatus.push(
        result.status === "complete"
          ? {
              resource,
              status: "complete",
              loaded: result.items.length,
              pages: result.pages,
            }
          : {
              resource,
              status: "truncated",
              loaded: result.items.length,
              pages: result.pages,
              reason: result.reason,
            },
      );
      return result.items;
    } catch (error) {
      console.error(`Error fetching ${resource} from`, apiUrl, error);
      resourceStatus.push({
        resource,
        status: "failed",
        error: error instanceof Error ? error.message : String(error),
      });
      return fallback;
    }
  }

  const [nodes, accounts, edges] = await Promise.all([
    loadResource<Node>("nodes"),
    loadResource<Account>("accounts"),
    loadResource<Edge>("edges"),
  ]);
  const resourceOrder: MapResourceName[] = ["nodes", "accounts", "edges"];
  resourceStatus.sort(
    (left, right) =>
      resourceOrder.indexOf(left.resource) -
      resourceOrder.indexOf(right.resource),
  );
  const failedCount = resourceStatus.filter(
    (status) => status.status === "failed",
  ).length;
  const completeCount = resourceStatus.filter(
    (status) => status.status === "complete",
  ).length;
  const loadState: MapLoadState =
    failedCount === resourceStatus.length
      ? "failed"
      : completeCount === resourceStatus.length
        ? "ok"
        : "partial";
  const resourceLabels: Record<MapResourceName, string> = {
    nodes: "Knoten",
    accounts: "Garnrollen",
    edges: "Fäden",
  };
  const labelsFor = (status: "failed" | "truncated") =>
    resourceOrder
      .filter((resource) =>
        resourceStatus.some(
          (entry) => entry.resource === resource && entry.status === status,
        ),
      )
      .map((resource) => resourceLabels[resource]);
  const failedLabels = labelsFor("failed");
  const truncatedLabels = labelsFor("truncated");
  const loadNotice =
    loadState === "partial"
      ? [
          failedLabels.length > 0
            ? `Einige Kartendaten konnten nicht geladen werden (${failedLabels.join(", ")}).`
            : null,
          truncatedLabels.length > 0
            ? `Der geladene Kartenbestand ist bewusst unvollständig (${truncatedLabels.join(", ")}).`
            : null,
        ]
          .filter(Boolean)
          .join(" ")
      : null;

  return { nodes, accounts, edges, loadState, loadNotice, resourceStatus };
}
