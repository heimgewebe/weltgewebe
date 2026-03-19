import { expect, test } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test.describe("Map Loader Data Resilience", () => {
  test("gracefully handles partial API failures and displays fallback data via debug badge", async ({
    page,
  }) => {
    // We want to test the behavior when some API endpoints fail concurrently.
    // The expected behavior in +page.ts is to catch the error and use `[]` as fallback
    // for the failed resource, ensuring the map load completes without a full page crash.

    // Base catch-all mocks for styles and auth
    await mockApiResponses(page);

    // Override specific endpoints to simulate partial failure:

    // Nodes will succeed (1 item)
    await page.route("**/api/nodes", async (route) => {
      route.fulfill({
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
      route.fulfill({
        status: 500,
        contentType: "text/plain",
        body: "Internal Server Error",
      });
    });

    // Edges will fail completely (network abort)
    await page.route("**/api/edges", async (route) => {
      route.abort("failed");
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
  });
});
