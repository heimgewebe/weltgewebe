import { test, expect } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

/**
 * Map URL addressing (UI Interaction Doctrine — first executable slice).
 *
 * These tests assert that the `/map` query string is honoured as an
 * *addressing layer* on top of the existing uiView / overlay stores:
 *  - `lens=filter|search` open the matching overlay,
 *  - `focus=<type>:<id>` opens the context panel for an existing entity,
 *  - `compose=node` enters node composition,
 *  - invalid query state is ignored without crashing.
 *
 * Deterministic mock data is layered on top of {@link mockApiResponses} so the
 * deep-link ids stay stable and readable regardless of demo-data changes.
 */
test.describe("Map URL addressing", () => {
  test.beforeEach(async ({ page }) => {
    await mockApiResponses(page);

    // mockApiResponses mocks the local-sovereign style (/local-basemap/style.json,
    // the active mode in the e2e build). This extra route is a defensive mock for
    // the external MapLibre demo style so the test never depends on the network.
    await page.route(
      "https://demotiles.maplibre.org/style.json",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ version: 8, sources: {}, layers: [] }),
        });
      },
    );

    await page.route("**/api/nodes", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "url-node-1",
            title: "URL Deep-Link Node",
            kind: "Event",
            location: { lat: 53.5, lon: 10.0 },
            summary: "A node reachable via focus deep link.",
            tags: [],
            modules: [],
            created_at: "2025-01-01T12:00:00Z",
            updated_at: "2025-01-01T12:00:00Z",
          },
        ]),
      });
    });

    await page.route("**/api/accounts", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "url-acc-1",
            type: "garnrolle",
            title: "URL Deep-Link Garnrolle",
            summary: "A garnrolle reachable via focus deep link.",
            public_pos: { lat: 53.55, lon: 10.05 },
            mode: "verortet",
            radius_m: 0,
            tags: [],
            modules: [],
            created_at: "2025-01-01T12:00:00Z",
          },
        ]),
      });
    });

    await page.route("**/api/edges", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });
  });

  test("opens the filter lens from the URL", async ({ page }) => {
    await page.goto("/map?lens=filter");
    await expect(page.getByTestId("filter-overlay")).toBeVisible();
    await expect(page.getByTestId("search-overlay")).toHaveCount(0);
  });

  test("opens the search lens from the URL", async ({ page }) => {
    await page.goto("/map?lens=search");
    await expect(page.getByTestId("search-overlay")).toBeVisible();
    await expect(page.getByTestId("filter-overlay")).toHaveCount(0);
  });

  test("opens the context panel for a node focus deep link", async ({
    page,
  }) => {
    await page.goto("/map?focus=node:url-node-1");
    const panel = page.getByTestId("context-panel");
    await expect(panel).toBeVisible();
    await expect(panel.locator(".panel-header h2")).toContainText("Knoten");
  });

  test("opens the context panel for a garnrolle focus deep link", async ({
    page,
  }) => {
    await page.goto("/map?focus=garnrolle:url-acc-1");
    const panel = page.getByTestId("context-panel");
    await expect(panel).toBeVisible();
    await expect(panel.locator(".panel-header h2")).toContainText("Garnrolle");
  });

  test("enters node composition from the URL", async ({ page }) => {
    await page.goto("/map?compose=node");
    const panel = page.getByTestId("context-panel");
    await expect(panel).toBeVisible();
    await expect(panel.locator(".state-pending")).toContainText(
      "Ort ausstehend",
    );
  });

  test("opens garnrolle focus panel via account alias", async ({ page }) => {
    await page.goto("/map?focus=account:url-acc-1");
    const panel = page.getByTestId("context-panel");
    await expect(panel).toBeVisible();
    await expect(panel.locator(".panel-header h2")).toContainText("Garnrolle");
  });

  test("does not fall back to lens while a valid focus target is unresolved", async ({
    page,
  }) => {
    await page.goto("/map?focus=node:missing&lens=filter");
    // A valid-but-unresolved focus has priority and blocks the lens fallback.
    await expect(page.locator("#map")).toBeVisible();
    await expect(page.getByTestId("filter-overlay")).toHaveCount(0);
  });

  test("navigating to lens URL does not show stale composition panel", async ({
    page,
  }) => {
    await page.goto("/map?compose=node");
    await expect(page.getByTestId("context-panel")).toBeVisible();

    await page.goto("/map?lens=filter");
    await expect(page.getByTestId("filter-overlay")).toBeVisible();
    await expect(page.getByTestId("context-panel")).toHaveCount(0);
  });

  test("navigating to lens URL does not show stale focus panel", async ({
    page,
  }) => {
    await page.goto("/map?focus=node:url-node-1");
    await expect(page.getByTestId("context-panel")).toBeVisible();

    await page.goto("/map?lens=filter");
    await expect(page.getByTestId("filter-overlay")).toBeVisible();
    await expect(page.getByTestId("context-panel")).toHaveCount(0);
  });

  test("plain map URL does not show stale composition panel", async ({
    page,
  }) => {
    await page.goto("/map?compose=node");
    await expect(page.getByTestId("context-panel")).toBeVisible();

    await page.goto("/map");
    await expect(page.locator("#map")).toBeVisible();
    await expect(page.getByTestId("context-panel")).toHaveCount(0);
    await expect(page.getByTestId("filter-overlay")).toHaveCount(0);
    await expect(page.getByTestId("search-overlay")).toHaveCount(0);
  });

  test("plain map URL does not show stale focus panel", async ({ page }) => {
    await page.goto("/map?focus=node:url-node-1");
    await expect(page.getByTestId("context-panel")).toBeVisible();

    await page.goto("/map");
    await expect(page.locator("#map")).toBeVisible();
    await expect(page.getByTestId("context-panel")).toHaveCount(0);
    await expect(page.getByTestId("filter-overlay")).toHaveCount(0);
    await expect(page.getByTestId("search-overlay")).toHaveCount(0);
  });

  test("unresolved focus closes an already open lens instead of falling back to it", async ({
    page,
  }) => {
    await page.goto("/map?lens=filter");
    await expect(page.getByTestId("filter-overlay")).toBeVisible();

    await page.goto("/map?focus=node:missing&lens=filter");
    await expect(page.locator("#map")).toBeVisible();
    await expect(page.getByTestId("filter-overlay")).toHaveCount(0);
    await expect(page.getByTestId("context-panel")).toHaveCount(0);
  });

  test("opens filter lens even when no markers are available", async ({
    page,
  }) => {
    // Empty datasets (registered after the beforeEach defaults, so they win):
    // the lens is an immediate intent and must not depend on map data.
    await page.route("**/api/nodes", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });
    await page.route("**/api/accounts", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });
    await page.route("**/api/edges", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });

    await page.goto("/map?lens=filter");
    await expect(page.getByTestId("filter-overlay")).toBeVisible();
  });

  test("ignores invalid URL state without crashing", async ({ page }) => {
    await page.goto("/map?focus=node:&lens=nope&compose=edge");
    // The map shell still renders and no overlay/panel is forced open.
    await expect(page.locator("#map")).toBeVisible();
    await expect(page.getByTestId("filter-overlay")).toHaveCount(0);
    await expect(page.getByTestId("search-overlay")).toHaveCount(0);
    await expect(page.getByTestId("context-panel")).toHaveCount(0);
  });
});
