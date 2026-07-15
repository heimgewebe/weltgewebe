export type ProposalStatus = "consent" | "voting" | "accepted" | "rejected";
export type VoteChoice = "ja" | "nein" | "enthaltung";

export interface Proposal {
  id: string;
  kind: "weberantrag";
  applicant_account_id: string;
  applicant_title: string;
  summary?: string;
  status: ProposalStatus;
  created_at: string;
  consent_until: string;
  voting_until?: string;
  finalized_at?: string;
  veto_count: number;
  yes_votes: number;
  no_votes: number;
  abstain_votes: number;
  remaining_seconds?: number;
}

export interface Veto {
  weber_account_id: string;
  weber_title: string;
  reason: string;
  created_at: string;
}

export interface ProposalDetail extends Proposal {
  vetoes: Veto[];
  own_vote?: VoteChoice;
}

export interface ProposalMessage {
  id: string;
  author_account_id: string;
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

export function listProposals(): Promise<Proposal[]> {
  return request<Proposal[]>("/api/proposals");
}

export function getProposal(id: string): Promise<ProposalDetail> {
  return request<ProposalDetail>(`/api/proposals/${encodeURIComponent(id)}`);
}

export function createWeberProposal(summary?: string): Promise<Proposal> {
  return request<Proposal>("/api/proposals", {
    method: "POST",
    body: JSON.stringify({
      kind: "weberantrag",
      ...(summary?.trim() ? { summary: summary.trim() } : {}),
    }),
  });
}

export function submitVeto(id: string, reason: string): Promise<Veto> {
  return request<Veto>(`/api/proposals/${encodeURIComponent(id)}/veto`, {
    method: "POST",
    body: JSON.stringify({ reason: reason.trim() }),
  });
}

export function submitVote(
  id: string,
  choice: VoteChoice,
): Promise<{ choice: VoteChoice }> {
  return request<{ choice: VoteChoice }>(
    `/api/proposals/${encodeURIComponent(id)}/vote`,
    {
      method: "PUT",
      body: JSON.stringify({ choice }),
    },
  );
}

export function listProposalMessages(id: string): Promise<ProposalMessage[]> {
  return request<ProposalMessage[]>(
    `/api/proposals/${encodeURIComponent(id)}/messages`,
  );
}

export function postProposalMessage(
  id: string,
  body: string,
): Promise<ProposalMessage> {
  return request<ProposalMessage>(
    `/api/proposals/${encodeURIComponent(id)}/messages`,
    {
      method: "POST",
      body: JSON.stringify({ body: body.trim() }),
    },
  );
}

export function exitGuestAccount(): Promise<{ status: "exited" }> {
  return request<{ status: "exited" }>("/api/accounts/me/exit", {
    method: "POST",
  });
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
  }
}
