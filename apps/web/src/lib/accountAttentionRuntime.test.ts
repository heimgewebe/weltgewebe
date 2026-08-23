import { get } from "svelte/store";
import { afterEach, describe, expect, it, vi } from "vitest";
import { accountAttentionInvalidation } from "$lib/accountAttention";
import type { DirectConversation } from "$lib/api/directMessages";
import { postProposalMessage, type Proposal } from "$lib/api/governance";
import type { AuthStatus } from "$lib/auth/store";
import {
  createAccountAttentionController,
  maskAccountAttentionForAuth,
  type AccountAttentionState,
} from "$lib/accountAttentionRuntime";

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
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });
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

  it("masks retained personal state before a different or logged-out account can render it", () => {
    const stale: AccountAttentionState = {
      accountId: "account-a",
      role: "weber",
      weberApplicationState: "unknown",
      conversations: [conversation("private-a", 2, "2026-08-17T07:00:00Z")],
      proposals: [],
      items: [
        {
          id: "direct:private-a",
          kind: "direct_message",
          meaning: "new",
          label: "Private A",
          detail: "2 ungelesene Nachrichten",
          href: "/nachrichten?id=private-a",
          occurredAt: "2026-08-17T07:00:00Z",
          count: 2,
        },
      ],
    };

    expect(
      maskAccountAttentionForAuth(stale, {
        state: "unauthenticated",
        authenticated: false,
        role: "gast",
      }),
    ).toMatchObject({
      accountId: "",
      conversations: [],
      proposals: [],
      items: [],
    });
    expect(
      maskAccountAttentionForAuth(stale, authenticated("account-b")),
    ).toMatchObject({
      accountId: "",
      conversations: [],
      proposals: [],
      items: [],
    });
  });

  it("reprojects retained governance immediately when a role loses collective participation", () => {
    const proposal: Proposal = {
      id: "collective",
      kind: "sachantrag",
      webgemeindezentrum_id: "wgz-test",
      title: "Parkbank",
      applicant_account_id: "account-b",
      applicant_title: "Berta",
      status: "voting",
      consent_until: "2026-08-17T07:00:00Z",
      voting_until: "2026-08-24T07:00:00Z",
      created_at: "2026-08-17T07:00:00Z",
      veto_count: 0,
      yes_votes: 0,
      no_votes: 0,
      abstain_votes: 0,
      viewer_participation: {
        vote_choice: null,
        has_veto: false,
        may_vote: true,
        may_veto: false,
      },
    };
    const stale: AccountAttentionState = {
      accountId: "account-a",
      role: "weber",
      weberApplicationState: "unknown",
      conversations: [],
      proposals: [proposal],
      items: [
        {
          id: "proposal:collective",
          kind: "governance",
          meaning: "available",
          label: "Parkbank",
          detail: "Du kannst noch abstimmen",
          href: "/antraege?id=collective",
          occurredAt: proposal.consent_until,
        },
      ],
    };

    const masked = maskAccountAttentionForAuth(
      stale,
      authenticated("account-a", "gast"),
    );
    expect(masked.role).toBe("gast");
    expect(masked.items).toEqual([]);
  });

  it("reprojects a crossed governance deadline locally without another network read", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-17T12:00:00Z"));
    const current = authenticated("account-a");
    const listProposals = vi.fn(
      async (): Promise<Proposal[]> => [
        {
          id: "deadline-vote",
          kind: "sachantrag",
          webgemeindezentrum_id: "wgz-test",
          title: "Parkbank",
          applicant_account_id: "account-b",
          applicant_title: "Berta",
          status: "voting",
          created_at: "2026-08-16T12:00:00Z",
          consent_until: "2026-08-17T10:00:00Z",
          voting_until: "2026-08-17T12:01:00Z",
          remaining_seconds: 60,
          veto_count: 0,
          yes_votes: 0,
          no_votes: 0,
          abstain_votes: 0,
          viewer_participation: {
            vote_choice: null,
            has_veto: false,
            may_vote: true,
            may_veto: false,
          },
        },
      ],
    );
    const listDirectConversations = vi.fn(
      async () => [] as DirectConversation[],
    );
    const controller = createAccountAttentionController({
      getAuthStatus: () => current,
      checkAuth: vi.fn(async () => current),
      listDirectConversations,
      listProposals,
    });

    await controller.refresh(current);
    expect(get(controller).items.map((item) => item.id)).toEqual([
      "proposal:deadline-vote",
    ]);

    vi.setSystemTime(new Date("2026-08-17T12:02:00Z"));
    controller.reproject();
    expect(get(controller).items).toEqual([]);
    expect(listProposals).toHaveBeenCalledTimes(1);
    expect(listDirectConversations).toHaveBeenCalledTimes(1);
  });

  it("re-reads proposal truth without re-reading messages", async () => {
    const current = authenticated("account-a");
    const baseProposal: Proposal = {
      id: "phase-change",
      kind: "sachantrag",
      webgemeindezentrum_id: "wgz-test",
      title: "Parkbank",
      applicant_account_id: "account-b",
      applicant_title: "Berta",
      status: "consent",
      created_at: "2026-08-17T10:00:00Z",
      consent_until: "2026-08-17T11:00:00Z",
      last_activity_at: "2026-08-17T10:00:00Z",
      veto_count: 1,
      yes_votes: 0,
      no_votes: 0,
      abstain_votes: 0,
      remaining_seconds: 60,
      viewer_participation: {
        vote_choice: null,
        has_veto: false,
        may_vote: false,
        may_veto: false,
      },
    };
    const listProposals = vi
      .fn<() => Promise<Proposal[]>>()
      .mockResolvedValueOnce([baseProposal])
      .mockResolvedValueOnce([
        {
          ...baseProposal,
          status: "voting",
          voting_until: "2026-08-24T11:00:00Z",
          last_activity_at: "2026-08-17T11:00:00Z",
          remaining_seconds: 604_800,
          viewer_participation: {
            vote_choice: null,
            has_veto: false,
            may_vote: true,
            may_veto: false,
          },
        },
      ]);
    const listDirectConversations = vi.fn(async () => [] as DirectConversation[]);
    const controller = createAccountAttentionController({
      getAuthStatus: () => current,
      checkAuth: vi.fn(async () => current),
      listDirectConversations,
      listProposals,
    });

    await controller.refresh(current);
    expect(get(controller).items).toEqual([]);

    await controller.refreshProposals(current);
    expect(get(controller).items.map((item) => item.id)).toEqual([
      "proposal:phase-change",
    ]);
    expect(listProposals).toHaveBeenCalledTimes(2);
    expect(listDirectConversations).toHaveBeenCalledTimes(1);
  });

  it("invalidates account attention after a successful governance message", async () => {
    const revisions: number[] = [];
    const unsubscribe = accountAttentionInvalidation.subscribe((value) =>
      revisions.push(value),
    );
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            id: "message-1",
            author_account_id: "account-a",
            author_title: "Anna",
            body: "Neu",
            created_at: "2026-08-23T08:00:00Z",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    try {
      const before = revisions.at(-1) ?? 0;
      await postProposalMessage("proposal-1", "Neu");
      expect(revisions.at(-1)).toBe(before + 1);
    } finally {
      unsubscribe();
    }
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
