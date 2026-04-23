import { expect, test } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test.describe("Map Loader Data Resilience", () => {
  test("gracefully handles partial API failures and displays degraded state banner", async ({
    page,
  }) => {
    // We want to test the behavior when some API endpoints fail concurrently.
    // The expected behavior in +page.ts is to catch the error and use `[]` as fallback
    // for the failed resource, ensuring the map load completes without a full page crash.
    // Additionally, the route now returns explicit loadState and resourceStatus.

    // Base catch-all mocks for styles and auth
    await mockApiResponses(page);

    // Override specific endpoints to simulate partial failure:

    // Nodes will succeed (1 item)
    await page.route("**/api/nodes", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "node-1",
            title: "Successful Node",
            kind: "Event",
            location: { lat: 53.5, lon: 10.0 },
            summary: "A test event node.",
          },
        ]),
      });
    });

    // Accounts will fail with a 500 error
    await page.route("**/api/accounts", async (route) => {
      await route.fulfill({
        status: 500,
        contentType: "text/plain",
        body: "Internal Server Error",
      });
    });

    // Edges will fail completely (network abort)
    await page.route("**/api/edges", async (route) => {
      await route.abort("failed");
    });

    // Navigate to the map page
    await page.goto("/map");

    // The map container should still render (no crash)
    await expect(page.locator("#map")).toBeVisible();

    // Verify the data output directly via the debug badge.
    // This stable test signal confirms the loader returned:
    // { nodes: [1 item], accounts: [], edges: [] }
    const debugBadge = page.getByTestId("debug-badge");
    await expect(debugBadge).toBeVisible();
    await expect(debugBadge).toContainText("Nodes: 1 / Accounts: 0 / Edges: 0");

    // Phase 1: Verify the degraded state banner is visible for partial failures
    const partialBanner = page.getByTestId("load-state-partial");
    await expect(partialBanner).toBeVisible();
    await expect(partialBanner).toContainText(
      "Einige Kartendaten konnten nicht geladen werden",
    );
    await expect(partialBanner).toContainText("Garnrollen");
    await expect(partialBanner).toContainText("Fäden");
  });

  test("shows failed state when all API resources fail", async ({ page }) => {
    await mockApiResponses(page);

    // All three endpoints fail
    await page.route("**/api/nodes", async (route) => {
      await route.fulfill({
        status: 500,
        contentType: "text/plain",
        body: "Internal Server Error",
      });
    });

    await page.route("**/api/accounts", async (route) => {
      await route.abort("failed");
    });

    await page.route("**/api/edges", async (route) => {
      await route.fulfill({
        status: 503,
        contentType: "text/plain",
        body: "Service Unavailable",
      });
    });

    await page.goto("/map");

    await expect(page.locator("#map")).toBeVisible();

    // Verify the failed state banner
    const failedBanner = page.getByTestId("load-state-failed");
    await expect(failedBanner).toBeVisible();
    await expect(failedBanner).toContainText(
      "Kartendaten konnten nicht geladen werden",
    );

    // No partial banner should be visible
    await expect(page.getByTestId("load-state-partial")).toHaveCount(0);
  });

  test("shows no degraded banner when all API resources succeed", async ({
    page,
  }) => {
    await mockApiResponses(page);

    await page.goto("/map");

    await expect(page.locator("#map")).toBeVisible();

    // No degraded banners should be visible
    await expect(page.getByTestId("load-state-partial")).toHaveCount(0);
    await expect(page.getByTestId("load-state-failed")).toHaveCount(0);
  });

  test("debug badge shows separated API and basemap modes", async ({
    page,
  }) => {
    await mockApiResponses(page);

    await page.goto("/map");

    const debugBadge = page.getByTestId("debug-badge");
    await expect(debugBadge).toBeVisible();

    // Phase 4: API and basemap modes are now separately visible
    await expect(debugBadge).toContainText("API: local");
    await expect(debugBadge).toContainText("Basemap: local-sovereign");
  });
});
