import { describe, expect, it } from "vitest";
import type { DirectConversation } from "$lib/api/directMessages";
import type { Proposal } from "$lib/api/governance";
import {
  countUnreadDirectMessages,
  hasAcceptedWeberApplication,
  hasPendingWeberApplication,
  projectTopBarAttention,
  unreadMessageAccessibleCount,
  unreadMessageBadgeLabel,
} from "./topBarAttentionState";

describe("topBarAttentionState", () => {
  it("recognizes only the current guest's active Weber application", () => {
    const proposals = [
      {
        kind: "weberantrag",
        applicant_account_id: "guest-a",
        status: "consent",
      },
      {
        kind: "weberantrag",
        applicant_account_id: "guest-b",
        status: "voting",
      },
      {
        kind: "weberantrag",
        applicant_account_id: "guest-a",
        status: "accepted",
      },
    ] as Proposal[];

    expect(hasPendingWeberApplication(proposals, "guest-a")).toBe(true);
    expect(hasPendingWeberApplication(proposals, "guest-c")).toBe(false);
    expect(hasPendingWeberApplication(proposals, undefined)).toBe(false);
  });

  it("recognizes an accepted application only for its own account", () => {
    const proposals = [
      {
        kind: "weberantrag",
        applicant_account_id: "guest-a",
        status: "accepted",
      },
      {
        kind: "weberantrag",
        applicant_account_id: "guest-b",
        status: "rejected",
      },
    ] as Proposal[];

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

  it("caps the compact badge at 99+ and rejects non-finite totals", () => {
    expect(unreadMessageBadgeLabel(4)).toBe("4");
    expect(unreadMessageBadgeLabel(100)).toBe("99+");
    expect(unreadMessageBadgeLabel(Number.POSITIVE_INFINITY)).toBe("0");
  });

  it("announces a saturated unread total as a lower bound", () => {
    expect(unreadMessageAccessibleCount(1)).toBe("1 ungelesene Nachricht");
    expect(unreadMessageAccessibleCount(4)).toBe("4 ungelesene Nachrichten");
    expect(unreadMessageAccessibleCount(100)).toBe(
      "99 oder mehr ungelesene Nachrichten",
    );
  });

  it("projects newest attention first using source timestamps", () => {
    const items = projectTopBarAttention({
      accountId: "weber-a",
      role: "weber",
      conversations: [
        {
          id: "older-message",
          counterpart_title: "Ada",
          unread_count: 2,
          updated_at: "2026-08-17T05:00:00Z",
          last_message_at: "2026-08-17T05:00:00Z",
        },
        {
          id: "newer-message",
          counterpart_title: "Berta",
          unread_count: 1,
          updated_at: "2026-08-17T07:00:00Z",
          last_message_at: "2026-08-17T07:00:00Z",
        },
      ] as DirectConversation[],
      proposals: [
        {
          id: "middle-proposal",
          kind: "sachantrag",
          title: "Gemeinschaftsgarten",
          applicant_account_id: "weber-b",
          applicant_title: "Berta",
          status: "consent",
          created_at: "2026-08-17T06:00:00Z",
        },
      ] as Proposal[],
    });

    expect(items.map((item) => item.id)).toEqual([
      "direct:newer-message",
      "proposal:middle-proposal",
      "direct:older-message",
    ]);
  });

  it("aggregates one direct conversation into one bubble with its unread count", () => {
    const items = projectTopBarAttention({
      accountId: "weber-a",
      role: "weber",
      conversations: [
        {
          id: "conversation-1",
          counterpart_title: "Ada",
          unread_count: 4,
          updated_at: "2026-08-17T07:00:00Z",
          last_message_at: "2026-08-17T07:00:00Z",
        },
      ] as DirectConversation[],
      proposals: [],
    });

    expect(items).toHaveLength(1);
    expect(items[0]).toMatchObject({
      id: "direct:conversation-1",
      kind: "direct_message",
      count: 4,
      href: "/nachrichten?id=conversation-1",
    });
  });

  it("deduplicates an own open Weber application from collective governance", () => {
    const items = projectTopBarAttention({
      accountId: "weber-a",
      role: "weber",
      conversations: [],
      proposals: [
        {
          id: "own-proposal",
          kind: "weberantrag",
          applicant_account_id: "weber-a",
          applicant_title: "Ada",
          status: "voting",
          created_at: "2026-08-17T07:00:00Z",
        },
      ] as Proposal[],
    });

    expect(items).toHaveLength(1);
    expect(items[0]).toMatchObject({
      id: "proposal:own-proposal",
      kind: "weber_application",
      label: "Dein Weberantrag",
    });
  });

  it("does not present collective proposals as guest attention", () => {
    const items = projectTopBarAttention({
      accountId: "guest-a",
      role: "gast",
      conversations: [],
      proposals: [
        {
          id: "foreign-proposal",
          kind: "sachantrag",
          title: "Parkbank",
          applicant_account_id: "weber-b",
          applicant_title: "Berta",
          status: "voting",
          created_at: "2026-08-17T07:00:00Z",
        },
      ] as Proposal[],
    });

    expect(items).toEqual([]);
  });

  it("never claims that a viewer-specific vote is missing", () => {
    const [item] = projectTopBarAttention({
      accountId: "weber-a",
      role: "weber",
      conversations: [],
      proposals: [
        {
          id: "vote-proposal",
          kind: "sachantrag",
          title: "Parkbank",
          applicant_account_id: "weber-b",
          applicant_title: "Berta",
          status: "voting",
          created_at: "2026-08-17T07:00:00Z",
        },
      ] as Proposal[],
    });

    expect(item.detail).toBe("Gespräch und Abstimmung läuft");
    expect(`${item.label} ${item.detail}`).not.toMatch(
      /deine Stimme|abstimmen/i,
    );
  });
});
