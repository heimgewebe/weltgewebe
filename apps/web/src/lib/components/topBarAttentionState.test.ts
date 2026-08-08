import { describe, expect, it } from "vitest";
import type { DirectConversation } from "$lib/api/directMessages";
import type { Proposal } from "$lib/api/governance";
import {
  countUnreadDirectMessages,
  hasAcceptedWeberApplication,
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
});
