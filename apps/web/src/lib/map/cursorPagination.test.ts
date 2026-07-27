import { describe, expect, it, vi } from "vitest";
import { fetchCursorPages, loadMapResources } from "./cursorPagination";

function page<T>(
  items: T[],
  hasMore: boolean,
  nextCursor: string | null,
  limit = 2,
) {
  return new Response(
    JSON.stringify({
      items,
      page: {
        limit,
        next_cursor: nextCursor,
        has_more: hasMore,
      },
    }),
    { status: 200, headers: { "content-type": "application/json" } },
  );
}

describe("fetchCursorPages", () => {
  it("loads every cursor page and preserves order", async () => {
    const fetcher = vi
      .fn<(input: string) => Promise<Response>>()
      .mockResolvedValueOnce(page([1, 2], true, "cursor-1"))
      .mockResolvedValueOnce(page([3, 4], true, "cursor-2"))
      .mockResolvedValueOnce(page([5], false, null));

    const result = await fetchCursorPages(fetcher, "/api/nodes", {
      pageSize: 2,
      maxPages: 10,
      maxItems: 10,
    });

    expect(result).toEqual({
      items: [1, 2, 3, 4, 5],
      status: "complete",
      pages: 3,
    });
    expect(fetcher.mock.calls.map(([url]) => url)).toEqual([
      "/api/nodes?pagination=cursor&limit=2",
      "/api/nodes?pagination=cursor&limit=2&cursor=cursor-1",
      "/api/nodes?pagination=cursor&limit=2&cursor=cursor-2",
    ]);
  });

  it("loads beyond one maximum-sized API page", async () => {
    const firstPage = Array.from({ length: 1000 }, (_, index) => index);
    const fetcher = vi
      .fn<(input: string) => Promise<Response>>()
      .mockResolvedValueOnce(page(firstPage, true, "cursor-1000", 1000))
      .mockResolvedValueOnce(page([1000], false, null, 1000));

    const result = await fetchCursorPages(fetcher, "/api/nodes");

    expect(result.status).toBe("complete");
    expect(result.items).toHaveLength(1001);
    expect(result.items.at(-1)).toBe(1000);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("rejects the legacy bare-array response instead of claiming completeness", async () => {
    const fetcher = vi.fn(
      async () => new Response(JSON.stringify([1, 2]), { status: 200 }),
    );

    await expect(fetchCursorPages(fetcher, "/api/nodes")).rejects.toThrow(
      "Invalid cursor response shape",
    );
  });

  it("rejects has_more without a next cursor", async () => {
    const fetcher = vi.fn(async () => page([1], true, null));

    await expect(fetchCursorPages(fetcher, "/api/nodes")).rejects.toThrow(
      "Missing next_cursor",
    );
  });

  it("does not let the page limit hide a broken cursor", async () => {
    const fetcher = vi.fn(async () => page([1], true, null));

    await expect(
      fetchCursorPages(fetcher, "/api/nodes", { maxPages: 1 }),
    ).rejects.toThrow("Missing next_cursor");
  });

  it("rejects a repeated cursor before looping", async () => {
    const fetcher = vi
      .fn<(input: string) => Promise<Response>>()
      .mockResolvedValueOnce(page([1], true, "same"))
      .mockResolvedValueOnce(page([2], true, "same"));

    await expect(fetchCursorPages(fetcher, "/api/nodes")).rejects.toThrow(
      "Cursor did not advance",
    );
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("fails the resource when a later page returns an HTTP error", async () => {
    const fetcher = vi
      .fn<(input: string) => Promise<Response>>()
      .mockResolvedValueOnce(page([1], true, "next"))
      .mockResolvedValueOnce(new Response("boom", { status: 503 }));

    await expect(fetchCursorPages(fetcher, "/api/nodes")).rejects.toThrow(
      "HTTP 503 while loading page 2",
    );
  });

  it("returns truncated when the page limit is reached", async () => {
    const fetcher = vi
      .fn<(input: string) => Promise<Response>>()
      .mockResolvedValueOnce(page([1], true, "cursor-1", 1))
      .mockResolvedValueOnce(page([2], true, "cursor-2", 1));

    await expect(
      fetchCursorPages(fetcher, "/api/nodes", {
        pageSize: 1,
        maxPages: 2,
        maxItems: 10,
      }),
    ).resolves.toEqual({
      items: [1, 2],
      status: "truncated",
      pages: 2,
      reason: "page_limit",
    });
  });

  it("caps the aggregate and returns truncated at the item limit", async () => {
    const fetcher = vi
      .fn<(input: string) => Promise<Response>>()
      .mockResolvedValueOnce(page([1, 2, 3], true, "cursor-1", 3))
      .mockResolvedValueOnce(page([4, 5, 6], true, "cursor-2", 3));

    await expect(
      fetchCursorPages(fetcher, "/api/nodes", {
        pageSize: 3,
        maxPages: 10,
        maxItems: 4,
      }),
    ).resolves.toEqual({
      items: [1, 2, 3, 4],
      status: "truncated",
      pages: 2,
      reason: "item_limit",
    });
  });
});

describe("loadMapResources", () => {
  it("returns resource statuses in stable domain order after out-of-order responses", async () => {
    const delays: Record<string, number> = { nodes: 15, accounts: 5, edges: 0 };
    const fetcher = vi.fn(async (input: string) => {
      const resource = new URL(input, "http://localhost").pathname
        .split("/")
        .at(-1)!;
      await new Promise((resolve) => setTimeout(resolve, delays[resource]));
      return page([], false, null, 1000);
    });

    const result = await loadMapResources(fetcher, "");

    expect(result.resourceStatus.map((status) => status.resource)).toEqual([
      "nodes",
      "accounts",
      "edges",
    ]);
    expect(result.loadState).toBe("ok");
    expect(result.loadNotice).toBeNull();
  });
});
