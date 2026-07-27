import { describe, expect, it } from "vitest";
import type { ProposalDetail, ProposalMessage } from "$lib/api/governance";
import {
  deriveGovernanceFadenSummary,
  visibleStrandOffsets,
} from "./governanceFaden";

const proposal: ProposalDetail = {
  id: "11111111-1111-4111-8111-111111111111",
  kind: "weberantrag",
  applicant_account_id: "guest-1",
  applicant_title: "Gast",
  status: "voting",
  created_at: "2026-07-14T10:00:00Z",
  consent_until: "2026-07-21T10:00:00Z",
  voting_until: "2026-07-28T10:00:00Z",
  veto_count: 2,
  message_count: 1,
  yes_votes: 3,
  no_votes: 1,
  abstain_votes: 2,
  vetoes: [
    {
      weber_account_id: "weber-1",
      weber_title: "Weber 1",
      reason: "Einwand 1",
      created_at: "2026-07-15T10:00:00Z",
    },
    {
      weber_account_id: "weber-2",
      weber_title: "Weber 2",
      reason: "Einwand 2",
      created_at: "2026-07-15T11:00:00Z",
    },
  ],
};

const messages: ProposalMessage[] = [
  {
    id: "message-1",
    author_account_id: "weber-1",
    author_title: "Weber 1",
    body: "Beitrag",
    created_at: "2026-07-15T12:00:00Z",
  },
];

describe("governance Faden projection", () => {
  it("derives every visible count from canonical governance records", () => {
    expect(deriveGovernanceFadenSummary(proposal, messages)).toEqual({
      proposal: 1,
      vetoes: 2,
      messages: 1,
      votes: 6,
      total: 10,
    });
  });

  it("bounds only the rendered bundle while preserving stable offsets", () => {
    expect(visibleStrandOffsets(0)).toEqual([]);
    expect(visibleStrandOffsets(1)).toEqual([0]);
    expect(visibleStrandOffsets(3)).toEqual([-5, 0, 5]);
    expect(visibleStrandOffsets(100)).toHaveLength(7);
  });
});
