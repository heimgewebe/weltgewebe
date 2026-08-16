import { describe, expect, it } from "vitest";
import type { ProposalDetail } from "$lib/api/governance";
import { deriveProposalProcess } from "./proposalProcess";

function proposal(
  status: ProposalDetail["status"],
  overrides: Partial<ProposalDetail> = {},
): ProposalDetail {
  return {
    id: "11111111-1111-4111-8111-111111111111",
    kind: "weberantrag",
    webgemeindezentrum_id: "webgemeindezentrum-hammer-park",
    applicant_account_id: "guest-1",
    applicant_title: "Gast",
    status,
    created_at: "2026-07-14T10:00:00Z",
    consent_until: "2026-07-21T10:00:00Z",
    voting_until: status === "voting" ? "2026-07-28T10:00:00Z" : undefined,
    veto_count: 0,
    yes_votes: 0,
    no_votes: 0,
    abstain_votes: 0,
    vetoes: [],
    ...overrides,
  };
}

describe("proposal process", () => {
  it("shows the direct consent path without inventing a voting phase", () => {
    const process = deriveProposalProcess(proposal("consent"), 1);

    expect(process.steps.map(({ id, state }) => ({ id, state }))).toEqual([
      { id: "filed", state: "complete" },
      { id: "consent", state: "current" },
      { id: "decision", state: "upcoming" },
    ]);
    expect(process.showVotes).toBe(false);
    expect(process.messageCount).toBe(1);
  });

  it("shows the upcoming voting phase as soon as a veto exists", () => {
    const process = deriveProposalProcess(
      proposal("consent", { veto_count: 1 }),
      2,
    );

    expect(process.steps.map(({ id, state }) => ({ id, state }))).toEqual([
      { id: "filed", state: "complete" },
      { id: "consent", state: "current" },
      { id: "voting", state: "upcoming" },
      { id: "decision", state: "upcoming" },
    ]);
  });

  it("makes the veto-triggered voting phase explicit", () => {
    const process = deriveProposalProcess(
      proposal("voting", {
        veto_count: 2,
        yes_votes: 3,
        no_votes: 1,
        abstain_votes: 2,
      }),
      4,
    );

    expect(process.steps.at(-2)).toEqual({
      id: "voting",
      label: "Gespräch und Abstimmung",
      state: "current",
    });
    expect(process.voteCount).toBe(6);
    expect(process.showVotes).toBe(true);
  });

  it("preserves the completed voting path after a decision", () => {
    const process = deriveProposalProcess(
      proposal("accepted", { veto_count: 1, yes_votes: 2 }),
      0,
    );

    expect(process.steps.map((step) => step.id)).toEqual([
      "filed",
      "consent",
      "voting",
      "decision",
    ]);
    expect(process.steps.at(-1)).toEqual({
      id: "decision",
      label: "Angenommen",
      state: "current",
    });
  });

  it("keeps a completed voting step when persisted votes prove that path", () => {
    const process = deriveProposalProcess(
      proposal("accepted", { veto_count: 0, yes_votes: 2 }),
      0,
    );

    expect(process.steps.map((step) => step.id)).toContain("voting");
    expect(process.showVotes).toBe(true);
  });

  it("shows withdrawal as final without inventing a voting phase from an unused veto", () => {
    const process = deriveProposalProcess(
      proposal("withdrawn", {
        veto_count: 1,
        finalized_at: "2026-07-18T10:00:00Z",
      }),
      3,
    );

    expect(process.steps.map((step) => step.id)).toEqual([
      "filed",
      "consent",
      "decision",
    ]);
    expect(process.steps.at(-1)).toEqual({
      id: "decision",
      label: "Zurückgezogen",
      state: "current",
    });
    expect(process.summary).toContain("zurückgezogen");
  });

  it("describes accepted Sachantraege as decisions rather than Weber promotion", () => {
    const process = deriveProposalProcess(
      proposal("accepted", {
        kind: "sachantrag",
        title: "Werkstattzeiten",
        finalized_at: "2026-07-21T10:00:00Z",
      }),
      0,
    );

    expect(process.summary).toContain("gemeinschaftlicher Beschluss");
    expect(process.summary).not.toContain("Weberstatus");
  });

  it("makes an accepted repeal proposal explicit", () => {
    const process = deriveProposalProcess(
      proposal("accepted", {
        kind: "sachantrag",
        title: "Aufhebung: Werkstattzeiten",
        repeals_proposal_id: "old-proposal",
        finalized_at: "2026-07-21T10:00:00Z",
      }),
      0,
    );

    expect(process.summary).toContain("Aufhebungsantrag wurde angenommen");
  });

  it("does not publish a partial vote total when one count is malformed", () => {
    const process = deriveProposalProcess(
      proposal("voting", {
        yes_votes: 4,
        no_votes: Number.NaN,
        abstain_votes: 2,
      }),
      0,
    );

    expect(process.voteCount).toBe(0);
  });

  it("fails closed when individually valid counts overflow in combination", () => {
    const process = deriveProposalProcess(
      proposal("voting", {
        yes_votes: Number.MAX_SAFE_INTEGER,
        no_votes: 1,
      }),
      0,
    );

    expect(process.voteCount).toBe(0);
  });

  it("fails closed to zero for malformed visible counts", () => {
    const malformed = proposal("voting", {
      veto_count: Number.NaN,
      yes_votes: Number.POSITIVE_INFINITY,
      no_votes: -1,
      abstain_votes: 1.5,
    });

    expect(deriveProposalProcess(malformed, Number.NaN)).toMatchObject({
      vetoCount: 0,
      messageCount: 0,
      voteCount: 0,
    });
  });
});
