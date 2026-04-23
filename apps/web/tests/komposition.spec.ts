import { test, expect } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test.describe("Komposition Flow", () => {
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
    await page.waitForSelector(".action-bar", { timeout: 10000 });
  });

  test("Komposition form requires location and title to submit", async ({
    page,
  }) => {
    // Enter komposition mode
    await page.locator('button:has-text("Neuer Knoten")').click();
    const panel = page.locator('[data-testid="context-panel"]');
    await expect(panel).toBeVisible();

    // Check that we are in "Ort ausstehend" state
    await expect(panel.locator(".state-pending")).toContainText(
      "Ort ausstehend",
    );

    // The submit button should be disabled since there's no location or title
    const submitBtn = panel.locator('button[type="submit"]');
    await expect(submitBtn).toBeDisabled();

    // Fill the title
    await page.fill("#title", "Test Node");

    // Still disabled because no location
    await expect(submitBtn).toBeDisabled();

    // Simulate longpress on map to set location
    const mapContainer = page.locator("#map");
    await mapContainer.hover({ position: { x: 50, y: 50 } });
    await page.mouse.down();
    await page.waitForTimeout(1000); // 800ms threshold
    await page.mouse.up();

    // Wait for state to change to "Ort gesetzt"
    await expect(panel.locator(".state-set")).toContainText("Ort gesetzt");

    // Submit button should now be enabled
    await expect(submitBtn).toBeEnabled();

    // Clear the title
    await page.fill("#title", "");

    // Focus out or click away might be needed to trigger validation, but svelte binding is immediate
    // Submit button should be disabled again
    await expect(submitBtn).toBeDisabled();
  });

  test("Cancel flow cleans up state and closes panel", async ({ page }) => {
    // Enter komposition mode
    await page.locator('button:has-text("Neuer Knoten")').click();
    const panel = page.locator('[data-testid="context-panel"]');
    await expect(panel).toBeVisible();

    // Click cancel button
    await panel.locator('button:has-text("Abbrechen")').click();

    // Panel should close
    await expect(panel).toHaveCount(0);
  });

  test("Successful submit transitions back to navigation", async ({ page }) => {
    // Enter komposition mode
    await page.locator('button:has-text("Neuer Knoten")').click();
    const panel = page.locator('[data-testid="context-panel"]');

    // Simulate longpress on map to set location
    const mapContainer = page.locator("#map");
    await mapContainer.hover({ position: { x: 50, y: 50 } });
    await page.mouse.down();
    await page.waitForTimeout(1000);
    await page.mouse.up();

    await expect(panel.locator(".state-set")).toContainText("Ort gesetzt");

    // Fill form
    await page.fill("#title", "My Awesome Node");
    await page.fill("#description", "This is a description");
    await page.selectOption("#nodeType", "event");

    // Click submit
    const submitBtn = panel.locator('button[type="submit"]');
    await expect(submitBtn).toBeEnabled();
    await submitBtn.click();

    // Panel should close (transition to navigation)
    await expect(panel).toHaveCount(0);
  });
});
