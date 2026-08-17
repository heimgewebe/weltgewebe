import type { DirectConversation } from "$lib/api/directMessages";
import type { Proposal } from "$lib/api/governance";
import type { AuthRole } from "$lib/auth/store";

const UNREAD_COUNT_OVERFLOW = 100;

export type AttentionItemKind =
  | "direct_message"
  | "weber_application"
  | "governance";

export interface AttentionItem {
  id: string;
  kind: AttentionItemKind;
  label: string;
  detail: string;
  href: string;
  occurredAt: string;
  count?: number;
}

export interface AttentionProjectionInput {
  conversations: DirectConversation[];
  proposals: Proposal[];
  accountId?: string;
  role: AuthRole;
}

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

function proposalLabel(proposal: Proposal): string {
  if (proposal.kind === "sachantrag") {
    return proposal.title?.trim() || "Sachantrag ohne Titel";
  }
  return `Weberstatus für ${proposal.applicant_title}`;
}

function proposalDetail(proposal: Proposal): string {
  return proposal.status === "voting"
    ? "Gespräch und Abstimmung läuft"
    : "Offene Konsentphase";
}

function sourceTime(value: string): number {
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : Number.NEGATIVE_INFINITY;
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

export function unreadMessageAccessibleCount(count: number): string {
  const bounded = boundedUnreadCount(count);
  if (bounded >= UNREAD_COUNT_OVERFLOW) {
    return "99 oder mehr ungelesene Nachrichten";
  }
  if (bounded === 1) return "1 ungelesene Nachricht";
  return `${bounded} ungelesene Nachrichten`;
}

export function projectTopBarAttention({
  conversations,
  proposals,
  accountId,
  role,
}: AttentionProjectionInput): AttentionItem[] {
  if (!accountId) return [];

  const items: AttentionItem[] = [];

  for (const conversation of conversations) {
    const unread = boundedUnreadCount(conversation.unread_count);
    if (unread === 0) continue;
    const occurredAt = conversation.last_message_at ?? conversation.updated_at;
    if (!occurredAt) continue;
    items.push({
      id: `direct:${conversation.id}`,
      kind: "direct_message",
      label: conversation.counterpart_title || "Private Nachricht",
      detail: unreadMessageAccessibleCount(unread),
      href: `/nachrichten?id=${encodeURIComponent(conversation.id)}`,
      occurredAt,
      count: unread,
    });
  }

  const canParticipateCollectively = role === "weber" || role === "admin";
  for (const proposal of proposals) {
    if (proposal.status !== "consent" && proposal.status !== "voting") continue;

    const ownApplication = isOwnWeberApplication(proposal, accountId);
    if (!ownApplication && !canParticipateCollectively) continue;
    if (!proposal.created_at) continue;

    items.push({
      id: `proposal:${proposal.id}`,
      kind: ownApplication ? "weber_application" : "governance",
      label: ownApplication ? "Dein Weberantrag" : proposalLabel(proposal),
      detail: proposalDetail(proposal),
      href: `/antraege?id=${encodeURIComponent(proposal.id)}`,
      occurredAt: proposal.created_at,
    });
  }

  return items.sort((left, right) => {
    const byTime = sourceTime(right.occurredAt) - sourceTime(left.occurredAt);
    return byTime || left.id.localeCompare(right.id);
  });
}
