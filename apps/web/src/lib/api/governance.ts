import { invalidateAccountAttention } from "$lib/accountAttention";

export type ProposalStatus =
  | "consent"
  | "voting"
  | "accepted"
  | "rejected"
  | "withdrawn";
export type VoteChoice = "ja" | "nein" | "enthaltung";

export interface ProposalViewerParticipation {
  vote_choice: VoteChoice | null;
  has_veto: boolean;
  may_vote: boolean;
  may_veto: boolean;
}

export interface Proposal {
  id: string;
  kind: "weberantrag" | "sachantrag";
  webgemeindezentrum_id: string;
  title?: string;
  target_node_id?: string;
  target_node_title?: string;
  repeals_proposal_id?: string;
  pending_repeal_proposal_id?: string;
  repealed_by_proposal_id?: string;
  repealed_at?: string;
  applicant_account_id: string | null;
  applicant_title: string;
  summary?: string;
  status: ProposalStatus;
  created_at: string;
  consent_until: string;
  voting_until?: string;
  finalized_at?: string;
  /** Kanonische letzte öffentliche Fachaktivität; vom Server abgeleitet. */
  last_activity_at?: string;
  veto_count: number;
  message_count?: number;
  yes_votes: number;
  no_votes: number;
  abstain_votes: number;
  remaining_seconds?: number;
  viewer_participation?: ProposalViewerParticipation | null;
  own_vote?: VoteChoice;
  /** @deprecated Transitional list-response compatibility; use viewer_participation. */
  own_veto?: boolean;
  /** @deprecated Transitional list-response compatibility; use viewer_participation. */
  can_vote?: boolean;
  /** @deprecated Transitional list-response compatibility; use viewer_participation. */
  can_veto?: boolean;
}

export interface Veto {
  weber_account_id: string;
  weber_title: string;
  reason: string;
  created_at: string;
}

export interface ProposalDetail extends Proposal {
  vetoes: Veto[];
}

export interface ProposalMessage {
  id: string;
  author_account_id: string | null;
  author_title: string;
  body: string;
  created_at: string;
}

export class GovernanceApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "GovernanceApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: "include",
    ...init,
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const message = (await response.text()).trim() || `HTTP ${response.status}`;
    throw new GovernanceApiError(response.status, message);
  }
  return response.json() as Promise<T>;
}

export function listProposals(signal?: AbortSignal): Promise<Proposal[]> {
  return request<Proposal[]>("/api/proposals", { signal });
}

export function getProposal(id: string): Promise<ProposalDetail> {
  return request<ProposalDetail>(`/api/proposals/${encodeURIComponent(id)}`);
}

export async function createWeberProposal(
  summary?: string,
  webgemeindezentrumId?: string,
): Promise<Proposal> {
  const proposal = await request<Proposal>("/api/proposals", {
    method: "POST",
    body: JSON.stringify({
      kind: "weberantrag",
      ...(summary?.trim() ? { summary: summary.trim() } : {}),
      ...(webgemeindezentrumId
        ? { webgemeindezentrum_id: webgemeindezentrumId }
        : {}),
    }),
  });
  invalidateAccountAttention();
  return proposal;
}

export async function createSachProposal(
  title: string,
  summary?: string,
  webgemeindezentrumId?: string,
  targetNodeId?: string,
): Promise<Proposal> {
  const proposal = await request<Proposal>("/api/proposals", {
    method: "POST",
    body: JSON.stringify({
      kind: "sachantrag",
      title: title.trim(),
      ...(summary?.trim() ? { summary: summary.trim() } : {}),
      ...(webgemeindezentrumId
        ? { webgemeindezentrum_id: webgemeindezentrumId }
        : {}),
      ...(targetNodeId ? { target_node_id: targetNodeId } : {}),
    }),
  });
  invalidateAccountAttention();
  return proposal;
}

export async function withdrawProposal(id: string): Promise<Proposal> {
  const proposal = await request<Proposal>(
    `/api/proposals/${encodeURIComponent(id)}/withdraw`,
    { method: "POST" },
  );
  invalidateAccountAttention();
  return proposal;
}

export async function requestProposalRepeal(
  id: string,
  summary?: string,
): Promise<Proposal> {
  const proposal = await request<Proposal>(
    `/api/proposals/${encodeURIComponent(id)}/repeal`,
    {
      method: "POST",
      body: JSON.stringify({
        ...(summary?.trim() ? { summary: summary.trim() } : {}),
      }),
    },
  );
  invalidateAccountAttention();
  return proposal;
}

export function proposalTitle(proposal: Proposal): string {
  return proposal.kind === "sachantrag"
    ? proposal.title || "Sachantrag ohne Titel"
    : `Weberstatus für ${proposal.applicant_title}`;
}

export async function submitVeto(id: string, reason: string): Promise<Veto> {
  const veto = await request<Veto>(
    `/api/proposals/${encodeURIComponent(id)}/veto`,
    {
      method: "POST",
      body: JSON.stringify({ reason: reason.trim() }),
    },
  );
  invalidateAccountAttention();
  return veto;
}

export async function submitVote(
  id: string,
  choice: VoteChoice,
): Promise<{ choice: VoteChoice }> {
  const vote = await request<{ choice: VoteChoice }>(
    `/api/proposals/${encodeURIComponent(id)}/vote`,
    {
      method: "PUT",
      body: JSON.stringify({ choice }),
    },
  );
  invalidateAccountAttention();
  return vote;
}

export function listProposalMessages(id: string): Promise<ProposalMessage[]> {
  return request<ProposalMessage[]>(
    `/api/proposals/${encodeURIComponent(id)}/messages`,
  );
}

export async function postProposalMessage(
  id: string,
  body: string,
): Promise<ProposalMessage> {
  const message = await request<ProposalMessage>(
    `/api/proposals/${encodeURIComponent(id)}/messages`,
    {
      method: "POST",
      body: JSON.stringify({ body: body.trim() }),
    },
  );
  invalidateAccountAttention();
  return message;
}

export type GuestExitResult =
  | { status: "exited" }
  | { status: "step-up-required"; challengeId: string };

export async function exitGuestAccount(): Promise<GuestExitResult> {
  const response = await fetch("/api/accounts/me/exit", {
    method: "POST",
    credentials: "include",
  });
  const responseText = (await response.text()).trim();

  // Rolling-deploy compatibility: an older API may still complete the exit
  // directly. Treat that as terminal instead of trying to request a challenge
  // for an account that has already been deleted.
  if (response.ok) return { status: "exited" };

  let payload: { error?: unknown; challenge_id?: unknown } | null = null;
  if (responseText) {
    try {
      payload = JSON.parse(responseText) as {
        error?: unknown;
        challenge_id?: unknown;
      };
    } catch {
      payload = null;
    }
  }

  if (
    response.status === 403 &&
    payload?.error === "STEP_UP_REQUIRED" &&
    typeof payload.challenge_id === "string" &&
    payload.challenge_id
  ) {
    return {
      status: "step-up-required",
      challengeId: payload.challenge_id,
    };
  }

  throw new GovernanceApiError(
    response.status,
    responseText || `HTTP ${response.status}`,
  );
}

export async function requestGuestExitStepUp(
  challengeId: string,
): Promise<void> {
  const response = await fetch("/api/auth/step-up/magic-link/request", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ challenge_id: challengeId }),
  });
  if (!response.ok) {
    const message = (await response.text()).trim() || `HTTP ${response.status}`;
    throw new GovernanceApiError(response.status, message);
  }
}

export function formatRemaining(seconds?: number): string {
  if (seconds === undefined) return "abgeschlossen";
  const clamped = Math.max(0, seconds);
  const days = Math.floor(clamped / 86_400);
  const hours = Math.floor((clamped % 86_400) / 3_600);
  if (days > 0) return `${days} T. ${hours} Std.`;
  const minutes = Math.floor((clamped % 3_600) / 60);
  if (hours > 0) return `${hours} Std. ${minutes} Min.`;
  return `${minutes} Min.`;
}

export function statusLabel(status: ProposalStatus): string {
  switch (status) {
    case "consent":
      return "Offene Konsentphase";
    case "voting":
      return "Gespräch und Abstimmung";
    case "accepted":
      return "Angenommen";
    case "rejected":
      return "Abgelehnt";
    case "withdrawn":
      return "Zurückgezogen";
  }
}

export function proposalStatusLabel(
  proposal: Pick<
    Proposal,
    "status" | "pending_repeal_proposal_id" | "repealed_by_proposal_id"
  >,
): string {
  if (proposal.status === "accepted") {
    if (proposal.repealed_by_proposal_id) return "Aufgehoben";
    if (proposal.pending_repeal_proposal_id)
      return "Angenommen · Aufhebung läuft";
  }
  return statusLabel(proposal.status);
}
