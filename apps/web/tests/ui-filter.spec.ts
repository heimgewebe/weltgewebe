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

  test("Case A: No filters -> Search global", async ({ page }) => {
    const searchBtn = page.getByRole("button", { name: "Suche", exact: true });
    await searchBtn.click();

    const searchOverlay = page.getByTestId("search-overlay");
    await expect(searchOverlay).toBeVisible();

    const searchInput = page.getByRole("textbox", { name: "Suchbegriff" });
    await expect(searchInput).toBeVisible();

    // Search for a node item
    await searchInput.clear();
    await searchInput.fill("Test Node 2");
    await expect(page.locator(".result-item")).toHaveCount(1);
    await expect(page.locator(".result-item").first()).toHaveText(
      /Test Node 2/,
    );

    // Search for an account item
    await searchInput.clear();
    await searchInput.fill("Test Account");
    await expect(page.locator(".result-item")).toHaveCount(1);
    await expect(page.locator(".result-item").first()).toHaveText(
      /Test Account/,
    );
  });

  test("Case B & E: Active filter -> Search strictly bounded, and Clear Filters", async ({
    page,
  }) => {
    const filterBtn = page.getByRole("button", { name: "Filter", exact: true });
    const searchBtn = page.getByRole("button", { name: "Suche", exact: true });
    const markerSelector = ".map-marker, .marker-account";

    // Initial marker count is 3
    await expect(page.locator(markerSelector)).toHaveCount(3);

    // Open filter overlay
    await filterBtn.click();
    const filterOverlay = page.getByTestId("filter-overlay");
    await expect(filterOverlay).toBeVisible();

    // Filter to ONLY show "Event"
    const eventLabel = page.locator("label.filter-item", { hasText: "Event" });
    await eventLabel.click();

    // Marker count drops strictly to 1
    await expect(page.locator(markerSelector)).toHaveCount(1);

    // Open search, verify it strictly respects the active filter
    await searchBtn.click();
    await expect(filterOverlay).not.toBeVisible();

    const searchInput = page.getByRole("textbox", { name: "Suchbegriff" });
    await expect(searchInput).toBeVisible();

    // Search for excluded items should return no results
    await searchInput.clear();
    await searchInput.fill("Test Node 2");
    await expect(page.locator(".result-item")).toHaveCount(0);
    await expect(page.getByRole("status")).toHaveText(
      `Keine Treffer für "Test Node 2"`,
    );

    await searchInput.clear();
    await searchInput.fill("Test Account");
    await expect(page.locator(".result-item")).toHaveCount(0);
    await expect(page.getByRole("status")).toHaveText(
      `Keine Treffer für "Test Account"`,
    );

    // Search for included item
    await searchInput.clear();
    await searchInput.fill("Test Node 1");
    await expect(page.locator(".result-item")).toHaveCount(1);
    await expect(page.locator(".result-item").first()).toHaveText(
      /Test Node 1/,
    );

    // Case E: Clear Filters resets marker count
    await filterBtn.click();
    const clearBtn = page.getByRole("button", { name: "Alle löschen" });
    await clearBtn.click();
    await expect(clearBtn).not.toBeVisible();
    await expect(page.locator(markerSelector)).toHaveCount(3);
  });

  test("Case C: Overlay exclusivity and focus shift", async ({ page }) => {
    const filterBtn = page.getByRole("button", { name: "Filter", exact: true });
    const searchBtn = page.getByRole("button", { name: "Suche", exact: true });

    const filterOverlay = page.getByTestId("filter-overlay");
    const searchOverlay = page.getByTestId("search-overlay");

    // Open search
    await searchBtn.click();
    await expect(searchOverlay).toBeVisible();
    await expect(filterOverlay).not.toBeVisible();

    // Open filter -> Search closes, focus should be inside filter
    await filterBtn.click();
    await expect(filterOverlay).toBeVisible();
    await expect(searchOverlay).not.toBeVisible();
    const firstCheckbox = page.locator('input[type="checkbox"]').first();
    await expect(firstCheckbox).toBeFocused();

    // Open search -> Filter closes, focus should be inside search
    await searchBtn.click();
    await expect(searchOverlay).toBeVisible();
    await expect(filterOverlay).not.toBeVisible();
    const searchInput = page.getByRole("textbox", { name: "Suchbegriff" });
    await expect(searchInput).toBeFocused();
  });

  test("Case D: Focus management for Filter", async ({ page }) => {
    const filterBtn = page.getByRole("button", { name: "Filter", exact: true });

    // Open filter overlay
    await filterBtn.click();
    const filterOverlay = page.getByTestId("filter-overlay");
    await expect(filterOverlay).toBeVisible();

    // First checkbox should be focused
    const firstCheckbox = page.locator('input[type="checkbox"]').first();
    await expect(firstCheckbox).toBeFocused();

    // Close with Escape
    await page.keyboard.press("Escape");
    await expect(filterOverlay).not.toBeVisible();

    // Focus lands back on Filter button
    await expect(filterBtn).toBeFocused();
  });
});
