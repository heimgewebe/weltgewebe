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
    deferListResponse?: boolean;
  } = {},
) {
  let currentStatus = options.initialStatus ?? "consent";
  let resolveListResponse: (() => void) | null = null;
  const listResponseGate = options.deferListResponse
    ? new Promise<void>((resolve) => {
        resolveListResponse = resolve;
      })
    : null;
  const requests: Array<{ method: string; pathname: string; body: unknown }> =
    [];

  await page.route("**/api/proposals**", async (route: Route) => {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method();
    const body = request.postData() ? request.postDataJSON() : null;
    requests.push({ method, pathname: url.pathname, body });

    if (url.pathname === "/api/proposals" && method === "GET") {
      if (listResponseGate) await listResponseGate;
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
          applicant_account_id: options.existingApplicantId ?? GUEST_ID,
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
          author_account_id: GUEST_ID,
          author_title: "Gast im Test",
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
    releaseListResponse: () => resolveListResponse?.(),
  };
}

test("governance views fan out from the top center and stay separate from weaving", async ({
  page,
}) => {
  await mockApiResponses(page, {
    auth: { authenticated: true, account_id: WEBER_ID, role: "weber" },
  });
  await page.goto("/map");

  const trigger = page.getByTestId("governance-fan-trigger");
  const triggerBox = await trigger.boundingBox();
  const viewport = page.viewportSize();
  expect(triggerBox).not.toBeNull();
  expect(viewport).not.toBeNull();
  expect(
    Math.abs(triggerBox!.x + triggerBox!.width / 2 - viewport!.width / 2),
  ).toBeLessThan(2);

  await trigger.click();
  await expect(page.getByTestId("governance-fan-all")).toHaveAttribute(
    "href",
    "/antraege",
  );
  await expect(page.getByTestId("governance-fan-open")).toHaveAttribute(
    "href",
    "/antraege?status=consent",
  );
  await expect(page.getByTestId("governance-fan-vetoes")).toHaveAttribute(
    "href",
    "/antraege?ereignis=veto",
  );
  await expect(
    page.getByTestId("governance-fan-conversations"),
  ).toHaveAttribute("href", "/antraege?ereignis=gespraech");
  await expect(page.getByTestId("governance-fan-voting")).toHaveAttribute(
    "href",
    "/antraege?status=voting",
  );

  await page.getByTestId("tool-fan-trigger").click();
  await expect(page.getByTestId("governance-fan")).toHaveAttribute(
    "data-expanded",
    "false",
  );
  await expect(page.getByTestId("tool-fan")).toHaveAttribute(
    "data-expanded",
    "true",
  );
  await expect(page.getByTestId("tool-fan-proposals")).toHaveCount(0);
});

test("the five governance actions stay usable on a 320 pixel viewport", async ({
  page,
}) => {
  await mockApiResponses(page, {
    auth: { authenticated: true, account_id: WEBER_ID, role: "weber" },
  });
  await page.setViewportSize({ width: 320, height: 568 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/map");
  await page.getByTestId("governance-fan-trigger").click();

  for (const testId of [
    "governance-fan-all",
    "governance-fan-open",
    "governance-fan-vetoes",
    "governance-fan-conversations",
    "governance-fan-voting",
  ]) {
    const box = await page.getByTestId(testId).boundingBox();
    expect(box, `${testId} has no visible box`).not.toBeNull();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(320);
    expect(box!.height).toBeGreaterThanOrEqual(44);
  }
});

test("veto and conversation links resolve to real filtered governance views", async ({
  page,
}) => {
  await mockApiResponses(page, {
    auth: { authenticated: true, account_id: WEBER_ID, role: "weber" },
  });
  await installGovernanceRoutes(page, { initialStatus: "voting" });

  await page.goto("/antraege?ereignis=veto");
  await expect(
    page.getByRole("heading", { name: "Anträge mit Veto" }),
  ).toBeVisible();
  await expect(page.getByText("Weberstatus für Gast im Test")).toBeVisible();

  await page.goto("/antraege?ereignis=gespraech");
  await expect(
    page.getByRole("heading", { name: "Gesprächsphasen" }),
  ).toBeVisible();
  await expect(page.getByText("Weberstatus für Gast im Test")).toBeVisible();
});

test("a guest reaches the Weber application as a distinct weaving action", async ({
  page,
}) => {
  await mockApiResponses(page, {
    auth: { authenticated: true, account_id: GUEST_ID, role: "gast" },
  });
  const governance = await installGovernanceRoutes(page, {
    deferListResponse: true,
  });
  await page.goto("/map");
  await page.getByTestId("tool-fan-trigger").click();
  await page.getByTestId("tool-fan-weave").click();
  const applicationAction = page.getByTestId("tool-fan-create-proposal");
  await expect(applicationAction).toHaveAttribute(
    "href",
    "/antraege#antrag-stellen",
  );
  await applicationAction.click();
  await expect(page).toHaveURL(/\/antraege#antrag-stellen$/);
  await expect(page.locator("#antrag-stellen")).toBeFocused({ timeout: 500 });
  expect(
    governance.requests.some(
      (entry) => entry.method === "GET" && entry.pathname === "/api/proposals",
    ),
  ).toBe(true);
  governance.releaseListResponse();
});

test("client-side hash navigation focuses the Weber application without remounting", async ({
  page,
}) => {
  await mockApiResponses(page, {
    auth: { authenticated: true, account_id: GUEST_ID, role: "gast" },
  });
  await installGovernanceRoutes(page);
  await page.goto("/antraege");
  await expect(
    page.getByRole("heading", { name: "Weberstatus beantragen" }),
  ).toBeVisible();

  await page.evaluate(() => {
    (window as Window & { __intraPageProbe?: string }).__intraPageProbe =
      "preserved";
    const link = document.createElement("a");
    link.href = "/antraege#antrag-stellen";
    link.textContent = "Zum Antrag";
    link.dataset.testid = "intra-page-application-link";
    document.body.appendChild(link);
  });
  await page.getByTestId("intra-page-application-link").click();

  await expect(page).toHaveURL(/\/antraege#antrag-stellen$/);
  await expect(page.locator("#antrag-stellen")).toBeFocused();
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          (window as Window & { __intraPageProbe?: string }).__intraPageProbe,
      ),
    )
    .toBe("preserved");
});

test("initial hash load does not steal focus after the user moves it", async ({
  page,
}) => {
  await mockApiResponses(page, {
    auth: { authenticated: true, account_id: GUEST_ID, role: "gast" },
  });
  let releaseAuthResponse!: () => void;
  const authResponseGate = new Promise<void>((resolve) => {
    releaseAuthResponse = resolve;
  });
  await page.route("**/api/auth/me", async (route) => {
    await authResponseGate;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        authenticated: true,
        account_id: GUEST_ID,
        role: "gast",
      }),
    });
  });
  await installGovernanceRoutes(page);
  await page.goto("/antraege#antrag-stellen");

  const backLink = page.getByRole("link", { name: "Zum Gewebe" });
  await backLink.focus();
  await expect(backLink).toBeFocused();
  releaseAuthResponse();

  await expect(
    page.getByRole("heading", { name: "Weberstatus beantragen" }),
  ).toBeVisible();
  await expect(backLink).toBeFocused();
});

test("guest can read, discuss, and submit the own Weber application", async ({
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
  const discussion = page.getByLabel("Beitrag verfassen");
  await expect(discussion).toBeVisible();
  await discussion.fill("Ich erläutere meinen Antrag als Gast.");
  await page.getByRole("button", { name: "Beitrag senden" }).click();
  const messageRequest = governance.requests.find(
    (entry) =>
      entry.method === "POST" &&
      entry.pathname === `/api/proposals/${PROPOSAL_ID}/messages`,
  );
  expect(messageRequest?.body).toEqual({
    body: "Ich erläutere meinen Antrag als Gast.",
  });
  await expect(
    page.getByText("Ich erläutere meinen Antrag als Gast."),
  ).toBeVisible();
});

test("applicant cannot veto or vote on the own Weber application", async ({
  page,
}) => {
  await mockApiResponses(page, {
    auth: { authenticated: true, account_id: GUEST_ID, role: "gast" },
  });
  await installGovernanceRoutes(page, { existingApplicantId: GUEST_ID });
  await page.goto(`/antraege?id=${PROPOSAL_ID}`);

  await expect(page.getByRole("button", { name: "Veto einlegen" })).toHaveCount(
    0,
  );
  await expect(page.getByRole("button", { name: "Ja" })).toHaveCount(0);
});

test("guest can veto and vote on another account's Weber application", async ({
  page,
}) => {
  await mockApiResponses(page, {
    auth: { authenticated: true, account_id: GUEST_ID, role: "gast" },
  });
  const governance = await installGovernanceRoutes(page, {
    existingApplicantId: "another-guest",
  });
  await page.goto(`/antraege?id=${PROPOSAL_ID}`);

  await page
    .getByPlaceholder("Konkreter Einwand und mögliche Lösung")
    .fill("Ich möchte diesen Punkt vor der Aufnahme gemeinsam klären.");
  await page.getByRole("button", { name: "Veto einlegen" }).click();
  await expect(page.getByText("Gespräch und Abstimmung")).toBeVisible();
  await page.getByRole("button", { name: "Ja" }).click();

  expect(
    governance.requests.find((entry) => entry.pathname.endsWith("/veto"))?.body,
  ).toEqual({
    reason: "Ich möchte diesen Punkt vor der Aufnahme gemeinsam klären.",
  });
  expect(
    governance.requests.find((entry) => entry.pathname.endsWith("/vote"))?.body,
  ).toEqual({
    choice: "ja",
  });
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
