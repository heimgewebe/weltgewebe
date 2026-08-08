import type { DirectConversation } from "$lib/api/directMessages";
import type { Proposal } from "$lib/api/governance";

export function hasPendingWeberApplication(
  proposals: Proposal[],
  accountId: string | undefined,
): boolean {
  if (!accountId) return false;
  return proposals.some(
    (proposal) =>
      proposal.kind === "weberantrag" &&
      proposal.applicant_account_id === accountId &&
      (proposal.status === "consent" || proposal.status === "voting"),
  );
}

export function countUnreadDirectMessages(
  conversations: DirectConversation[],
): number {
  return conversations.reduce(
    (sum, conversation) => sum + Math.max(0, conversation.unread_count),
    0,
  );
}

export function unreadMessageBadgeLabel(count: number): string {
  return count > 99 ? "99+" : String(Math.max(0, count));
}
