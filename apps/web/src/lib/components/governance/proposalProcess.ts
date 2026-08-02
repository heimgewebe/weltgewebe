import type { ProposalDetail } from "$lib/api/governance";

export type ProposalProcessStepState = "complete" | "current" | "upcoming";

export interface ProposalProcessStep {
  id: "filed" | "consent" | "voting" | "decision";
  label: string;
  state: ProposalProcessStepState;
}

export interface ProposalProcessModel {
  steps: ProposalProcessStep[];
  summary: string;
  deadlineLabel?: string;
  deadlineAt?: string;
  vetoCount: number;
  messageCount: number;
  voteCount: number;
  showVotes: boolean;
}

function parseSafeCount(value: unknown): number | undefined {
  return typeof value === "number" &&
    Number.isFinite(value) &&
    Number.isSafeInteger(value) &&
    value >= 0
    ? value
    : undefined;
}

function safeCount(value: unknown): number {
  return parseSafeCount(value) ?? 0;
}

function safeCountSum(...values: unknown[]): number {
  let total = 0;
  for (const value of values) {
    const count = parseSafeCount(value);
    if (count === undefined || total > Number.MAX_SAFE_INTEGER - count)
      return 0;
    total += count;
  }
  return total;
}

function decisionLabel(proposal: ProposalDetail): string {
  if (proposal.status === "accepted") return "Angenommen";
  if (proposal.status === "rejected") return "Abgelehnt";
  return "Entscheidung";
}

export function deriveProposalProcess(
  proposal: ProposalDetail,
  messageCount: unknown,
): ProposalProcessModel {
  const vetoCount = safeCount(proposal.veto_count);
  const voteCount = safeCountSum(
    proposal.yes_votes,
    proposal.no_votes,
    proposal.abstain_votes,
  );
  const normalizedMessageCount = safeCount(messageCount);
  const finalized =
    proposal.status === "accepted" || proposal.status === "rejected";
  const includesVoting =
    proposal.status === "voting" ||
    vetoCount > 0 ||
    (finalized && voteCount > 0);

  const steps: ProposalProcessStep[] = [
    { id: "filed", label: "Antrag gestellt", state: "complete" },
    {
      id: "consent",
      label: "Einspruchsfrist",
      state: proposal.status === "consent" ? "current" : "complete",
    },
  ];

  if (includesVoting) {
    steps.push({
      id: "voting",
      label: "Gespräch und Abstimmung",
      state:
        proposal.status === "voting"
          ? "current"
          : finalized
            ? "complete"
            : "upcoming",
    });
  }

  steps.push({
    id: "decision",
    label: decisionLabel(proposal),
    state: finalized ? "current" : "upcoming",
  });

  if (proposal.status === "consent") {
    return {
      steps,
      summary:
        vetoCount > 0
          ? "Mindestens ein begründetes Veto liegt vor. Nach Ende der Einspruchsfrist beginnt die Gesprächs- und Abstimmungsphase."
          : "Bis zum Fristende können berechtigte Weber ein begründetes Veto einlegen. Ohne Veto wird der Antrag anschließend angenommen.",
      deadlineLabel: "Einspruch möglich bis",
      deadlineAt: proposal.consent_until,
      vetoCount,
      messageCount: normalizedMessageCount,
      voteCount,
      showVotes: false,
    };
  }

  if (proposal.status === "voting") {
    return {
      steps,
      summary:
        "Die Einspruchsfrist ist beendet. Bis zum Fristende wird beraten und abgestimmt; angenommen wird der Antrag nur mit mehr Ja- als Nein-Stimmen.",
      deadlineLabel: "Abstimmung offen bis",
      deadlineAt: proposal.voting_until,
      vetoCount,
      messageCount: normalizedMessageCount,
      voteCount,
      showVotes: true,
    };
  }

  return {
    steps,
    summary:
      proposal.status === "accepted"
        ? "Das Verfahren ist abgeschlossen. Der Weberstatus wurde erteilt."
        : "Das Verfahren ist abgeschlossen. Der Weberstatus wurde nicht erteilt.",
    vetoCount,
    messageCount: normalizedMessageCount,
    voteCount,
    showVotes: includesVoting || voteCount > 0,
  };
}
