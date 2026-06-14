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

  test("ignores invalid URL state without crashing", async ({ page }) => {
    await page.goto("/map?focus=node:&lens=nope&compose=edge");
    // The map shell still renders and no overlay/panel is forced open.
    await expect(page.locator("#map")).toBeVisible();
    await expect(page.getByTestId("filter-overlay")).toHaveCount(0);
    await expect(page.getByTestId("search-overlay")).toHaveCount(0);
    await expect(page.getByTestId("context-panel")).toHaveCount(0);
  });
});
