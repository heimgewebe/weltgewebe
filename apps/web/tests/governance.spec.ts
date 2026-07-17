import { expect, test, type Page, type Route } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

const GUEST_ID = "guest-governance-e2e";
const WEBER_ID = "weber-governance-e2e";
const PROPOSAL_ID = "11111111-1111-4111-8111-111111111111";

function proposal(status: "consent" | "voting" = "consent") {
  return {
    id: PROPOSAL_ID,
    kind: "weberantrag",
    applicant_account_id: GUEST_ID,
    applicant_title: "Gast im Test",
    summary: "Ich möchte Verantwortung im Weltgewebe übernehmen.",
    status,
    created_at: "2026-07-14T10:00:00Z",
    consent_until: "2026-07-21T10:00:00Z",
    voting_until: status === "voting" ? "2026-07-28T10:00:00Z" : undefined,
    veto_count: status === "voting" ? 1 : 0,
    yes_votes: 0,
    no_votes: 0,
    abstain_votes: 0,
    remaining_seconds: 604800,
    vetoes:
      status === "voting"
        ? [
            {
              weber_account_id: WEBER_ID,
              weber_title: "Weber im Test",
              reason: "Die offene Frage soll gemeinsam beraten werden.",
              created_at: "2026-07-15T10:00:00Z",
            },
          ]
        : [],
  };
}

async function installGovernanceRoutes(
  page: Page,
  options: {
    initialStatus?: "consent" | "voting";
    existingApplicantId?: string;
  } = {},
) {
  let currentStatus = options.initialStatus ?? "consent";
  const requests: Array<{ method: string; pathname: string; body: unknown }> =
    [];

  await page.route("**/api/proposals**", async (route: Route) => {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method();
    const body = request.postData() ? request.postDataJSON() : null;
    requests.push({ method, pathname: url.pathname, body });

    if (url.pathname === "/api/proposals" && method === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            ...proposal(currentStatus),
            applicant_account_id: options.existingApplicantId ?? GUEST_ID,
          },
        ]),
      });
    }
    if (url.pathname === "/api/proposals" && method === "POST") {
      return route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(proposal("consent")),
      });
    }
    if (url.pathname === `/api/proposals/${PROPOSAL_ID}` && method === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ...proposal(currentStatus),
          own_vote: undefined,
        }),
      });
    }
    if (
      url.pathname === `/api/proposals/${PROPOSAL_ID}/messages` &&
      method === "GET"
    ) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "message-1",
            author_account_id: WEBER_ID,
            author_title: "Weber im Test",
            body: "Willkommen im öffentlichen Gesprächsraum.",
            created_at: "2026-07-14T12:00:00Z",
          },
        ]),
      });
    }
    if (
      url.pathname === `/api/proposals/${PROPOSAL_ID}/messages` &&
      method === "POST"
    ) {
      return route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          id: "message-new",
          author_account_id: WEBER_ID,
          author_title: "Weber im Test",
          body: (body as { body: string }).body,
          created_at: "2026-07-15T12:00:00Z",
        }),
      });
    }
    if (
      url.pathname === `/api/proposals/${PROPOSAL_ID}/veto` &&
      method === "POST"
    ) {
      currentStatus = "voting";
      return route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          weber_account_id: WEBER_ID,
          weber_title: "Weber im Test",
          reason: (body as { reason: string }).reason,
          created_at: "2026-07-15T10:00:00Z",
        }),
      });
    }
    if (
      url.pathname === `/api/proposals/${PROPOSAL_ID}/vote` &&
      method === "PUT"
    ) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(body),
      });
    }
    return route.fulfill({ status: 404 });
  });

  return {
    requests,
    setStatus: (status: "consent" | "voting") => (currentStatus = status),
  };
}

test("Anträge is reachable as a secondary link inside the tool fan", async ({
  page,
}) => {
  await mockApiResponses(page, {
    auth: { authenticated: true, account_id: WEBER_ID, role: "weber" },
  });
  await page.goto("/map");

  const link = page.getByTestId("tool-fan-proposals");
  // Secondary access: not reachable while the fan is closed.
  await expect(link).toHaveAttribute("tabindex", "-1");

  await page.getByTestId("tool-fan-trigger").click();
  await expect(link).toBeVisible();
  await expect(link).toHaveAttribute("href", "/antraege");
});

test("guest can read everything and submit only the own Weber application", async ({
  page,
}) => {
  await mockApiResponses(page, {
    auth: { authenticated: true, account_id: GUEST_ID, role: "gast" },
  });
  const governance = await installGovernanceRoutes(page, {
    existingApplicantId: "another-guest",
  });
  await page.goto("/antraege");

  await expect(
    page.getByRole("heading", { name: "Anträge", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Weberstatus beantragen" }),
  ).toBeVisible();
  await expect(page.getByText("Weberstatus für Gast im Test")).toBeVisible();
  await page
    .getByLabel("Kurze Vorstellung oder Begründung")
    .fill("  Ich möchte mitweben.  ");
  await page.getByRole("button", { name: "Weberstatus beantragen" }).click();

  const create = governance.requests.find(
    (entry) => entry.method === "POST" && entry.pathname === "/api/proposals",
  );
  expect(create?.body).toEqual({
    kind: "weberantrag",
    summary: "Ich möchte mitweben.",
  });

  const directFadenWrites: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname === "/api/edges" && request.method() !== "GET") {
      directFadenWrites.push(request.method());
    }
  });

  await page.goto(`/antraege?id=${PROPOSAL_ID}`);
  await expect(
    page.getByRole("heading", { name: "Fäden dieses Antrags" }),
  ).toBeVisible();
  await expect(page.getByTestId("faden-count-proposal")).toContainText("1");
  await expect(page.getByTestId("faden-count-vetoes")).toContainText("0");
  await expect(page.getByTestId("faden-count-messages")).toContainText("1");
  await expect(page.getByTestId("faden-count-votes")).toContainText("0");
  await expect(
    page.getByTestId("governance-faden").locator("path"),
  ).toHaveCount(2);
  expect(directFadenWrites).toEqual([]);
  await expect(
    page.getByText("Willkommen im öffentlichen Gesprächsraum."),
  ).toBeVisible();
  await expect(
    page.getByText(/Als Gast kannst du den Gesprächsraum lesen/),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Veto einlegen" })).toHaveCount(
    0,
  );
  await expect(page.getByRole("button", { name: "Ja" })).toHaveCount(0);
});

test("Weber veto opens the second phase and voting uses yes greater than no without quorum", async ({
  page,
}) => {
  await mockApiResponses(page, {
    auth: { authenticated: true, account_id: WEBER_ID, role: "weber" },
  });
  const governance = await installGovernanceRoutes(page);
  await page.goto(`/antraege?id=${PROPOSAL_ID}`);

  await page
    .getByPlaceholder("Konkreter Einwand und mögliche Lösung")
    .fill("Bitte die offene Verantwortungsfrage zuerst klären.");
  await page.getByRole("button", { name: "Veto einlegen" }).click();

  await expect(page.getByText("Gespräch und Abstimmung")).toBeVisible();
  await expect(
    page.getByText(/Es gibt keine Mindestbeteiligung/),
  ).toBeVisible();
  await page.getByRole("button", { name: "Ja" }).click();

  const veto = governance.requests.find((entry) =>
    entry.pathname.endsWith("/veto"),
  );
  const vote = governance.requests.find((entry) =>
    entry.pathname.endsWith("/vote"),
  );
  expect(veto?.body).toEqual({
    reason: "Bitte die offene Verantwortungsfrage zuerst klären.",
  });
  expect(vote?.body).toEqual({ choice: "ja" });
});
