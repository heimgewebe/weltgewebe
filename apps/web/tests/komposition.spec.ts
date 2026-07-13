import { test, expect, type Page } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

const WEBER_ACCOUNT_ID = "weber-e2e-1";

async function mockAuthRole(
  page: Page,
  auth: { authenticated: boolean; account_id?: string; role: string },
) {
  await page.route("**/api/auth/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(auth),
    }),
  );
}

async function mockMapTiles(page: Page) {
  await page.route("https://demotiles.maplibre.org/style.json", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ version: 8, sources: {}, layers: [] }),
    });
  });
}

async function gotoMapAs(
  page: Page,
  auth: { authenticated: boolean; account_id?: string; role: string },
) {
  await mockApiResponses(page);
  await mockAuthRole(page, auth);
  await mockMapTiles(page);
  await page.goto("/map");
  await page.waitForSelector(".action-bar", { timeout: 10000 });
}

async function longPressMapCenter(page: Page) {
  const mapContainer = page.locator("#map");
  await mapContainer.hover({ position: { x: 50, y: 50 } });
  await page.mouse.down();
  await page.waitForTimeout(1000); // 800ms threshold
  await page.mouse.up();
}

test.describe("Komposition Flow (weber)", () => {
  test.beforeEach(async ({ page }) => {
    await gotoMapAs(page, {
      authenticated: true,
      account_id: WEBER_ACCOUNT_ID,
      role: "weber",
    });
  });

  test("Komposition form requires location, name, and address to submit", async ({
    page,
  }) => {
    await page.locator('button:has-text("Knoten knüpfen")').click();
    const panel = page.locator('[data-testid="context-panel"]');
    await expect(panel).toBeVisible();

    await expect(panel.locator(".state-pending")).toContainText(
      "Ort ausstehend",
    );

    const submitBtn = panel.locator('button[type="submit"]');
    await expect(submitBtn).toBeDisabled();

    await page.fill("#title", "Test Node");
    await expect(submitBtn).toBeDisabled(); // still no location, no address

    await page.fill("#address", "Teststraße 1, Teststadt");
    await expect(submitBtn).toBeDisabled(); // still no location

    await longPressMapCenter(page);
    await expect(panel.locator(".state-set")).toContainText("Ort gewählt");
    await expect(submitBtn).toBeEnabled();

    await page.fill("#address", "");
    await expect(submitBtn).toBeDisabled();
    await page.fill("#address", "Teststraße 1, Teststadt");
    await expect(submitBtn).toBeEnabled();

    await page.fill("#title", "");
    await expect(submitBtn).toBeDisabled();
  });

  test("Cancel flow cleans up state and closes panel", async ({ page }) => {
    await page.locator('button:has-text("Knoten knüpfen")').click();
    const panel = page.locator('[data-testid="context-panel"]');
    await expect(panel).toBeVisible();

    await panel.locator('button:has-text("Abbrechen")').click();

    await expect(panel).toHaveCount(0);
  });

  test("Successful submit creates the node, links it to the account, reloads data, and focuses it", async ({
    page,
  }) => {
    const nodeRequest = page.waitForRequest(
      (req) => req.url().endsWith("/api/nodes") && req.method() === "POST",
    );
    const edgeRequest = page.waitForRequest(
      (req) => req.url().endsWith("/api/edges") && req.method() === "POST",
    );

    await page.locator('button:has-text("Knoten knüpfen")').click();
    const panel = page.locator('[data-testid="context-panel"]');

    await longPressMapCenter(page);
    await expect(panel.locator(".state-set")).toContainText("Ort gewählt");

    await page.fill("#title", "My Awesome Node");
    await page.fill("#address", "Musterstraße 1, 12345 Musterstadt");
    await page.fill("#description", "This is a description");
    await page.selectOption("#nodeType", "event");

    const submitBtn = panel.locator('button[type="submit"]');
    await expect(submitBtn).toBeEnabled();
    await submitBtn.click();

    // Node created with the form's values before any edge is attempted.
    const nodeReq = await nodeRequest;
    const nodePayload = nodeReq.postDataJSON();
    expect(nodePayload).toMatchObject({
      title: "My Awesome Node",
      kind: "event",
      address: "Musterstraße 1, 12345 Musterstadt",
      summary: "This is a description",
    });
    expect(typeof nodePayload.location?.lat).toBe("number");
    expect(typeof nodePayload.location?.lon).toBe("number");
    expect(nodePayload.operation_id).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
    );

    // Edge links the current account to the new node.
    const edgeReq = await edgeRequest;
    const edgePayload = edgeReq.postDataJSON();
    expect(edgePayload.source_id).toBe(WEBER_ACCOUNT_ID);
    expect(edgePayload.source_type).toBe("account");
    expect(edgePayload.target_type).toBe("node");
    expect(edgePayload.edge_kind).toBe("reference");
    expect(edgePayload.operation_id).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
    );

    // Data reloaded: the debug badge's node count increases by one.
    const debugBadge = page.locator('[data-testid="debug-badge"]');
    await expect(debugBadge).toContainText("Nodes: 2");

    // The panel leaves komposition mode and the new node is focused: the
    // context panel now shows "Knoten" instead of the create form.
    await expect(panel.locator("h2")).toContainText("Knoten");
  });

  test("Edge creation failure shows a partial-success message and reuses the operation id on retry", async ({
    page,
  }) => {
    const operationIds: string[] = [];
    let edgeAttempts = 0;
    await page.route("**/api/edges", async (route) => {
      if (route.request().method() !== "POST") {
        return route.fallback();
      }
      const payload = route.request().postDataJSON();
      operationIds.push(payload.operation_id);
      edgeAttempts += 1;
      if (edgeAttempts === 1) {
        return route.fulfill({ status: 500 });
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "mock-edge-replay",
          ...payload,
          created_at: new Date().toISOString(),
        }),
      });
    });

    await page.locator('button:has-text("Knoten knüpfen")').click();
    const panel = page.locator('[data-testid="context-panel"]');

    await longPressMapCenter(page);
    await expect(panel.locator(".state-set")).toContainText("Ort gewählt");

    await page.fill("#title", "Partial Node");
    await page.fill("#address", "Somewhere 1");

    await panel.locator('button[type="submit"]').click();

    // Clear, honest partial-success messaging — never a silent failure and
    // never a false claim that node+edge were created atomically.
    await expect(panel).toContainText("Knoten gespeichert");
    await expect(panel).toContainText("Faden");
    await expect(
      panel.locator('button:has-text("Faden erneut knüpfen")'),
    ).toBeVisible();
    await expect(
      panel.locator('button:has-text("Ohne Faden fortfahren")'),
    ).toBeVisible();

    // The global close control must not discard this partial-success state.
    await panel.getByRole("button", { name: "Schließen" }).click();
    await expect(panel).toBeVisible();
    await expect(panel).toContainText("Der Knoten ist bereits gespeichert");

    await panel.locator('button:has-text("Faden erneut knüpfen")').click();
    await expect(panel.locator("h2")).toContainText("Knoten");
    expect(operationIds).toHaveLength(2);
    expect(operationIds[1]).toBe(operationIds[0]);
  });

  test("Node retry reuses its operation id while unchanged form data starts no second action", async ({
    page,
  }) => {
    const operationIds: string[] = [];
    let attempts = 0;
    await page.route("**/api/nodes", async (route) => {
      if (route.request().method() !== "POST") {
        return route.fallback();
      }
      const payload = route.request().postDataJSON();
      operationIds.push(payload.operation_id);
      attempts += 1;
      if (attempts === 1) {
        return route.fulfill({ status: 500 });
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "mock-node-replay",
          ...payload,
          tags: [],
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }),
      });
    });

    await page.locator('button:has-text("Knoten knüpfen")').click();
    const panel = page.locator('[data-testid="context-panel"]');
    await longPressMapCenter(page);
    await page.fill("#title", "Retry Node");
    await page.fill("#address", "Retrystraße 1");

    await panel.locator('button[type="submit"]').click();
    await expect(panel.locator('[role="alert"]')).toBeVisible();
    await panel.locator('button[type="submit"]').click();

    await expect(panel.locator("h2")).toContainText("Knoten");
    expect(operationIds).toHaveLength(2);
    expect(operationIds[1]).toBe(operationIds[0]);
  });
});

test.describe("Komposition Flow (gast/anonymous)", () => {
  test("Guests get no functional write path: no action-bar button, no longpress panel", async ({
    page,
  }) => {
    await gotoMapAs(page, { authenticated: false, role: "gast" });

    await expect(page.locator('button:has-text("Knoten knüpfen")')).toHaveCount(
      0,
    );

    await longPressMapCenter(page);
    await expect(page.locator('[data-testid="context-panel"]')).toHaveCount(0);
  });
});
