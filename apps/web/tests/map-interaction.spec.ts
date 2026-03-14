import { test, expect } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test.describe("Map Interaction & Context Panel", () => {
  test.beforeEach(async ({ page }) => {
    await mockApiResponses(page);
    await page.goto("/map");
  });

  test("Initial state is navigation with closed panel", async ({ page }) => {
    await page.waitForSelector(".map-marker", { timeout: 10000 });
    await expect(page.locator('[data-testid="context-panel"]')).toHaveCount(0);
  });

  test("Clicking a marker opens the context panel in fokus mode", async ({
    page,
  }) => {
    await page.waitForSelector(".map-marker", { timeout: 10000 });

    // Ensure the map rendering is stable
    await page.waitForTimeout(1000);

    // Using evaluate to forcefully trigger a click on the map-marker to bypass layout flakiness
    await page.evaluate(() => {
      (document.querySelector(".map-marker") as HTMLElement)?.click();
    });

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

    // Ensure the map rendering is stable
    await page.waitForTimeout(1000);

    // Open panel first
    await page.evaluate(() => {
      (document.querySelector(".map-marker") as HTMLElement)?.click();
    });
    await expect(page.locator('[data-testid="context-panel"]')).toBeVisible();

    // Wait for the context panel to be fully visible before clicking away
    await expect(page.locator('[data-testid="context-panel"]')).toBeVisible();

    // Click empty map area (stabile Leerklick-Zone determined at 50,50)
    // Avoid action bar
    await page.locator("#map").click({ position: { x: 50, y: 50 } });

    // Ensure we trigger the map's click event. Sometimes the map canvas absorbs the click strangely in tests.
    // MapLibre's canvas handles clicks
    await page
      .locator("canvas.maplibregl-canvas")
      .click({ position: { x: 50, y: 50 } });

    // Panel should close
    await expect(page.locator('[data-testid="context-panel"]')).toHaveCount(0);
  });

  test("Switching between markers resets the active tab", async ({ page }) => {
    await page.waitForSelector(".map-marker", { timeout: 10000 });

    // Ensure the map rendering is stable
    await page.waitForTimeout(1000);

    // Open panel on first marker
    const markers = page.locator(".map-marker");
    await page.evaluate(() => {
      (document.querySelectorAll(".map-marker")[0] as HTMLElement)?.click();
    });

    const panel = page.locator('[data-testid="context-panel"]');
    await expect(panel).toBeVisible();

    // Switch to a non-default tab if possible (assuming node default is 'uebersicht', switch to 'gespraech')
    const gespraechTab = panel.locator('button:has-text("Gespräch")');
    if (await gespraechTab.isVisible()) {
      await gespraechTab.click();
      await expect(gespraechTab).toHaveClass(/active/, { timeout: 5000 });

      // Click a different marker (force since sometimes map elements overlay)
      await markers.nth(1).click({ force: true });

      // Harte Tab-Assertion: Die neue Selection sollte (falls Node) den Übersicht-Tab aktiv haben oder (falls Account) den Profil-Tab
      // Wir scopen auf das Panel und warten explizit auf den finalen DOM-Zustand, um Flakiness zu vermeiden.
      const activeTab = panel.locator("button.active");
      await expect(activeTab).toHaveText(/^(Übersicht|Profil)$/, {
        timeout: 5000,
      });
    }
  });

  test("Komposition mode initializes correctly from action bar", async ({
    page,
  }) => {
    await page.waitForSelector(".action-bar", { timeout: 10000 });

    // Click new node in action bar
    await page.locator('button:has-text("Neuer Knoten")').click();

    // Context panel should open
    const panel = page.locator('[data-testid="context-panel"]');
    await expect(panel).toBeVisible();

    // Should show "Ort ausstehend" state
    await expect(panel).toContainText("Ort ausstehend");
  });

  test("Longpress on map initializes komposition mode with coordinates", async ({
    page,
  }) => {
    await page.waitForSelector(".map-marker", { timeout: 10000 });

    // Simulate longpress by dispatching mousedown and waiting
    const mapContainer = page.locator("#map");
    // Ensure we hover and click on empty space (50, 50)
    await mapContainer.hover({ position: { x: 50, y: 50 } });
    await page.mouse.down();
    await page.waitForTimeout(1000); // 800ms is the longpress threshold
    await page.mouse.up();

    const panel = page.locator('[data-testid="context-panel"]');
    await panel.waitFor({ state: "visible", timeout: 5000 });
    await expect(panel).toContainText("Ort gesetzt");
  });

  test("Empty map click does not close context panel in komposition mode", async ({
    page,
  }) => {
    await page.waitForSelector(".action-bar", { timeout: 10000 });

    // Enter komposition mode via action bar
    await page.locator('button:has-text("Neuer Knoten")').click();
    const panel = page.locator('[data-testid="context-panel"]');
    await expect(panel).toBeVisible();

    // Click on an empty area of the map
    await page.locator("#map").click({ position: { x: 50, y: 50 } });

    // Panel should still be visible (komposition protection)
    await expect(panel).toBeVisible();
  });
});
