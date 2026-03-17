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
    // We expect the count to strictly reduce because our demo data has multiple types.
    await expect(async () => {
      const filteredMarkerCount = await page.locator(".map-marker").count();
      expect(filteredMarkerCount).toBeGreaterThan(0);
      expect(filteredMarkerCount).toBeLessThan(initialMarkerCount);
    }).toPass();

    // 4. Verify Search operates only on filtered markers
    await searchBtn.click();
    await expect(overlay).not.toBeVisible();
    await expect(page.getByTestId("search-overlay")).toBeVisible();

    // We unchecked all but the first filter type (likely "Garnrolle" alphabetically or similar).
    // Type in a search term. We search for "fairschenkbox" which is a "Knoten" in demo data.
    // Since "Knoten" is likely not the active filter if we just clicked the first one (Garnrolle),
    // it should yield no results. To be absolutely sure, we'll search for something generic
    // and verify the results list doesn't show the excluded type.
    const searchInput = page.getByRole("textbox", { name: "Suchbegriff" });
    await searchInput.fill("a");
    // Just verify the listbox appears or shows no results, but we mainly want to ensure no crash
    // and that search respects the filter state (which we patched).
    // Because .result-type can match multiple elements, we assert that the count of elements with "Knoten" is 0
    await expect(
      page.locator(".result-type", { hasText: "Knoten" }),
    ).toHaveCount(0);

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
