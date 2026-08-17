import { get } from "svelte/store";
import { describe, expect, it, vi } from "vitest";
import type { DirectConversation } from "$lib/api/directMessages";
import type { Proposal } from "$lib/api/governance";
import type { AuthStatus } from "$lib/auth/store";
import { createAccountAttentionController } from "$lib/accountAttentionRuntime";

function authenticated(
  accountId: string,
  role: "gast" | "weber" = "weber",
): AuthStatus {
  return {
    state: "authenticated",
    authenticated: true,
    account_id: accountId,
    role,
  };
}

function conversation(
  id: string,
  unreadCount: number,
  lastMessageAt: string,
): DirectConversation {
  return {
    id,
    counterpart_account_id: `counterpart-${id}`,
    counterpart_title: `Person ${id}`,
    created_at: lastMessageAt,
    updated_at: lastMessageAt,
    unread_count: unreadCount,
    last_message_preview: "Hallo",
    last_message_at: lastMessageAt,
    blocked_by_me: false,
    can_send: true,
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((next) => {
    resolve = next;
  });
  return { promise, resolve };
}

describe("accountAttentionRuntime", () => {
  it("drops a late message result after the authenticated account changes", async () => {
    let current = authenticated("account-a");
    const first = deferred<DirectConversation[]>();
    const second = deferred<DirectConversation[]>();
    const listDirectConversations = vi
      .fn<() => Promise<DirectConversation[]>>()
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise);

    const controller = createAccountAttentionController({
      getAuthStatus: () => current,
      checkAuth: vi.fn(async () => current),
      listDirectConversations,
      listProposals: vi.fn(async () => [] as Proposal[]),
    });

    const refreshA = controller.refresh(current);
    current = authenticated("account-b");
    const refreshB = controller.refresh(current);

    first.resolve([conversation("from-a", 1, "2026-08-17T06:00:00Z")]);
    await Promise.resolve();
    expect(get(controller).accountId).toBe("account-b");
    expect(get(controller).items).toEqual([]);

    second.resolve([conversation("from-b", 2, "2026-08-17T07:00:00Z")]);
    await Promise.all([refreshA, refreshB]);

    expect(get(controller).items.map((item) => item.id)).toEqual([
      "direct:from-b",
    ]);
  });

  it("keeps the last confirmed unread projection through a transient failure", async () => {
    const current = authenticated("account-a");
    const listDirectConversations = vi
      .fn<() => Promise<DirectConversation[]>>()
      .mockResolvedValueOnce([
        conversation("confirmed", 3, "2026-08-17T07:00:00Z"),
      ])
      .mockRejectedValueOnce(new Error("temporary outage"));

    const controller = createAccountAttentionController({
      getAuthStatus: () => current,
      checkAuth: vi.fn(async () => current),
      listDirectConversations,
      listProposals: vi.fn(async () => [] as Proposal[]),
    });

    await controller.refresh(current);
    expect(get(controller).items[0]).toMatchObject({
      id: "direct:confirmed",
      count: 3,
    });

    await controller.refreshMessages(current);
    expect(get(controller).items[0]).toMatchObject({
      id: "direct:confirmed",
      count: 3,
    });
  });

  it("keeps a guest application unknown when the initial proposal read fails", async () => {
    const current = authenticated("guest-a", "gast");
    const controller = createAccountAttentionController({
      getAuthStatus: () => current,
      checkAuth: vi.fn(async () => current),
      listDirectConversations: vi.fn(async () => []),
      listProposals: vi.fn(async () => {
        throw new Error("temporarily unavailable");
      }),
    });

    await controller.refresh(current);
    expect(get(controller).weberApplicationState).toBe("unknown");
  });

  it("resets personal attention when authentication disappears", async () => {
    let current = authenticated("account-a");
    const controller = createAccountAttentionController({
      getAuthStatus: () => current,
      checkAuth: vi.fn(async () => current),
      listDirectConversations: vi.fn(async () => [
        conversation("confirmed", 1, "2026-08-17T07:00:00Z"),
      ]),
      listProposals: vi.fn(async () => []),
    });

    await controller.refresh(current);
    expect(get(controller).items).toHaveLength(1);

    current = { state: "unauthenticated", authenticated: false, role: "gast" };
    await controller.refresh(current);
    expect(get(controller)).toMatchObject({
      accountId: "",
      weberApplicationState: "unknown",
      conversations: [],
      proposals: [],
      items: [],
    });
  });
});
