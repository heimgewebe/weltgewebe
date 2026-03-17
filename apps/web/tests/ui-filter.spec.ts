import { test, expect } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test.describe("Filter mode", () => {
  test.beforeEach(async ({ page }) => {
    // 1. Load the base mock API to prevent CartoCDN errors, etc.
    await mockApiResponses(page);

    // 2. Explicit, deterministic mock data overrides
    await page.route("**/api/nodes", async (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "node-1",
            title: "Test Node 1",
            kind: "Event",
            location: { lat: 53.5, lon: 10.0 },
            summary: "A test event node.",
          },
          {
            id: "node-2",
            title: "Test Node 2",
            kind: "Place",
            location: { lat: 53.6, lon: 10.1 },
            summary: "A test place node.",
          },
        ]),
      });
    });

    await page.route("**/api/accounts", async (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "account-1",
            title: "Test Account",
            type: "Garnrolle",
            public_pos: { lat: 53.55, lon: 10.05 },
            summary: "A test account.",
          },
        ]),
      });
    });

    await page.route("**/api/edges", async (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]), // No edges needed for this test
      });
    });

    await page.goto("/map");
    // Wait for the map to be ready
    await page.waitForFunction(() =>
      (window as any).__TEST_MAP__?.isStyleLoaded(),
    );
    await page.waitForSelector(".map-marker");
  });

  test("deterministically toggles filter, impacts visible markers, and coordinates with search", async ({
    page,
  }) => {
    const filterBtn = page.getByRole("button", { name: "Filter", exact: true });
    const searchBtn = page.getByRole("button", { name: "Suche", exact: true });

    // Use an explicit, robust selector to cover both standard nodes and accounts.
    // Initial marker count should be exactly 3 (2 nodes + 1 account)
    const markerSelector = ".map-marker, .marker-account";
    await expect(page.locator(markerSelector)).toHaveCount(3);

    // 1. Open filter overlay
    await filterBtn.click();
    const overlay = page.getByTestId("filter-overlay");
    await expect(overlay).toBeVisible();

    // Our explicit mock defines exactly 3 types: "Event", "Place", and "Garnrolle".
    // We expect the overlay to list all of them.
    const filterLabels = page.locator(".filter-label");
    await expect(filterLabels).toHaveCount(3);

    // Check they contain the expected text (order might vary)
    await expect(
      page.locator("label.filter-item", { hasText: "Event" }),
    ).toBeVisible();
    await expect(
      page.locator("label.filter-item", { hasText: "Place" }),
    ).toBeVisible();
    await expect(
      page.locator("label.filter-item", { hasText: "Garnrolle" }),
    ).toBeVisible();

    // 2. Test exact exclusion dynamically
    // Currently, all 3 are technically "visible" on the map (no active filters means show all).
    // We filter to ONLY show "Event".
    const eventLabel = page.locator("label.filter-item", { hasText: "Event" });
    await eventLabel.click();

    // Verify clear button appears
    const clearBtn = page.getByRole("button", { name: "Alle löschen" });
    await expect(clearBtn).toBeVisible();

    // The marker count MUST strictly drop to 1 because there is exactly 1 Event node in the mock.
    await expect(page.locator(markerSelector)).toHaveCount(1);

    // 3. Verify Search operates ONLY on the filtered base
    await searchBtn.click();
    await expect(overlay).not.toBeVisible();
    await expect(page.getByTestId("search-overlay")).toBeVisible();

    const searchInput = page.getByRole("textbox", { name: "Suchbegriff" });

    // Wait until search box is ready
    await expect(searchInput).toBeVisible();

    // Wait until search box is ready.
    // It's possible the test environment intercepts the first character if typed too quickly,
    // so we clear it explicitly first.
    await searchInput.clear();

    // Search for an explicitly excluded node item
    // Since our item "Test Node 2" (Place) was filtered out, let's search for "Test Node 2" directly
    await searchInput.fill("Test Node 2");
    await expect(page.locator(".result-item")).toHaveCount(0);
    await expect(page.getByRole("status")).toHaveText(
      `Keine Treffer für "Test Node 2"`,
    );

    await searchInput.clear();

    // Search for an explicitly excluded account item
    // Since our item "Test Account" (Garnrolle) was filtered out, let's search for "Test Account"
    await searchInput.fill("Test Account");
    await expect(page.locator(".result-item")).toHaveCount(0);
    await expect(page.getByRole("status")).toHaveText(
      `Keine Treffer für "Test Account"`,
    );

    await searchInput.clear();

    // Search for the strictly included item
    // In our mock, 'Test Node 1' is an 'Event'.
    await searchInput.fill("Test Node 1");
    // Explicitly wait for results to appear to avoid test flakiness
    // We assert that exactly 1 result is visible
    await expect(page.locator(".result-item")).toHaveCount(1);
    await expect(page.locator(".result-item").first()).toHaveText(
      /Test Node 1/,
    );

    // 4. Close Search, open Filter again, clear filters
    await filterBtn.click();
    await expect(page.getByTestId("search-overlay")).not.toBeVisible();
    await expect(overlay).toBeVisible();

    await clearBtn.click();
    await expect(clearBtn).not.toBeVisible();

    // Assert marker count returns to 3
    await expect(page.locator(markerSelector)).toHaveCount(3);

    // 5. Test Escape key support
    await page.keyboard.press("Escape");
    await expect(overlay).not.toBeVisible();
  });
});
