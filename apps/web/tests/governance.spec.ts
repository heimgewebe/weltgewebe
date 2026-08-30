import { expect, test, type Page, type Route } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

const GUEST_ID = "guest-governance-e2e";
const WEBER_ID = "weber-governance-e2e";
const PROPOSAL_ID = "11111111-1111-4111-8111-111111111111";
const SECOND_PROPOSAL_ID = "22222222-2222-4222-8222-222222222222";

function proposal(
  status: "consent" | "voting" = "consent",
  messageCount: number | null = 1,
) {
  return {
    id: PROPOSAL_ID,
    kind: "weberantrag",
    webgemeindezentrum_id: "webgemeindezentrum-hammer-park",
    applicant_account_id: GUEST_ID,
    applicant_title: "Gast im Test",
    summary: "Ich möchte Verantwortung im Weltgewebe übernehmen.",
    status,
    created_at: "2026-07-14T10:00:00Z",
    consent_until: "2026-07-21T10:00:00Z",
    voting_until: status === "voting" ? "2026-07-28T10:00:00Z" : undefined,
    veto_count: status === "voting" ? 1 : 0,
    ...(messageCount === null ? {} : { message_count: messageCount }),
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

function sachProposal() {
  return {
    ...proposal("consent", 0),
    kind: "sachantrag",
    title: "Werkstatt dauerhaft öffnen",
    target_node_id: "node-werkstatt",
    target_node_title: "Offene Werkstatt",
    applicant_account_id: WEBER_ID,
    applicant_title: "Weber im Test",
    summary: "Die Ortsweberei soll verlässliche Öffnungszeiten beschließen.",
    vetoes: [],
  };
}

async function installGovernanceRoutes(
  page: Page,
  options: {
    initialStatus?: "consent" | "voting";
    existingApplicantId?: string;
    initialMessageCount?: number;
    detailMessageCount?: number;
    initialMessages?: number;
    omitMessageCount?: boolean;
    rawListMessageCount?: string;
    deferListResponse?: boolean;
    deferMessagesResponse?: boolean;
  } = {},
) {
  let currentStatus = options.initialStatus ?? "consent";
  let resolveListResponse: (() => void) | null = null;
  const listResponseGate = options.deferListResponse
    ? new Promise<void>((resolve) => {
        resolveListResponse = resolve;
      })
    : null;
  let resolveMessagesResponse: (() => void) | null = null;
  const messagesResponseGate = options.deferMessagesResponse
    ? new Promise<void>((resolve) => {
        resolveMessagesResponse = resolve;
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
      const listedProposal = {
        ...proposal(
          currentStatus,
          options.omitMessageCount ? null : (options.initialMessageCount ?? 1),
        ),
        applicant_account_id: options.existingApplicantId ?? GUEST_ID,
      };
      let responseBody = JSON.stringify([listedProposal]);
      if (options.rawListMessageCount) {
        responseBody = responseBody.replace(
          /"message_count":-?\d+(?:\.\d+)?(?:e[+-]?\d+)?/i,
          `"message_count":${options.rawListMessageCount}`,
        );
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: responseBody,
      });
    }
    if (url.pathname === "/api/proposals" && method === "POST") {
      return route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(proposal("consent", 0)),
      });
    }
    if (url.pathname === `/api/proposals/${PROPOSAL_ID}` && method === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ...proposal(
            currentStatus,
            options.omitMessageCount
              ? undefined
              : (options.detailMessageCount ??
                  options.initialMessageCount ??
                  1),
          ),
          applicant_account_id: options.existingApplicantId ?? GUEST_ID,
          own_vote: undefined,
        }),
      });
    }
    if (
      url.pathname === `/api/proposals/${PROPOSAL_ID}/messages` &&
      method === "GET"
    ) {
      if (messagesResponseGate) await messagesResponseGate;
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          Array.from({ length: options.initialMessages ?? 1 }, (_, index) => ({
            id: `message-${index + 1}`,
            author_account_id: WEBER_ID,
            author_title: "Weber im Test",
            body: "Willkommen im öffentlichen Gesprächsraum.",
            created_at: "2026-07-14T12:00:00Z",
          })),
        ),
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
    releaseMessagesResponse: () => resolveMessagesResponse?.(),
  };
}

test("the map drops the Governance fan while the canonical governance filters stay available", async ({
  page,
}) => {
  await mockApiResponses(page, {
    auth: { authenticated: true, account_id: WEBER_ID, role: "weber" },
  });
  await page.goto("/map");

  await expect(page.getByTestId("governance-fan-trigger")).toHaveCount(0);
  await page.getByTestId("tool-fan-trigger").click();
  await expect(page.getByTestId("tool-fan")).toHaveAttribute(
    "data-expanded",
    "true",
  );
  await expect(page.getByTestId("tool-fan-proposals")).toHaveCount(0);

  await page.goto("/antraege");
  const expectedFilters = [
    ["Alle", "/antraege"],
    ["Offen", "/antraege?status=consent"],
    ["Vetos", "/antraege?ereignis=veto"],
    ["Gespräche", "/antraege?ereignis=gespraech"],
    ["Abstimmungen", "/antraege?status=voting"],
  ] as const;
  for (const [label, href] of expectedFilters) {
    await expect(
      page.getByRole("link", { name: label, exact: true }),
    ).toHaveAttribute("href", href);
  }
});

test("the five canonical governance filters stay usable at 320 pixels", async ({
  page,
}) => {
  await mockApiResponses(page, {
    auth: { authenticated: true, account_id: WEBER_ID, role: "weber" },
  });
  await page.setViewportSize({ width: 320, height: 568 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/antraege");

  const filters = page.locator(".proposal-filters a");
  await expect(filters).toHaveCount(5);
  for (let index = 0; index < 5; index += 1) {
    const box = await filters.nth(index).boundingBox();
    expect(box, `governance filter ${index} has no visible box`).not.toBeNull();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(320);
    expect(box!.height).toBeGreaterThanOrEqual(44);
  }
});

test("veto and conversation links resolve to their factual governance views", async ({
  page,
}) => {
  await mockApiResponses(page, {
    auth: { authenticated: true, account_id: WEBER_ID, role: "weber" },
  });
  const governance = await installGovernanceRoutes(page, {
    initialStatus: "voting",
    initialMessageCount: 1,
  });

  await page.goto("/antraege?ereignis=veto");
  await expect(
    page.getByRole("heading", { name: "Anträge mit Veto" }),
  ).toBeVisible();
  await expect(page.getByText("Weberstatus für Gast im Test")).toBeVisible();

  governance.setStatus("consent");
  await page.goto("/antraege?ereignis=gespraech");
  await expect(page.getByRole("heading", { name: "Gespräche" })).toBeVisible();
  await expect(page.getByText("Weberstatus für Gast im Test")).toBeVisible();
  await expect(page.getByText("1 Beitrag", { exact: true })).toBeVisible();
});

test("Sachantrag list and detail keep the same center decision linked to its node", async ({
  page,
}) => {
  await mockApiResponses(page, {
    auth: { authenticated: true, account_id: "other-weber", role: "weber" },
  });
  await page.route("**/api/proposals**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/api/proposals") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([sachProposal()]),
      });
    }
    if (url.pathname === `/api/proposals/${PROPOSAL_ID}`) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(sachProposal()),
      });
    }
    if (url.pathname === `/api/proposals/${PROPOSAL_ID}/messages`) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: "[]",
      });
    }
    return route.fulfill({ status: 404 });
  });

  await page.goto("/antraege");
  await expect(
    page.getByRole("heading", { name: "Werkstatt dauerhaft öffnen" }),
  ).toBeVisible();
  await expect(page.getByText("Knoten:").locator("..")).toContainText(
    "Offene Werkstatt",
  );
  await expect(
    page.getByRole("link", { name: "Offene Werkstatt" }),
  ).toHaveAttribute("href", "/map?focus=node%3Anode-werkstatt");

  await page.getByRole("link", { name: "Werkstatt dauerhaft öffnen" }).click();
  await expect(page.getByText("Gemeinschaftlicher Beschluss")).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Offene Werkstatt" }),
  ).toHaveAttribute("href", "/map?focus=node%3Anode-werkstatt");
});

test("the conversation view treats a legacy API without message_count as empty", async ({
  page,
}) => {
  await mockApiResponses(page, {
    auth: { authenticated: true, account_id: WEBER_ID, role: "weber" },
  });
  await installGovernanceRoutes(page, {
    initialStatus: "voting",
    omitMessageCount: true,
  });

  await page.goto("/antraege?ereignis=gespraech");
  await expect(page.getByRole("heading", { name: "Gespräche" })).toBeVisible();
  await expect(page.getByText("Weberstatus für Gast im Test")).toHaveCount(0);
  await expect(
    page.getByText("Noch gibt es keine Gespräche mit Beiträgen."),
  ).toBeVisible();
});

test("the conversation view rejects a non-finite message count", async ({
  page,
}) => {
  await mockApiResponses(page, {
    auth: { authenticated: true, account_id: WEBER_ID, role: "weber" },
  });
  await installGovernanceRoutes(page, {
    initialStatus: "voting",
    rawListMessageCount: "1e400",
  });

  await page.goto("/antraege?ereignis=gespraech");
  await expect(page.getByText("Weberstatus für Gast im Test")).toHaveCount(0);
  await expect(
    page.getByText("Noch gibt es keine Gespräche mit Beiträgen."),
  ).toBeVisible();
});

test("query navigation rebinds detail and mutations to the selected proposal", async ({
  page,
}) => {
  await mockApiResponses(page, {
    auth: { authenticated: true, account_id: WEBER_ID, role: "weber" },
  });

  let releaseFirstDetail!: () => void;
  const firstDetailGate = new Promise<void>((resolve) => {
    releaseFirstDetail = resolve;
  });
  let markFirstDetailRequested!: () => void;
  const firstDetailRequested = new Promise<void>((resolve) => {
    markFirstDetailRequested = resolve;
  });
  const messagePosts: string[] = [];

  await page.route("**/api/proposals**", async (route: Route) => {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method();

    if (url.pathname === "/api/proposals" && method === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            ...proposal("consent", 0),
            id: PROPOSAL_ID,
            applicant_title: "Antrag Alpha",
          },
          {
            ...proposal("consent", 0),
            id: SECOND_PROPOSAL_ID,
            applicant_title: "Antrag Beta",
          },
        ]),
      });
    }

    const detailMatch = url.pathname.match(/^\/api\/proposals\/([^/]+)$/);
    if (detailMatch && method === "GET") {
      const proposalId = detailMatch[1];
      if (proposalId === PROPOSAL_ID) {
        markFirstDetailRequested();
        await firstDetailGate;
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ...proposal("consent", 0),
          id: proposalId,
          applicant_title:
            proposalId === PROPOSAL_ID ? "Antrag Alpha" : "Antrag Beta",
          own_vote: undefined,
        }),
      });
    }

    const messagesMatch = url.pathname.match(
      /^\/api\/proposals\/([^/]+)\/messages$/,
    );
    if (messagesMatch && method === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: "[]",
      });
    }
    if (messagesMatch && method === "POST") {
      messagePosts.push(url.pathname);
      const body = request.postDataJSON() as { body: string };
      return route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          id: "message-beta",
          author_account_id: WEBER_ID,
          author_title: "Weber im Test",
          body: body.body,
          created_at: "2026-07-27T15:00:00Z",
        }),
      });
    }

    return route.fulfill({ status: 404 });
  });

  await page.goto(`/antraege?id=${PROPOSAL_ID}`);
  await firstDetailRequested;
  await page.evaluate((proposalId) => {
    const link = document.createElement("a");
    link.href = `/antraege?id=${proposalId}`;
    link.textContent = "Zu Antrag Beta";
    document.body.append(link);
  }, SECOND_PROPOSAL_ID);
  await page.getByRole("link", { name: "Zu Antrag Beta" }).click();

  await expect(
    page.getByRole("heading", { name: "Antrag Beta" }),
  ).toBeVisible();
  await page.getByLabel("Beitrag verfassen").fill("Beitrag für Beta");
  await page.getByRole("button", { name: "Beitrag senden" }).click();
  await expect(page.getByText("Beitrag für Beta")).toBeVisible();
  expect(messagePosts).toEqual([
    `/api/proposals/${SECOND_PROPOSAL_ID}/messages`,
  ]);

  releaseFirstDetail();
  await expect(
    page.getByRole("heading", { name: "Antrag Beta" }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Antrag Alpha" })).toHaveCount(
    0,
  );
});

test("the first contribution updates the retained proposal projection", async ({
  page,
}) => {
  await mockApiResponses(page, {
    auth: { authenticated: true, account_id: WEBER_ID, role: "weber" },
  });
  await installGovernanceRoutes(page, {
    initialStatus: "consent",
    initialMessageCount: 0,
    initialMessages: 0,
  });

  await page.goto(`/antraege?id=${PROPOSAL_ID}`);
  await page.getByLabel("Beitrag verfassen").fill("Erster belegter Beitrag");
  await page.getByRole("button", { name: "Beitrag senden" }).click();
  await expect(page.getByText("Erster belegter Beitrag")).toBeVisible();

  await page.getByRole("link", { name: "Alle Anträge" }).click();
  await expect(page.getByText("1 Beitrag", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Gespräche" }).click();
  await expect(page.getByText("Weberstatus für Gast im Test")).toBeVisible();
});

test("a late list response cannot undo the first confirmed contribution", async ({
  page,
}) => {
  await mockApiResponses(page, {
    auth: { authenticated: true, account_id: WEBER_ID, role: "weber" },
  });
  const governance = await installGovernanceRoutes(page, {
    initialStatus: "consent",
    initialMessageCount: 0,
    initialMessages: 0,
    deferListResponse: true,
  });

  await page.goto(`/antraege?id=${PROPOSAL_ID}`);
  await page.getByLabel("Beitrag verfassen").fill("Beitrag vor später Liste");
  await page.getByRole("button", { name: "Beitrag senden" }).click();
  await expect(page.getByText("Beitrag vor später Liste")).toBeVisible();

  governance.releaseListResponse();
  await page.getByRole("link", { name: "Alle Anträge" }).click();
  await expect(page.getByText("1 Beitrag", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Gespräche" }).click();
  await expect(page.getByText("Weberstatus für Gast im Test")).toBeVisible();
});

test("a confirmed post increments a fresher retained detail count", async ({
  page,
}) => {
  await mockApiResponses(page, {
    auth: { authenticated: true, account_id: WEBER_ID, role: "weber" },
  });
  const governance = await installGovernanceRoutes(page, {
    initialStatus: "consent",
    initialMessageCount: 0,
    detailMessageCount: 1,
    initialMessages: 0,
    deferMessagesResponse: true,
  });
  const listResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/proposals" && response.request().method() === "GET"
    );
  });

  await page.goto(`/antraege?id=${PROPOSAL_ID}`);
  await listResponse;
  await page.evaluate(
    () =>
      new Promise<void>((resolve) => requestAnimationFrame(() => resolve())),
  );
  governance.releaseMessagesResponse();
  await page.getByLabel("Beitrag verfassen").fill("Zweiter belegter Beitrag");
  await page.getByRole("button", { name: "Beitrag senden" }).click();
  await expect(page.getByText("Zweiter belegter Beitrag")).toBeVisible();

  await page.getByRole("link", { name: "Alle Anträge" }).click();
  await expect(page.getByText("2 Beiträge", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Gespräche" }).click();
  await expect(page.getByText("Weberstatus für Gast im Test")).toBeVisible();
});

test("the conversation view excludes voting proposals without contributions", async ({
  page,
}) => {
  await mockApiResponses(page, {
    auth: { authenticated: true, account_id: WEBER_ID, role: "weber" },
  });
  await installGovernanceRoutes(page, {
    initialStatus: "voting",
    initialMessageCount: 0,
  });

  await page.goto("/antraege?ereignis=gespraech");
  await expect(page.getByRole("heading", { name: "Gespräche" })).toBeVisible();
  await expect(page.getByText("Weberstatus für Gast im Test")).toHaveCount(0);
  await expect(
    page.getByText("Noch gibt es keine Gespräche mit Beiträgen."),
  ).toBeVisible();
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
  await expect
    .poll(() =>
      governance.requests.some(
        (entry) =>
          entry.method === "GET" && entry.pathname === "/api/proposals",
      ),
    )
    .toBe(true);
  governance.releaseListResponse();
});

test("guest exit requests fresh step-up confirmation before deleting the account", async ({
  page,
}) => {
  await mockApiResponses(page, {
    auth: { authenticated: true, account_id: GUEST_ID, role: "gast" },
  });
  await installGovernanceRoutes(page);

  let exitRequests = 0;
  let stepUpBody: unknown = null;
  await page.route("**/api/accounts/me/exit", async (route: Route) => {
    exitRequests += 1;
    await route.fulfill({
      status: 403,
      contentType: "application/json",
      body: JSON.stringify({
        error: "STEP_UP_REQUIRED",
        challenge_id: "guest-exit-challenge",
      }),
    });
  });
  await page.route(
    "**/api/auth/step-up/magic-link/request",
    async (route: Route) => {
      stepUpBody = route.request().postDataJSON();
      await route.fulfill({ status: 204 });
    },
  );

  page.once("dialog", async (dialog) => {
    expect(dialog.type()).toBe("confirm");
    expect(dialog.message()).toContain("Bestätigungslink");
    await dialog.accept();
  });

  await page.goto("/antraege");
  await page
    .getByRole("button", { name: "commonThing vollständig verlassen" })
    .click();

  await expect.poll(() => exitRequests).toBe(1);
  await expect
    .poll(() => stepUpBody)
    .toEqual({
      challenge_id: "guest-exit-challenge",
    });
  await expect(
    page.getByText(
      "Bestätigungslink gesendet. Dein Gastkonto bleibt bestehen, bis du den Link in deiner E-Mail bestätigst.",
    ),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/antraege$/);
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

  const backLink = page.getByRole("link", { name: "Zur Karte" });
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
    page.getByRole("heading", { name: "Ablauf dieses Antrags" }),
  ).toBeVisible();
  await expect(
    page.getByTestId("proposal-process-step-consent"),
  ).toHaveAttribute("aria-current", "step");
  await expect(page.getByTestId("proposal-process-vetoes")).toContainText("0");
  await expect(page.getByTestId("proposal-process-messages")).toContainText(
    "1",
  );
  await expect(page.getByTestId("proposal-process-votes")).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "Fäden dieses Antrags" }),
  ).toHaveCount(0);
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

test("guest can discuss but cannot veto or vote on another account's Weber application", async ({
  page,
}) => {
  await mockApiResponses(page, {
    auth: { authenticated: true, account_id: GUEST_ID, role: "gast" },
  });
  const governance = await installGovernanceRoutes(page, {
    existingApplicantId: "another-guest",
  });
  await page.goto(`/antraege?id=${PROPOSAL_ID}`);

  await expect(page.getByRole("button", { name: "Veto einlegen" })).toHaveCount(
    0,
  );
  await expect(page.getByRole("button", { name: "Ja" })).toHaveCount(0);
  await expect(
    page.getByPlaceholder("Konkreter Einwand und mögliche Lösung"),
  ).toHaveCount(0);

  expect(
    governance.requests.filter(
      (entry) =>
        entry.pathname.endsWith("/veto") || entry.pathname.endsWith("/vote"),
    ),
  ).toEqual([]);
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

  await expect(
    page.getByTestId("proposal-process-step-voting"),
  ).toHaveAttribute("aria-current", "step");
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
