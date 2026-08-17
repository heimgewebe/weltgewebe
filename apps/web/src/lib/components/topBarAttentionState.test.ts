import { describe, expect, it } from "vitest";
import type { DirectConversation } from "$lib/api/directMessages";
import type { Proposal } from "$lib/api/governance";
import {
  attentionMeaningLabel,
  countUnreadDirectMessages,
  hasAcceptedWeberApplication,
  hasPendingWeberApplication,
  projectTopBarAttention,
  unreadMessageAccessibleCount,
  unreadMessageBadgeLabel,
} from "./topBarAttentionState";

function conversation(
  id: string,
  unreadCount: number,
  at: string,
): DirectConversation {
  return {
    id,
    counterpart_account_id: `counterpart-${id}`,
    counterpart_title: `Person ${id}`,
    created_at: at,
    updated_at: at,
    unread_count: unreadCount,
    last_message_preview: `Nachricht ${id}`,
    last_message_at: at,
    blocked_by_me: false,
    can_send: true,
  };
}

function proposal(overrides: Partial<Proposal> = {}): Proposal {
  return {
    id: "proposal-1",
    kind: "sachantrag",
    webgemeindezentrum_id: "wgz-test",
    title: "Parkbank",
    applicant_account_id: "weber-b",
    applicant_title: "Berta",
    status: "consent",
    created_at: "2026-08-17T06:00:00Z",
    consent_until: "2026-08-24T06:00:00Z",
    veto_count: 0,
    yes_votes: 0,
    no_votes: 0,
    abstain_votes: 0,
    ...overrides,
  };
}

describe("topBarAttentionState", () => {
  it("recognizes only the current guest's active Weber application", () => {
    const proposals = [
      proposal({
        kind: "weberantrag",
        applicant_account_id: "guest-a",
        status: "consent",
      }),
      proposal({
        id: "proposal-2",
        kind: "weberantrag",
        applicant_account_id: "guest-b",
        status: "voting",
      }),
      proposal({
        id: "proposal-3",
        kind: "weberantrag",
        applicant_account_id: "guest-a",
        status: "accepted",
      }),
    ];

    expect(hasPendingWeberApplication(proposals, "guest-a")).toBe(true);
    expect(hasPendingWeberApplication(proposals, "guest-c")).toBe(false);
    expect(hasPendingWeberApplication(proposals, undefined)).toBe(false);
  });

  it("recognizes an accepted application only for its own account", () => {
    const proposals = [
      proposal({
        kind: "weberantrag",
        applicant_account_id: "guest-a",
        status: "accepted",
      }),
      proposal({
        id: "proposal-2",
        kind: "weberantrag",
        applicant_account_id: "guest-b",
        status: "rejected",
      }),
    ];

    expect(hasAcceptedWeberApplication(proposals, "guest-a")).toBe(true);
    expect(hasAcceptedWeberApplication(proposals, "guest-b")).toBe(false);
    expect(hasAcceptedWeberApplication(proposals, undefined)).toBe(false);
  });

  it("rejects malformed unread counts before summing", () => {
    const conversations = [
      { unread_count: 2 },
      { unread_count: 3 },
      { unread_count: -1 },
      { unread_count: Number.POSITIVE_INFINITY },
      { unread_count: 1.5 },
    ] as DirectConversation[];

    expect(countUnreadDirectMessages(conversations)).toBe(5);
  });

  it("saturates unread totals at the 99+ display boundary", () => {
    const conversations = [
      { unread_count: 80 },
      { unread_count: 40 },
    ] as DirectConversation[];

    expect(countUnreadDirectMessages(conversations)).toBe(100);
  });

  it("caps and announces unread totals safely", () => {
    expect(unreadMessageBadgeLabel(4)).toBe("4");
    expect(unreadMessageBadgeLabel(100)).toBe("99+");
    expect(unreadMessageBadgeLabel(Number.POSITIVE_INFINITY)).toBe("0");
    expect(unreadMessageAccessibleCount(1)).toBe("1 ungelesene Nachricht");
    expect(unreadMessageAccessibleCount(4)).toBe("4 ungelesene Nachrichten");
    expect(unreadMessageAccessibleCount(100)).toBe(
      "99 oder mehr ungelesene Nachrichten",
    );
  });

  it("keeps the four display meanings explicit and human-readable", () => {
    expect(attentionMeaningLabel("required")).toBe("Handlung erforderlich");
    expect(attentionMeaningLabel("new")).toBe("Neu für dich");
    expect(attentionMeaningLabel("available")).toBe("Mitwirkung möglich");
    expect(attentionMeaningLabel("waiting")).toBe("Läuft ohne dein Zutun");
  });

  it("projects unread direct conversations as new personal attention", () => {
    const items = projectTopBarAttention({
      accountId: "weber-a",
      role: "weber",
      conversations: [
        conversation("conversation-1", 4, "2026-08-17T07:00:00Z"),
      ],
      proposals: [],
    });

    expect(items).toHaveLength(1);
    expect(items[0]).toMatchObject({
      id: "direct:conversation-1",
      kind: "direct_message",
      meaning: "new",
      count: 4,
      href: "/nachrichten?id=conversation-1",
    });
  });

  it("orders by semantic meaning before recency and by recency inside a meaning", () => {
    const items = projectTopBarAttention({
      accountId: "weber-a",
      role: "weber",
      conversations: [
        conversation("older-new", 1, "2026-08-17T05:00:00Z"),
        conversation("newer-new", 1, "2026-08-17T07:00:00Z"),
      ],
      proposals: [
        proposal({
          id: "available-newer-than-messages",
          can_veto: true,
          created_at: "2026-08-17T08:00:00Z",
        }),
        proposal({
          id: "own-waiting-newest",
          applicant_account_id: "weber-a",
          created_at: "2026-08-17T09:00:00Z",
        }),
      ],
    });

    expect(items.map((item) => `${item.meaning}:${item.id}`)).toEqual([
      "new:direct:newer-new",
      "new:direct:older-new",
      "available:proposal:available-newer-than-messages",
      "waiting:proposal:own-waiting-newest",
    ]);
  });

  it("projects every own open proposal once as waiting, including Sachanträge", () => {
    const items = projectTopBarAttention({
      accountId: "weber-a",
      role: "weber",
      conversations: [],
      proposals: [
        proposal({
          id: "own-weber",
          kind: "weberantrag",
          applicant_account_id: "weber-a",
          applicant_title: "Ada",
          status: "voting",
          consent_until: "2026-08-17T07:00:00Z",
          voting_until: "2026-08-24T07:00:00Z",
          can_vote: false,
        }),
        proposal({
          id: "own-sach",
          applicant_account_id: "weber-a",
          title: "Gemeinschaftsgarten",
          can_veto: false,
        }),
      ],
    });

    expect(items).toHaveLength(2);
    expect(items).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: "proposal:own-weber",
          kind: "weber_application",
          meaning: "waiting",
          label: "Dein Weberantrag",
          occurredAt: "2026-08-17T07:00:00Z",
        }),
        expect.objectContaining({
          id: "proposal:own-sach",
          kind: "own_proposal",
          meaning: "waiting",
          label: "Dein Antrag: Gemeinschaftsgarten",
        }),
      ]),
    );
  });

  it("projects a still-open vote only when the server proves personal participation is available", () => {
    const [item] = projectTopBarAttention({
      accountId: "weber-a",
      role: "weber",
      conversations: [],
      proposals: [
        proposal({
          id: "vote-proposal",
          status: "voting",
          consent_until: "2026-08-17T07:00:00Z",
          voting_until: "2026-08-24T07:00:00Z",
          can_vote: true,
        }),
      ],
    });

    expect(item).toMatchObject({
      id: "proposal:vote-proposal",
      kind: "governance",
      meaning: "available",
      detail: "Du kannst noch abstimmen",
      occurredAt: "2026-08-17T07:00:00Z",
      deadline: "2026-08-24T07:00:00Z",
    });
  });

  it("removes voting attention after the canonical list reports an own vote", () => {
    const items = projectTopBarAttention({
      accountId: "weber-a",
      role: "weber",
      conversations: [],
      proposals: [
        proposal({
          status: "voting",
          voting_until: "2026-08-24T07:00:00Z",
          can_vote: true,
          own_vote: "ja",
        }),
      ],
    });

    expect(items).toEqual([]);
  });

  it("projects an open consent only when a fresh veto is actually available", () => {
    const [item] = projectTopBarAttention({
      accountId: "weber-a",
      role: "weber",
      conversations: [],
      proposals: [proposal({ can_veto: true })],
    });

    expect(item).toMatchObject({
      meaning: "available",
      detail: "Du kannst ein begründetes Veto einlegen",
    });
  });

  it("does not infer personal governance attention from role or phase alone", () => {
    const items = projectTopBarAttention({
      accountId: "weber-a",
      role: "weber",
      conversations: [],
      proposals: [
        proposal({ status: "consent" }),
        proposal({
          id: "vote",
          status: "voting",
          voting_until: "2026-08-24T07:00:00Z",
        }),
      ],
    });

    expect(items).toEqual([]);
  });

  it("masks stale server participation immediately after a role downgrade", () => {
    const items = projectTopBarAttention({
      accountId: "guest-a",
      role: "gast",
      conversations: [],
      proposals: [proposal({ can_veto: true, can_vote: true })],
    });

    expect(items).toEqual([]);
  });

  it("uses the stable id as a final tie-breaker", () => {
    const items = projectTopBarAttention({
      accountId: "weber-a",
      role: "weber",
      conversations: [
        conversation("zeta", 1, "2026-08-17T07:00:00Z"),
        conversation("alpha", 1, "2026-08-17T07:00:00Z"),
      ],
      proposals: [],
    });

    expect(items.map((item) => item.id)).toEqual([
      "direct:alpha",
      "direct:zeta",
    ]);
  });
});
