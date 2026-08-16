import { expect, test, type Browser, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

type Actor = "applicant-consent" | "applicant-voting" | "weber-a" | "weber-b";
type AuthStatus = {
  authenticated: boolean;
  account_id?: string;
  role?: string;
};
type Proposal = {
  id: string;
  kind: "weberantrag" | "sachantrag";
  applicant_account_id: string | null;
  status: "consent" | "voting" | "accepted" | "rejected" | "withdrawn";
  consent_until: string;
  voting_until?: string;
  repeals_proposal_id?: string;
  pending_repeal_proposal_id?: string;
  repealed_by_proposal_id?: string;
  remaining_seconds?: number;
  yes_votes: number;
  no_votes: number;
  abstain_votes: number;
  veto_count: number;
};

type ActorSession = {
  page: Page;
  account_id: string;
  role: string;
};

async function jsonRequest<T>(
  page: Page,
  url: string,
  method: "GET" | "POST" = "GET",
  body?: unknown,
): Promise<T> {
  const result = await page.evaluate(
    async ({ requestUrl, requestMethod, requestBody }) => {
      const response = await fetch(requestUrl, {
        method: requestMethod,
        credentials: "include",
        headers:
          requestBody === undefined
            ? undefined
            : { "content-type": "application/json" },
        body:
          requestBody === undefined ? undefined : JSON.stringify(requestBody),
      });
      const text = await response.text();
      return { status: response.status, text };
    },
    { requestUrl: url, requestMethod: method, requestBody: body },
  );
  expect(
    result.status,
    `${method} ${url}: ${result.text}`,
  ).toBeGreaterThanOrEqual(200);
  expect(result.status, `${method} ${url}: ${result.text}`).toBeLessThan(300);
  return JSON.parse(result.text) as T;
}

async function bootstrapActor(
  browser: Browser,
  baseURL: string,
  runId: string,
  actor: Actor,
): Promise<ActorSession> {
  const context = await browser.newContext({ baseURL });
  const page = await context.newPage();
  await page.goto("/antraege");
  const session = await jsonRequest<{ account_id: string; role: string }>(
    page,
    "/api/auth/testing/governance/bootstrap-session",
    "POST",
    { run_id: runId, actor },
  );
  await page.reload();
  const auth = await jsonRequest<AuthStatus>(page, "/api/auth/me");
  expect(auth.authenticated).toBe(true);
  expect(auth.account_id).toBe(session.account_id);
  expect(auth.role).toBe(session.role);
  return { page, account_id: session.account_id, role: session.role };
}

async function createApplication(
  actor: ActorSession,
  summary: string,
): Promise<Proposal> {
  await actor.page.goto("/antraege");
  await actor.page
    .getByLabel("Kurze Vorstellung oder Begründung")
    .fill(summary);
  await actor.page
    .getByRole("button", { name: "Weberstatus beantragen" })
    .click();
  await expect(
    actor.page.getByText("Dein Weberantrag ist bereits offen."),
  ).toBeVisible();
  const proposals = await jsonRequest<Proposal[]>(actor.page, "/api/proposals");
  const proposal = proposals.find(
    (item) =>
      item.applicant_account_id === actor.account_id &&
      item.status === "consent",
  );
  expect(
    proposal,
    "new application must be persisted in PostgreSQL",
  ).toBeTruthy();
  return proposal as Proposal;
}

async function advance(
  page: Page,
  proposal: Proposal,
  now: string,
): Promise<Proposal> {
  return jsonRequest<Proposal>(
    page,
    `/api/governance/testing/proposals/${proposal.id}/advance`,
    "POST",
    { now },
  );
}

test("proves withdrawal, consent, veto, voting, repeal, and atomic guest-to-Weber promotion", async ({
  browser,
  baseURL,
}, testInfo) => {
  expect(typeof baseURL).toBe("string");
  const runId = `r${Date.now()}-${testInfo.workerIndex}`;
  const applicantConsent = await bootstrapActor(
    browser,
    baseURL as string,
    runId,
    "applicant-consent",
  );
  const applicantVoting = await bootstrapActor(
    browser,
    baseURL as string,
    runId,
    "applicant-voting",
  );
  const weberA = await bootstrapActor(
    browser,
    baseURL as string,
    runId,
    "weber-a",
  );
  const weberB = await bootstrapActor(
    browser,
    baseURL as string,
    runId,
    "weber-b",
  );

  const withdrawalProposal = await createApplication(
    applicantVoting,
    "Diesen Antrag ziehe ich bewusst wieder zurück.",
  );
  await applicantVoting.page.goto(`/antraege?id=${withdrawalProposal.id}`);
  await expect(applicantVoting.page.getByText(/^Noch /)).toBeVisible();
  applicantVoting.page.once("dialog", (dialog) => {
    void dialog.accept();
  });
  await applicantVoting.page
    .getByRole("button", { name: "Antrag zurückziehen" })
    .click();
  await expect(
    applicantVoting.page.getByText("Zurückgezogen", { exact: true }),
  ).toBeVisible();
  await expect(applicantVoting.page.getByText(/^Noch /)).toHaveCount(0);
  const withdrawn = await jsonRequest<Proposal>(
    applicantVoting.page,
    `/api/proposals/${withdrawalProposal.id}`,
  );
  expect(withdrawn.status).toBe("withdrawn");
  expect(withdrawn.remaining_seconds).toBeUndefined();

  const consentProposal = await createApplication(
    applicantConsent,
    "Ich möchte Verantwortung im Weltgewebe übernehmen.",
  );
  const acceptedWithoutVeto = await advance(
    applicantConsent.page,
    consentProposal,
    consentProposal.consent_until,
  );
  expect(acceptedWithoutVeto.status).toBe("accepted");
  const consentApplicantAuth = await jsonRequest<AuthStatus>(
    applicantConsent.page,
    "/api/auth/me",
  );
  expect(consentApplicantAuth.account_id).toBe(applicantConsent.account_id);
  expect(consentApplicantAuth.role).toBe("weber");

  const votingProposal = await createApplication(
    applicantVoting,
    "Ich möchte nach öffentlicher Beratung Weber werden.",
  );
  await weberA.page.goto(`/antraege?id=${votingProposal.id}`);
  await weberA.page
    .getByPlaceholder("Konkreter Einwand und mögliche Lösung")
    .fill("Bitte klären, welche Verantwortung übernommen wird.");
  await weberA.page.getByRole("button", { name: "Veto einlegen" }).click();
  await expect(
    weberA.page.getByText(
      "Bitte klären, welche Verantwortung übernommen wird.",
    ),
  ).toBeVisible();

  const voting = await advance(
    weberA.page,
    votingProposal,
    votingProposal.consent_until,
  );
  expect(voting.status).toBe("voting");
  expect(voting.veto_count).toBe(1);
  expect(voting.voting_until).toBeTruthy();

  await weberA.page.goto(`/antraege?id=${votingProposal.id}`);
  await weberA.page.getByRole("button", { name: "Nein", exact: true }).click();
  await weberA.page.getByRole("button", { name: "Ja", exact: true }).click();
  await weberB.page.goto(`/antraege?id=${votingProposal.id}`);
  await weberB.page.getByRole("button", { name: "Ja", exact: true }).click();

  const beforeFinalization = await jsonRequest<Proposal>(
    weberB.page,
    `/api/proposals/${votingProposal.id}`,
  );
  expect(beforeFinalization.yes_votes).toBe(2);
  expect(beforeFinalization.no_votes).toBe(0);
  expect(beforeFinalization.abstain_votes).toBe(0);

  await applicantVoting.page.goto(`/antraege?id=${votingProposal.id}`);
  await expect(
    applicantVoting.page.getByRole("button", { name: "Ja", exact: true }),
  ).toHaveCount(0);
  await expect(
    applicantVoting.page.getByRole("button", { name: "Nein", exact: true }),
  ).toHaveCount(0);

  const acceptedAfterVote = await advance(
    weberB.page,
    beforeFinalization,
    beforeFinalization.voting_until as string,
  );
  expect(acceptedAfterVote.status).toBe("accepted");
  const votingApplicantAuth = await jsonRequest<AuthStatus>(
    applicantVoting.page,
    "/api/auth/me",
  );
  expect(votingApplicantAuth.account_id).toBe(applicantVoting.account_id);
  expect(votingApplicantAuth.role).toBe("weber");

  const sachTarget = await jsonRequest<Proposal>(
    weberA.page,
    "/api/proposals",
    "POST",
    {
      kind: "sachantrag",
      title: "Gemeinschaftswerkstatt sonntags öffnen",
      summary: "Browserbeweis für eine später nachvollziehbare Aufhebung.",
    },
  );
  expect(sachTarget.kind).toBe("sachantrag");
  const acceptedSachTarget = await advance(
    weberA.page,
    sachTarget,
    sachTarget.consent_until,
  );
  expect(acceptedSachTarget.status).toBe("accepted");

  await weberB.page.goto(`/antraege?id=${sachTarget.id}`);
  await weberB.page
    .getByLabel("Begründung (optional)")
    .fill("Der Beschluss soll nach erneutem Verfahren aufgehoben werden.");
  await weberB.page
    .getByRole("button", { name: "Aufhebung beantragen" })
    .click();
  await expect(weberB.page).toHaveURL(/\/antraege\?id=/);
  const repealId = new URL(weberB.page.url()).searchParams.get("id");
  if (!repealId)
    throw new Error("repeal navigation must expose the new proposal id");
  const repeal = await jsonRequest<Proposal>(
    weberB.page,
    `/api/proposals/${repealId}`,
  );
  expect(repeal.kind).toBe("sachantrag");
  expect(repeal.status).toBe("consent");
  expect(repeal.repeals_proposal_id).toBe(sachTarget.id);
  const originalWithPending = await jsonRequest<Proposal>(
    weberB.page,
    `/api/proposals/${sachTarget.id}`,
  );
  expect(originalWithPending.status).toBe("accepted");
  expect(originalWithPending.pending_repeal_proposal_id).toBe(repeal.id);

  const acceptedRepeal = await advance(
    weberB.page,
    repeal,
    repeal.consent_until,
  );
  expect(acceptedRepeal.status).toBe("accepted");
  const originalAfterRepeal = await jsonRequest<Proposal>(
    weberB.page,
    `/api/proposals/${sachTarget.id}`,
  );
  expect(originalAfterRepeal.status).toBe("accepted");
  expect(originalAfterRepeal.pending_repeal_proposal_id).toBeUndefined();
  expect(originalAfterRepeal.repealed_by_proposal_id).toBe(repeal.id);

  const proofDir = path.resolve(
    process.cwd(),
    "../../build/proofs/governance-full-flow",
  );
  fs.mkdirSync(proofDir, { recursive: true });
  fs.writeFileSync(
    path.join(proofDir, "proof-summary.json"),
    `${JSON.stringify(
      {
        proof: "governance-full-flow",
        withdrawal: {
          proposal_id: withdrawalProposal.id,
          final_status: withdrawn.status,
          remaining_seconds_visible: false,
        },
        no_veto: {
          proposal_id: consentProposal.id,
          retained_account_id: consentApplicantAuth.account_id,
          final_status: acceptedWithoutVeto.status,
          final_role: consentApplicantAuth.role,
        },
        veto_and_vote: {
          proposal_id: votingProposal.id,
          veto_count: acceptedAfterVote.veto_count,
          yes_votes: acceptedAfterVote.yes_votes,
          no_votes: acceptedAfterVote.no_votes,
          final_status: acceptedAfterVote.status,
          retained_account_id: votingApplicantAuth.account_id,
          final_role: votingApplicantAuth.role,
          applicant_self_vote_controls_visible: false,
        },
        repeal: {
          original_proposal_id: sachTarget.id,
          original_status: originalAfterRepeal.status,
          repeal_proposal_id: repeal.id,
          repeal_status: acceptedRepeal.status,
          original_repealed_by_proposal_id:
            originalAfterRepeal.repealed_by_proposal_id,
        },
      },
      null,
      2,
    )}\n`,
  );
});
