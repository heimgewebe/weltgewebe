import { expect, test, type Page, type Route } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

const CONVERSATION_ID = "d3a6c9b1-8c4f-4e6b-a02a-2c9d6a5b6c3a";

interface MockMessage {
  id: string;
  conversation_id: string;
  author_account_id: string | null;
  author_title: string;
  content: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

async function openFirstNodeConversation(page: Page) {
  await page.goto("/map");
  await page.waitForSelector(".map-marker");
  await page
    .locator(".map-marker:not(.marker-account)")
    .first()
    .click({ force: true });
  const panel = page.getByTestId("context-panel");
  await panel.getByRole("tab", { name: "Gespräch" }).click();
  return panel;
}

async function installConversationApi(
  page: Page,
  messages: MockMessage[],
  options: { failFirstCreate?: boolean; delaySecondList?: boolean } = {},
) {
  let listRequests = 0;
  let createAttempts = 0;
  const idempotencyKeys: string[] = [];
  let releaseDelayedList: (() => void) | null = null;
  let delayedListStarted = false;

  await page.route("**/api/**", async (route: Route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();

    if (/^\/api\/nodes\/[^/]+\/conversation$/.test(path) && method === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: CONVERSATION_ID,
          conversation_type: "node",
          node_id: "fake-id",
          visibility: "public",
          created_at: "2026-07-19T10:00:00Z",
          updated_at: "2026-07-19T10:00:00Z",
          deleted_at: null,
        }),
      });
    }

    if (
      path === `/api/conversations/${CONVERSATION_ID}/messages` &&
      method === "GET"
    ) {
      listRequests += 1;
      const snapshot = messages.map((message) => ({ ...message }));
      if (options.delaySecondList && listRequests === 2) {
        delayedListStarted = true;
        await new Promise<void>((resolve) => {
          releaseDelayedList = resolve;
        });
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: snapshot,
          page: { limit: 50, next_cursor: null, has_more: false },
        }),
      });
    }

    if (
      path === `/api/conversations/${CONVERSATION_ID}/messages` &&
      method === "POST"
    ) {
      createAttempts += 1;
      idempotencyKeys.push(request.headers()["idempotency-key"] ?? "");
      if (options.failFirstCreate && createAttempts === 1) {
        return route.fulfill({
          status: 503,
          contentType: "application/json",
          body: JSON.stringify({
            code: "conversation_store_unavailable",
            message: "unavailable",
          }),
        });
      }
      const content = (request.postDataJSON() as { content: string }).content;
      const now = "2026-07-19T10:01:00Z";
      const created: MockMessage = {
        id: "e4a7d0c2-9d5a-4f7c-b13a-3d0e7a6c7d4a",
        conversation_id: CONVERSATION_ID,
        author_account_id: "e2e-weber",
        author_title: "Eigene Garnrolle",
        content,
        created_at: now,
        updated_at: now,
        deleted_at: null,
      };
      messages.push(created);
      return route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(created),
      });
    }

    const messageMatch = path.match(
      new RegExp(`^/api/conversations/${CONVERSATION_ID}/messages/([^/]+)$`),
    );
    if (messageMatch && (method === "PATCH" || method === "DELETE")) {
      const message = messages.find((item) => item.id === messageMatch[1]);
      if (!message) return route.fulfill({ status: 404 });
      expect(request.headers()["if-match"]).toBe(`"${message.updated_at}"`);
      if (method === "PATCH") {
        message.content = (
          request.postDataJSON() as { content: string }
        ).content;
        message.updated_at = "2026-07-19T10:02:00Z";
      } else {
        message.content = null;
        message.updated_at = "2026-07-19T10:03:00Z";
        message.deleted_at = message.updated_at;
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(message),
      });
    }

    return route.fallback();
  });

  return {
    listRequestCount: () => listRequests,
    delayedListHasStarted: () => delayedListStarted,
    releaseDelayedList: () => releaseDelayedList?.(),
    idempotencyKeys,
  };
}

test("Gast liest den leeren Knotengesprächsraum ohne Schreibaktionen", async ({
  page,
}) => {
  await mockApiResponses(page, {
    auth: { authenticated: true, account_id: "e2e-gast", role: "gast" },
  });
  await installConversationApi(page, []);

  const panel = await openFirstNodeConversation(page);

  await expect(panel.getByText(/Noch keine Beiträge/)).toBeVisible();
  await expect(panel.getByText(/Als Gast kannst du/)).toBeVisible();
  await expect(panel.getByLabel("Neuer Beitrag")).toHaveCount(0);
});

test("Weber behält Entwürfe, bearbeitet eigene Beiträge und tombstoned sie", async ({
  page,
}) => {
  await mockApiResponses(page, {
    auth: { authenticated: true, account_id: "e2e-weber", role: "weber" },
  });
  const api = await installConversationApi(page, [], {
    failFirstCreate: true,
  });
  const panel = await openFirstNodeConversation(page);
  const draft = panel.getByLabel("Neuer Beitrag");
  await draft.fill("Mein Gesprächsentwurf");

  await panel.getByRole("button", { name: "Beitrag veröffentlichen" }).click();
  await expect(draft).toHaveValue("Mein Gesprächsentwurf");
  await expect(panel.getByText(/Entwurf bleibt erhalten/)).toBeVisible();

  await panel.getByRole("button", { name: "Beitrag veröffentlichen" }).click();
  await expect(panel.getByText("Mein Gesprächsentwurf")).toBeVisible();
  expect(api.idempotencyKeys).toHaveLength(2);
  expect(api.idempotencyKeys[0]).toBe(api.idempotencyKeys[1]);

  const messageList = panel.getByRole("log", { name: "Gesprächsbeiträge" });
  await messageList.getByRole("button", { name: "Bearbeiten" }).click();
  await panel.getByLabel("Beitrag bearbeiten").fill("Überarbeiteter Beitrag");
  await panel.getByRole("button", { name: "Änderung speichern" }).click();
  await expect(panel.getByText("Überarbeiteter Beitrag")).toBeVisible();

  page.once("dialog", async (dialog) => dialog.accept());
  await messageList.getByRole("button", { name: "Entfernen" }).click();
  await expect(panel.getByText("Beitrag entfernt.")).toBeVisible();
  await expect(panel.getByText("Überarbeiteter Beitrag")).toHaveCount(0);
});

test("Ein geänderter Entwurf beginnt nach unklarem Fehler eine neue idempotente Operation", async ({
  page,
}) => {
  await mockApiResponses(page, {
    auth: { authenticated: true, account_id: "e2e-weber", role: "weber" },
  });
  const api = await installConversationApi(page, [], {
    failFirstCreate: true,
  });
  const panel = await openFirstNodeConversation(page);
  const draft = panel.getByLabel("Neuer Beitrag");
  await draft.fill("Erster Entwurf");
  await panel.getByRole("button", { name: "Beitrag veröffentlichen" }).click();
  await expect(panel.getByText(/Entwurf bleibt erhalten/)).toBeVisible();

  await draft.fill("Geänderter Entwurf");
  await panel.getByRole("button", { name: "Beitrag veröffentlichen" }).click();
  await expect(panel.getByText("Geänderter Entwurf")).toBeVisible();
  expect(api.idempotencyKeys).toHaveLength(2);
  expect(api.idempotencyKeys[0]).not.toBe(api.idempotencyKeys[1]);
});

test("Eine verspätete Polling-Antwort überschreibt keinen gerade veröffentlichten Beitrag", async ({
  page,
}) => {
  await mockApiResponses(page, {
    auth: { authenticated: true, account_id: "e2e-weber", role: "weber" },
  });
  const api = await installConversationApi(page, [], {
    delaySecondList: true,
  });
  const panel = await openFirstNodeConversation(page);
  await expect(panel.getByText(/Noch keine Beiträge/)).toBeVisible();

  await expect.poll(api.delayedListHasStarted, { timeout: 7_000 }).toBe(true);
  await panel.getByLabel("Neuer Beitrag").fill("Neuer Stand");
  await panel.getByRole("button", { name: "Beitrag veröffentlichen" }).click();
  await expect(panel.getByText("Neuer Stand")).toBeVisible();

  api.releaseDelayedList();
  await page.waitForTimeout(250);
  await expect(panel.getByText("Neuer Stand")).toBeVisible();
});

test("Polling läuft nur im sichtbaren aktiven Gesprächstab", async ({
  page,
}) => {
  await mockApiResponses(page, {
    auth: { authenticated: true, account_id: "e2e-weber", role: "weber" },
  });
  const api = await installConversationApi(page, []);
  const panel = await openFirstNodeConversation(page);
  await expect(panel.getByText(/Noch keine Beiträge/)).toBeVisible();
  const visibleCount = api.listRequestCount();

  await page.evaluate(() => {
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      value: "hidden",
    });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await page.waitForTimeout(5_300);
  expect(api.listRequestCount()).toBe(visibleCount);

  await page.evaluate(() => {
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      value: "visible",
    });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await expect.poll(api.listRequestCount).toBeGreaterThan(visibleCount);
  await panel.getByRole("tab", { name: "Übersicht" }).click();
  const inactiveCount = api.listRequestCount();
  await page.waitForTimeout(5_300);
  expect(api.listRequestCount()).toBe(inactiveCount);
});
