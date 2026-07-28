import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ArchiveConversationApiError,
  loadArchivedConversation,
} from "./archiveConversation";

const CONVERSATION_ID = "70000000-0000-4000-8000-000000000001";

function conversation() {
  return {
    id: CONVERSATION_ID,
    conversation_type: "node",
    lifecycle_state: "archived",
    node_id: null,
    node_id_snapshot: "node/mit leerzeichen",
    node_title_snapshot: "Historischer Knoten",
    visibility: "public",
    created_at: "2026-07-27T08:00:00Z",
    updated_at: "2026-07-27T09:05:00Z",
    archived_at: "2026-07-27T09:05:00Z",
    deleted_at: null,
  };
}

function message(id: string, createdAt: string) {
  return {
    id,
    conversation_id: CONVERSATION_ID,
    author_account_id: "account-a",
    author_title: "Garnrolle A",
    content: `Beitrag ${id}`,
    created_at: createdAt,
    updated_at: createdAt,
    deleted_at: null,
  };
}

afterEach(() => vi.unstubAllGlobals());

describe("conversation archive API", () => {
  it("loads validated metadata and every message page in chronological order", async () => {
    const newer = message(
      "80000000-0000-4000-8000-000000000002",
      "2026-07-27T09:00:00Z",
    );
    const older = message(
      "80000000-0000-4000-8000-000000000001",
      "2026-07-27T08:30:00Z",
    );
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        expect(init).toEqual(
          expect.objectContaining({ credentials: "include" }),
        );
        if (path === `/api/conversations/${CONVERSATION_ID}`) {
          return Response.json(conversation());
        }
        if (
          path === `/api/conversations/${CONVERSATION_ID}/messages?limit=50`
        ) {
          return Response.json({
            items: [newer],
            page: { limit: 50, next_cursor: "older-page", has_more: true },
          });
        }
        if (
          path ===
          `/api/conversations/${CONVERSATION_ID}/messages?limit=50&cursor=older-page`
        ) {
          return Response.json({
            items: [older],
            page: { limit: 50, next_cursor: null, has_more: false },
          });
        }
        return new Response(null, { status: 404 });
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(loadArchivedConversation(CONVERSATION_ID)).resolves.toEqual({
      conversation: conversation(),
      messages: [older, newer],
    });
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it.each([
    ["metadata", {}],
    [
      "message collection",
      {
        items: [{ content: "<script>alert(1)</script>" }],
        page: { limit: 50, next_cursor: null, has_more: false },
      },
    ],
  ])("rejects malformed %s responses fail-safe", async (kind, malformed) => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input);
        if (path.endsWith("/messages?limit=50")) {
          return Response.json(malformed);
        }
        return Response.json(kind === "metadata" ? malformed : conversation());
      }),
    );

    const error = await loadArchivedConversation(CONVERSATION_ID).catch(
      (reason) => reason,
    );
    expect(error).toBeInstanceOf(ArchiveConversationApiError);
    expect(error).toMatchObject({
      status: 502,
      code: "malformed_response",
    });
  });

  it("preserves not-found responses for the archive state", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          Response.json(
            { code: "conversation_not_found", message: "not found" },
            { status: 404 },
          ),
        ),
    );

    await expect(
      loadArchivedConversation(CONVERSATION_ID),
    ).rejects.toMatchObject({
      status: 404,
      code: "conversation_not_found",
    });
  });
});
