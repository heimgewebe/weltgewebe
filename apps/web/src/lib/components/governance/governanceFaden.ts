import type { ProposalDetail, ProposalMessage } from "$lib/api/governance";

export interface GovernanceFadenSummary {
  proposal: 1;
  vetoes: number;
  messages: number;
  votes: number;
  total: number;
}

/**
 * Derive the visible governance-thread counts exclusively from canonical
 * proposal data. The visualisation never creates or persists a domain edge.
 */
export function deriveGovernanceFadenSummary(
  proposal: ProposalDetail,
  messages: ProposalMessage[],
): GovernanceFadenSummary {
  const vetoes = proposal.vetoes.length;
  const votes = proposal.yes_votes + proposal.no_votes + proposal.abstain_votes;
  const messageCount = messages.length;

  return {
    proposal: 1,
    vetoes,
    messages: messageCount,
    votes,
    total: 1 + vetoes + messageCount + votes,
  };
}

/**
 * Return a bounded set of parallel offsets for an SVG thread bundle. Large
 * communities stay cheap to render; the exact count remains visible as text.
 */
export function visibleStrandOffsets(count: number, maximum = 7): number[] {
  const visible = Math.min(Math.max(0, Math.trunc(count)), maximum);
  if (visible === 0) return [];
  if (visible === 1) return [0];

  const spacing = 5;
  const start = -((visible - 1) * spacing) / 2;
  return Array.from({ length: visible }, (_, index) => start + index * spacing);
}
