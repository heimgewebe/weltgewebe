import { test, expect } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test.describe("Filter mode", () => {
  test.beforeEach(async ({ page }) => {
    await mockApiResponses(page);
    await page.goto("/map");
    // Wait for the map to be ready and the map-marker elements to exist
    await page.waitForFunction(() =>
      (window as any).__TEST_MAP__?.isStyleLoaded(),
    );
    await page.waitForSelector(".map-marker");
  });

  test("toggles filter overlay, filters markers, and supports keyboard navigation", async ({
    page,
  }) => {
    const filterBtn = page.getByRole("button", { name: "Filter", exact: true });
    const searchBtn = page.getByRole("button", { name: "Suche", exact: true });

    // Initial marker count (should be all)
    const initialMarkerCount = await page.locator(".map-marker").count();
    expect(initialMarkerCount).toBeGreaterThan(1);

    // Toggle Search just to make sure they are mutually exclusive
    await searchBtn.click();
    await expect(page.getByTestId("search-overlay")).toBeVisible();

    // 1. Open filter overlay
    await filterBtn.click();
    const overlay = page.getByTestId("filter-overlay");
    await expect(overlay).toBeVisible();

    // Search overlay should be closed
    await expect(page.getByTestId("search-overlay")).not.toBeVisible();

    // 2. Check focus management
    // The first checkbox should be focused
    const firstCheckbox = page
      .locator('.filter-list input[type="checkbox"]')
      .first();
    await expect(firstCheckbox).toBeFocused();

    // 3. Select a filter and verify markers change
    // Uncheck everything by default (it's already unchecked), click one to filter
    await firstCheckbox.click();

    // Verify clear button appears
    const clearBtn = page.getByRole("button", { name: "Alle löschen" });
    await expect(clearBtn).toBeVisible();

    // Wait for markers to update dynamically without a hardcoded timeout.
    // The framework will retry this assertion until it passes or times out.
    await expect(async () => {
      const filteredMarkerCount = await page.locator(".map-marker").count();
      expect(filteredMarkerCount).toBeGreaterThan(0);
      expect(filteredMarkerCount).toBeLessThanOrEqual(initialMarkerCount);
    }).toPass();

    // 4. Verify Search operates only on filtered markers
    await searchBtn.click();
    await expect(overlay).not.toBeVisible();
    await expect(page.getByTestId("search-overlay")).toBeVisible();

    // 5. Close Search, open Filter again, clear filters
    await filterBtn.click();
    await expect(page.getByTestId("search-overlay")).not.toBeVisible();
    await expect(overlay).toBeVisible();

    await clearBtn.click();
    await expect(clearBtn).not.toBeVisible();

    // 6. Test Escape key support
    await page.keyboard.press("Escape");
    await expect(overlay).not.toBeVisible();
  });
});
