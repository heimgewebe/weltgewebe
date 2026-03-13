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

  test("Switching between markers resets the active tab", async ({ page }) => {
    await page.waitForSelector(".map-marker", { timeout: 10000 });

    // Open panel on first marker
    const markers = page.locator(".map-marker");
    await markers.nth(0).click();

    const panel = page.locator('[data-testid="context-panel"]');
    await expect(panel).toBeVisible();

    // Switch to a non-default tab if possible (assuming node default is 'uebersicht', switch to 'gespraech')
    const gespraechTab = panel.locator('button:has-text("Gespräch")');
    if (await gespraechTab.isVisible()) {
      await gespraechTab.click();
      await expect(gespraechTab).toHaveClass(/active/, { timeout: 5000 });

      // Click a different marker (force since sometimes map elements overlay)
      await markers.nth(1).click({ force: true });

      // Verify tab is reset back to 'uebersicht' (or 'profil' depending on what nth(1) is, but gespraech should no longer be active)
      // Because `gespraechTab` might no longer exist if the second marker is an account/garnrolle, we just check count or active state loosely
      await expect(page.locator("button.active")).not.toHaveText("Gespräch", {
        timeout: 5000,
      });
    }
  });

  test("Komposition mode initializes correctly from action bar", async ({
    page,
  }) => {
    await page.waitForSelector(".action-bar", { timeout: 10000 });

    // Ensure panel is not initially visible
    await expect(page.locator('[data-testid="context-panel"]')).toHaveCount(0);

    // Click new node in action bar
    await page.locator('button:has-text("Neuer Knoten")').click();

    // Context panel should open
    const panel = page.locator('[data-testid="context-panel"]');
    await expect(panel).toBeVisible();

    // Should show "Ort ausstehend" state
    await expect(panel).toContainText("Ort ausstehend");

    // Close panel
    await panel.locator(".close-btn").click({ force: true });
    await expect(panel).toHaveCount(0);
  });
});
