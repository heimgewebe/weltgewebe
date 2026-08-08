import { describe, expect, it } from "vitest";
import type { DirectConversation } from "$lib/api/directMessages";
import type { Proposal } from "$lib/api/governance";
import {
  countUnreadDirectMessages,
  hasPendingWeberApplication,
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

  it("sums unread messages without letting negative counts reduce the badge", () => {
    const conversations = [
      { unread_count: 2 },
      { unread_count: 3 },
      { unread_count: -1 },
    ] as DirectConversation[];

    expect(countUnreadDirectMessages(conversations)).toBe(5);
  });

  it("caps the compact badge at 99+", () => {
    expect(unreadMessageBadgeLabel(4)).toBe("4");
    expect(unreadMessageBadgeLabel(140)).toBe("99+");
  });
});
