import { afterEach, describe, expect, it, vi } from "vitest";
import {
  listDirectConversations,
  markDirectConversationRead,
  openDirectConversation,
  setDirectConversationBlocked,
} from "./directMessages";

afterEach(() => vi.unstubAllGlobals());

const conversation = {
  id: "conversation-a",
  counterpart_account_id: "account-b",
  counterpart_title: "B",
  created_at: "2026-07-30T12:00:00Z",
  updated_at: "2026-07-30T12:00:00Z",
  unread_count: 1,
  last_message_preview: "Hallo",
  last_message_at: "2026-07-30T12:00:00Z",
  blocked_by_me: false,
  can_send: true,
};

describe("direct messages API", () => {
  it("loads the authenticated inbox", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ items: [conversation] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(listDirectConversations()).resolves.toEqual([conversation]);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/direct-conversations",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("opens a conversation with a canonical recipient payload", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(conversation), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await openDirectConversation("account-b");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/direct-conversations",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        body: JSON.stringify({ recipient_account_id: "account-b" }),
      }),
    );
  });

  it("accepts the empty 204 read receipt", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      markDirectConversationRead("conversation-a", "message-a"),
    ).resolves.toBeUndefined();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/direct-conversations/conversation-a/read",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ through_message_id: "message-a" }),
      }),
    );
  });

  it("uses PUT to block and DELETE to unblock", async () => {
    const blockedConversation = {
      ...conversation,
      blocked_by_me: true,
      can_send: false,
    };
    // Releasing the own block does not restore sending while the counterpart
    // still blocks, so the refreshed conversation is the authoritative answer.
    const releasedConversation = {
      ...conversation,
      blocked_by_me: false,
      can_send: false,
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify(blockedConversation), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(releasedConversation), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      setDirectConversationBlocked("conversation-a", true),
    ).resolves.toEqual(blockedConversation);
    await expect(
      setDirectConversationBlocked("conversation-a", false),
    ).resolves.toEqual(releasedConversation);

    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({ method: "PUT" });
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({ method: "DELETE" });
  });
});
