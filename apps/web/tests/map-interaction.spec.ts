import { test, expect } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test.describe("Map Interaction & Context Panel", () => {
  test.beforeEach(async ({ page }) => {
    await mockApiResponses(page);
    await page.goto("/map");
  });

  test("displays explicit OSM/ODbL attribution", async ({ page }) => {
    const attributionLink = page.locator(".maplibregl-ctrl-attrib-inner a", {
      hasText: "OpenStreetMap",
    });
    await expect(attributionLink).toBeVisible();
    await expect(attributionLink).toHaveAttribute(
      "href",
      "https://www.openstreetmap.org/copyright",
    );
    await expect(attributionLink).toHaveAttribute("target", "_blank");
    await expect(attributionLink).toHaveAttribute("rel", "noopener noreferrer");
  });

  test("Initial state is navigation with closed panel", async ({ page }) => {
    await page.waitForSelector(".map-marker", { timeout: 10000 });
    await expect(page.locator('[data-testid="context-panel"]')).toHaveCount(0);
  });

  test("Clicking a marker opens the context panel in fokus mode", async ({
    page,
  }) => {
    await page.waitForSelector(".map-marker", { timeout: 10000 });

    // Click a marker
    // using page.evaluate because map markers overlap with other invisible MapLibre overlay elements
    await page.evaluate(() => {
      (document.querySelector(".map-marker") as HTMLElement)?.dispatchEvent(
        new MouseEvent("click", { bubbles: true }),
      );
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

  test("Escape closes ContextPanel when in focus mode", async ({ page }) => {
    await page.waitForSelector(".map-marker", { timeout: 10000 });

    // Open panel first
    // using page.evaluate because map markers overlap with other invisible MapLibre overlay elements
    await page.evaluate(() => {
      (document.querySelector(".map-marker") as HTMLElement)?.dispatchEvent(
        new MouseEvent("click", { bubbles: true }),
      );
    });

    const panel = page.locator('[data-testid="context-panel"]');
    await expect(panel).toBeVisible();

    // Press Escape key
    await page.keyboard.press("Escape");

    // Panel should close
    await expect(panel).toBeHidden();
  });

  test("Escape closes ContextPanel when composing", async ({ page }) => {
    await page.waitForSelector(".action-bar", { timeout: 10000 });

    // Enter komposition mode via action bar
    await page.locator('button:has-text("Neuer Knoten")').click();

    const panel = page.locator('[data-testid="context-panel"]');
    await expect(panel).toBeVisible();

    // Press Escape key
    await page.keyboard.press("Escape");

    // Panel should close
    await expect(panel).toBeHidden();
  });

  test("Clicking empty map area closes the context panel", async ({ page }) => {
    await page.waitForSelector(".map-marker", { timeout: 10000 });

    // Open panel first
    // using page.evaluate because map markers overlap with other invisible MapLibre overlay elements
    await page.evaluate(() => {
      (document.querySelector(".map-marker") as HTMLElement)?.dispatchEvent(
        new MouseEvent("click", { bubbles: true }),
      );
    });
    await expect(page.locator('[data-testid="context-panel"]')).toBeVisible();

    // Click empty map area (stabile Leerklick-Zone determined at 50,50)
    // MapLibre's canvas handles clicks
    await page
      .locator("canvas.maplibregl-canvas")
      .click({ position: { x: 50, y: 50 } });

    // Panel should close
    await expect(page.locator('[data-testid="context-panel"]')).toHaveCount(0);
  });

  test("Switching between markers resets the active tab", async ({ page }) => {
    await page.waitForSelector(".map-marker", { timeout: 10000 });

    // Open panel on first marker
    // using page.evaluate because map markers overlap with other invisible MapLibre overlay elements
    await page.evaluate(() => {
      (
        document.querySelectorAll(".map-marker")[0] as HTMLElement
      )?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    const panel = page.locator('[data-testid="context-panel"]');
    await expect(panel).toBeVisible();

    // Switch to a non-default tab if possible (assuming node default is 'uebersicht', switch to 'gespraech')
    const gespraechTab = panel.locator('button:has-text("Gespräch")');
    if (await gespraechTab.isVisible()) {
      await gespraechTab.click();
      await expect(gespraechTab).toHaveClass(/active/, { timeout: 5000 });

      // Click a different marker
      // using page.evaluate because map markers overlap with other invisible MapLibre overlay elements
      await page.evaluate(() => {
        (
          document.querySelectorAll(".map-marker")[1] as HTMLElement
        )?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      });

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
    await expect(panel.locator(".state-pending")).toContainText(
      "Ort ausstehend",
    );
  });

  test("Longpress on map initializes komposition mode with coordinates", async ({
    page,
  }) => {
    await page.waitForSelector(".map-marker", { timeout: 10000 });

    // Simulate longpress by dispatching mousedown and waiting
    const mapCanvas = page.locator("canvas.maplibregl-canvas");
    // Ensure we hover and click on empty space (50, 50)
    await mapCanvas.hover({ position: { x: 50, y: 50 } });
    await page.mouse.down();
    await page.waitForTimeout(1000); // 800ms is the longpress threshold
    await page.mouse.up();

    const panel = page.locator('[data-testid="context-panel"]');
    await panel.waitFor({ state: "visible", timeout: 5000 });
    await expect(panel.locator(".state-set")).toContainText("Ort gesetzt");
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
    await page
      .locator("canvas.maplibregl-canvas")
      .click({ position: { x: 50, y: 50 } });

    // Panel should still be visible (komposition protection)
    await expect(panel).toBeVisible();
  });
});
