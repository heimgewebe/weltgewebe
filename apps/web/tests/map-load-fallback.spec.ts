import { expect, test } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test.describe("Map Loader Data Contract", () => {
  test("gracefully handles partial API failures by resolving to empty fallback arrays", async ({
    page,
  }) => {
    // We want to test the behavior when some API endpoints fail concurrently.
    // The expected semantic contract in +page.ts is to catch the error and use `[]` as fallback
    // for the failed resource, without aborting the Promise.all() or the other fetches.

    // First, set up the base catch-all mocks for styles and auth
    await mockApiResponses(page);

    // Now, override the specific data endpoints for this test to explicitly test partial failure.
    // The order of page.route matters in Playwright: these more specific, later-registered
    // routes will correctly take precedence over the catch-all in mockApiResponses.

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

    // The map should still load successfully (not crash)
    await expect(page.locator("#map")).toBeVisible();

    // To directly prove the loader returned `{ nodes: [1], accounts: [], edges: [] }`
    // without relying purely on brittle DOM marker rendering logic, we assert against
    // the debug-badge which explicitly renders the array lengths from the page data in TEST mode.
    const debugBadge = page.getByTestId("debug-badge");
    await expect(debugBadge).toBeVisible();
    await expect(debugBadge).toContainText("Nodes: 1 / Accounts: 0 / Edges: 0");
  });
});
