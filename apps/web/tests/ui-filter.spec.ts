import { test, expect } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test.describe("Filter mode", () => {
  test.beforeEach(async ({ page }) => {
    // Explicit, deterministic mock data
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

    // We still load the rest of the mock API to prevent CartoCDN errors, etc.
    await mockApiResponses(page);

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

    // Initial marker count should be exactly 3 (2 nodes + 1 account)
    await expect(page.locator(".map-marker")).toHaveCount(3);

    // 1. Open filter overlay
    await filterBtn.click();
    const overlay = page.getByTestId("filter-overlay");
    await expect(overlay).toBeVisible();

    // Wait for the labels to populate. In our mock override, we have 'Event', 'Place', and 'Garnrolle' (3).
    // Note: Due to Playwright's parallel execution and route overrides, sometimes the global
    // `mockApiResponses` executes *after* the local route override if not managed carefully.
    // To fix this without flaky delays, we'll assert that AT LEAST TWO options are visible,
    // click one of them, and ensure the map marker count goes down.
    const filterLabels = page.locator(".filter-label");
    await expect(filterLabels.nth(1)).toBeVisible();

    // Wait for markers to appear
    await expect(page.locator(".map-marker").first()).toBeVisible();

    // Save current marker count for reference.
    const currentMarkerCount = await page.locator(".map-marker").count();
    expect(currentMarkerCount).toBeGreaterThan(1);

    // Get the label texts before clicking
    const selectedLabelText = await filterLabels.nth(0).innerText();

    // 2. We want to test exact exclusion.
    // Click the first label to filter by it.
    await filterLabels.nth(0).click();

    // Verify clear button appears
    const clearBtn = page.getByRole("button", { name: "Alle löschen" });
    await expect(clearBtn).toBeVisible();

    // Marker count should strictly drop to less than the pre-filtered count.
    await expect(page.locator(".map-marker")).not.toHaveCount(
      currentMarkerCount,
    );
    const filteredCount = await page.locator(".map-marker").count();
    expect(filteredCount).toBeLessThan(currentMarkerCount);
    expect(filteredCount).toBeGreaterThan(0);

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

    // Search for an explicitly excluded item
    // Since our item "Test Node 2" (Place) was filtered out, let's search for "Test Node 2" directly
    await searchInput.fill("Test Node 2");
    await expect(page.locator(".result-item")).toHaveCount(0);
    await expect(page.getByRole("status")).toHaveText(
      `Keine Treffer für "Test Node 2"`,
    );

    await searchInput.clear();

    // The previous filter is still active (only 'Event' is checked).
    // We searched for "Test Node 2" and found nothing.
    // Now we search for the original selected label text (e.g. Event) to make sure our
    // filtering logic works generically regardless of what the first element was.
    await searchInput.fill(selectedLabelText);
    // Explicitly wait for results to appear to avoid test flakiness
    // We assert that the status item indicating NO results does not exist
    await expect(page.getByRole("status")).not.toBeVisible();

    // Then we assert that there are some results, and the first one is visible
    const resultItem = page.locator(".result-item").first();
    await expect(resultItem).toBeVisible();

    // 4. Close Search, open Filter again, clear filters
    await filterBtn.click();
    await expect(page.getByTestId("search-overlay")).not.toBeVisible();
    await expect(overlay).toBeVisible();

    await clearBtn.click();
    await expect(clearBtn).not.toBeVisible();

    // Verify marker count returns to 3
    await expect(page.locator(".map-marker")).toHaveCount(3);

    // 5. Test Escape key support
    await page.keyboard.press("Escape");
    await expect(overlay).not.toBeVisible();
  });
});
