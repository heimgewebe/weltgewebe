import type { DirectConversation } from "$lib/api/directMessages";
import type { Proposal } from "$lib/api/governance";

const UNREAD_COUNT_OVERFLOW = 100;

function isOwnWeberApplication(proposal: Proposal, accountId: string): boolean {
  return (
    proposal.kind === "weberantrag" &&
    proposal.applicant_account_id === accountId
  );
}

function boundedUnreadCount(value: number): number {
  if (!Number.isFinite(value) || !Number.isInteger(value) || value <= 0) {
    return 0;
  }
  return Math.min(value, UNREAD_COUNT_OVERFLOW);
}

export function hasPendingWeberApplication(
  proposals: Proposal[],
  accountId: string | undefined,
): boolean {
  if (!accountId) return false;
  return proposals.some(
    (proposal) =>
      isOwnWeberApplication(proposal, accountId) &&
      (proposal.status === "consent" || proposal.status === "voting"),
  );
}

export function hasAcceptedWeberApplication(
  proposals: Proposal[],
  accountId: string | undefined,
): boolean {
  if (!accountId) return false;
  return proposals.some(
    (proposal) =>
      isOwnWeberApplication(proposal, accountId) &&
      proposal.status === "accepted",
  );
}

export function countUnreadDirectMessages(
  conversations: DirectConversation[],
): number {
  return conversations.reduce(
    (sum, conversation) =>
      Math.min(
        UNREAD_COUNT_OVERFLOW,
        sum + boundedUnreadCount(conversation.unread_count),
      ),
    0,
  );
}

export function unreadMessageBadgeLabel(count: number): string {
  const bounded = boundedUnreadCount(count);
  return bounded >= UNREAD_COUNT_OVERFLOW ? "99+" : String(bounded);
}
