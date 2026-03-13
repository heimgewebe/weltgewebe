import { test, expect } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test.describe("Map Interaction & Context Panel", () => {
  test.beforeEach(async ({ page }) => {
    await mockApiResponses(page);
    // intercept MapLibre styling which requires an internet connection in playwright tests
    await page.route("https://demotiles.maplibre.org/style.json", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ version: 8, sources: {}, layers: [] }),
      });
    });
    await page.goto("/map");
  });

  test("Clicking a marker opens the context panel in fokus mode", async ({
    page,
  }) => {
    await page.waitForSelector(".map-marker", { timeout: 10000 });

    // Ensure panel is not initially visible
    await expect(page.locator('[data-testid="context-panel"]')).toHaveCount(0);

    // Click a marker
    await page.locator(".map-marker").first().click();

    // Context panel should open
    const panel = page.locator('[data-testid="context-panel"]');
    await expect(panel).toBeVisible();

    // The panel header should have close button
    const closeBtn = panel.locator(".close-btn");
    await expect(closeBtn).toBeVisible();

    // Click close
    await closeBtn.click({ force: true });
    await expect(page.locator('[data-testid="context-panel"]')).toHaveCount(0);
  });

  test("Clicking empty map area closes the context panel", async ({ page }) => {
    await page.waitForSelector(".map-marker", { timeout: 10000 });

    // Open panel first
    await page.locator(".map-marker").first().click();
    await expect(page.locator('[data-testid="context-panel"]')).toBeVisible();

    // Click empty map area (bottom left corner might be safe)
    await page.mouse.click(10, 10);

    // Panel should close
    await expect(page.locator('[data-testid="context-panel"]')).toHaveCount(0);
  });
});
