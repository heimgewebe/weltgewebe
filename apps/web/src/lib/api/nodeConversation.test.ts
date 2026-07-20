import { afterEach, describe, expect, it, vi } from "vitest";
import {
  compareApiTimestamps,
  createConversationMessage,
  listConversationMessages,
  tombstoneConversationMessage,
  updateConversationMessage,
} from "./nodeConversation";

afterEach(() => vi.unstubAllGlobals());

describe("node conversation API", () => {
  it("orders UTC timestamps exactly across optional fractional precision", () => {
    expect(
      compareApiTimestamps("2026-07-19T12:00:00.1Z", "2026-07-19T12:00:00Z"),
    ).toBeGreaterThan(0);
    expect(
      compareApiTimestamps(
        "2026-07-19T12:00:00.123457Z",
        "2026-07-19T12:00:00.123456Z",
      ),
    ).toBeGreaterThan(0);
    expect(
      compareApiTimestamps(
        "2026-07-19T12:00:00.100000Z",
        "2026-07-19T12:00:00.1Z",
      ),
    ).toBe(0);
  });

  it("uses bounded cursor pagination", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          items: [],
          page: { limit: 50, next_cursor: null, has_more: false },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await listConversationMessages("conversation-a", "opaque-cursor");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/conversations/conversation-a/messages?limit=50&cursor=opaque-cursor",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("sends idempotency and optimistic concurrency headers", async () => {
    const message = {
      id: "message-a",
      conversation_id: "conversation-a",
      author_account_id: "account-a",
      author_title: "Alex",
      content: "Hallo",
      created_at: "2026-07-19T12:00:00Z",
      updated_at: "2026-07-19T12:00:00Z",
      deleted_at: null,
    };
    const fetchMock = vi.fn().mockImplementation(
      async () =>
        new Response(JSON.stringify(message), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await createConversationMessage("conversation-a", "Hallo", "operation-a");
    await updateConversationMessage(
      "conversation-a",
      "message-a",
      "Neu",
      message.updated_at,
    );
    await tombstoneConversationMessage(
      "conversation-a",
      "message-a",
      message.updated_at,
    );

    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
      method: "POST",
      headers: { "Idempotency-Key": "operation-a" },
    });
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({
      method: "PATCH",
      headers: { "If-Match": '"2026-07-19T12:00:00Z"' },
    });
    expect(fetchMock.mock.calls[2]?.[1]).toMatchObject({
      method: "DELETE",
      headers: { "If-Match": '"2026-07-19T12:00:00Z"' },
    });
  });

  it("keeps the stable backend error and current conflict version", async () => {
    const current = {
      id: "message-a",
      conversation_id: "conversation-a",
      author_account_id: "account-a",
      author_title: "Alex",
      content: "Serverstand",
      created_at: "2026-07-19T12:00:00Z",
      updated_at: "2026-07-19T12:01:00Z",
      deleted_at: null,
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            code: "message_version_conflict",
            message: "conflict",
            current,
          }),
          { status: 412, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    await expect(
      updateConversationMessage(
        "conversation-a",
        "message-a",
        "Entwurf",
        "stale",
      ),
    ).rejects.toMatchObject({
      status: 412,
      code: "message_version_conflict",
      current,
    });
  });
});
