import { expect, test } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test.describe("Map Data Loading", () => {
  test("gracefully handles partial API failures by returning empty arrays", async ({
    page,
  }) => {
    // We want to test the behavior when some API endpoints fail.
    // The expected behavior in +page.ts is to catch the error and use `[]` as fallback
    // for the failed resource, without aborting the Promise.all() or the other fetches.

    // First, set up the base mocks for styles and auth
    await mockApiResponses(page);

    // Now, override the specific data endpoints for this test
    // Nodes will succeed
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

    // Accounts will fail with 500
    await page.route("**/api/accounts", async (route) => {
      route.fulfill({
        status: 500,
        contentType: "text/plain",
        body: "Internal Server Error",
      });
    });

    // Edges will fail with network error (abort)
    await page.route("**/api/edges", async (route) => {
      route.abort("failed");
    });

    // Navigate to the map page
    await page.goto("/map");

    // The map should still load successfully (not crash)
    await expect(page.locator("#map")).toBeVisible();

    // The node that successfully fetched should be visible
    const marker = page.locator('.map-marker[aria-label="Successful Node"]');
    await expect(marker).toBeVisible();

    // Ensure there are no accounts rendered since the request failed and fallback is []
    await expect(page.locator(".marker-account")).toHaveCount(0);

    // Also, we can check that there's exactly 1 marker in total (the node)
    await expect(page.locator(".map-marker, .marker-account")).toHaveCount(1);
  });
});
