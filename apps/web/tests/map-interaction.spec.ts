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
    await expect(panel).toHaveCount(0);
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
    await expect(panel).toHaveCount(0);
  });

  test("Escape does NOT close ContextPanel when search is open", async ({
    page,
  }) => {
    await page.waitForSelector(".action-bar", { timeout: 10000 });

    // Enter komposition mode to open panel
    await page.locator('button:has-text("Neuer Knoten")').click();
    const panel = page.locator('[data-testid="context-panel"]');
    await expect(panel).toBeVisible();

    // Open search
    await page.locator('.action-bar button[aria-label="Suche"]').click();
    const searchOverlay = page.locator('[data-testid="search-overlay"]');
    await expect(searchOverlay).toBeVisible();

    // Press Escape key
    await page.keyboard.press("Escape");
    await expect(searchOverlay).toHaveCount(0);
    await expect(panel).toBeVisible();

    // Press Escape again
    await page.keyboard.press("Escape");
    await expect(panel).toHaveCount(0);
  });

  test("Escape does NOT close ContextPanel when filter is open", async ({
    page,
  }) => {
    await page.waitForSelector(".action-bar", { timeout: 10000 });
    await page.locator('button:has-text("Neuer Knoten")').click();
    const panel = page.locator('[data-testid="context-panel"]');
    await expect(panel).toBeVisible();
    await page.locator('.action-bar button[aria-label="Filter"]').click();
    const filterOverlay = page.locator('[data-testid="filter-overlay"]');
    await expect(filterOverlay).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(filterOverlay).toHaveCount(0);
    await expect(panel).toBeVisible();

    // Press Escape again
    await page.keyboard.press("Escape");
    await expect(panel).toHaveCount(0);
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

  test("NodePanel keyboard navigation allows arrow keys, Home, and End", async ({
    page,
  }) => {
    await page.waitForSelector(".map-marker", { timeout: 10000 });

    // Ensure we open a node. In our mock data, nodes usually have the title "Demo Node" or "Hamburg Workshop".
    // We can evaluate and click the first node marker.
    await page.evaluate(() => {
      const markers = Array.from(
        document.querySelectorAll(".map-marker"),
      ) as HTMLElement[];
      // Try to find a node by finding a marker that doesn't look like an account (just a generic marker)
      const nodeMarker =
        markers.find((m) => !m.classList.contains("garnrolle-marker")) ||
        markers[0];
      nodeMarker?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    const panel = page.locator('[data-testid="context-panel"]');
    await expect(panel).toBeVisible();

    // Ensure we are in a NodePanel by checking for the 'Übersicht' tab
    const uebersichtTab = panel.locator('button[role="tab"]', {
      hasText: "Übersicht",
    });
    await expect(uebersichtTab).toBeVisible();

    // Focus the active tab (usually Übersicht by default)
    await uebersichtTab.focus();
    await expect(uebersichtTab).toBeFocused();
    await expect(uebersichtTab).toHaveAttribute("aria-selected", "true");

    // Press ArrowRight -> Should move to "Gespräch"
    await page.keyboard.press("ArrowRight");
    const gespraechTab = panel.locator('button[role="tab"]', {
      hasText: "Gespräch",
    });
    await expect(gespraechTab).toBeFocused();
    await expect(gespraechTab).toHaveAttribute("aria-selected", "true");
    await expect(panel.locator("#panel-gespraech")).toBeVisible();

    // Press End -> Should move to "Verlauf"
    await page.keyboard.press("End");
    const verlaufTab = panel.locator('button[role="tab"]', {
      hasText: "Verlauf",
    });
    await expect(verlaufTab).toBeFocused();
    await expect(verlaufTab).toHaveAttribute("aria-selected", "true");
    await expect(panel.locator("#panel-verlauf")).toBeVisible();

    // Press Home -> Should move back to "Übersicht"
    await page.keyboard.press("Home");
    await expect(uebersichtTab).toBeFocused();
    await expect(uebersichtTab).toHaveAttribute("aria-selected", "true");

    // Press ArrowLeft -> Should wrap around to "Verlauf"
    await page.keyboard.press("ArrowLeft");
    await expect(verlaufTab).toBeFocused();
    await expect(verlaufTab).toHaveAttribute("aria-selected", "true");
  });

  test("AccountPanel keyboard navigation allows arrow keys, Home, and End", async ({
    page,
  }) => {
    await page.waitForSelector(".map-marker", { timeout: 10000 });

    // Open an account. In our mock data, accounts usually use garnrolle markers.
    await page.evaluate(() => {
      const markers = Array.from(
        document.querySelectorAll(".map-marker"),
      ) as HTMLElement[];
      const accountMarker =
        markers.find((m) => m.classList.contains("garnrolle-marker")) ||
        markers[markers.length - 1];
      accountMarker?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    const panel = page.locator('[data-testid="context-panel"]');
    await expect(panel).toBeVisible();

    // Ensure we are in an AccountPanel by checking for the 'Profil' tab
    const profilTab = panel.locator('button[role="tab"]', {
      hasText: "Profil",
    });
    await expect(profilTab).toBeVisible();

    // Focus the active tab (usually Profil by default)
    await profilTab.focus();
    await expect(profilTab).toBeFocused();
    await expect(profilTab).toHaveAttribute("aria-selected", "true");

    // Press ArrowRight -> Should move to "Aktivität"
    await page.keyboard.press("ArrowRight");
    const aktivitaetTab = panel.locator('button[role="tab"]', {
      hasText: "Aktivität",
    });
    await expect(aktivitaetTab).toBeFocused();
    await expect(aktivitaetTab).toHaveAttribute("aria-selected", "true");
    await expect(panel.locator("#panel-aktivitaet")).toBeVisible();

    // Press End -> Should move to "Knoten"
    await page.keyboard.press("End");
    const knotenTab = panel.locator('button[role="tab"]', {
      hasText: "Knoten",
    });
    await expect(knotenTab).toBeFocused();
    await expect(knotenTab).toHaveAttribute("aria-selected", "true");
    await expect(panel.locator("#panel-knoten")).toBeVisible();

    // Press Home -> Should move back to "Profil"
    await page.keyboard.press("Home");
    await expect(profilTab).toBeFocused();
    await expect(profilTab).toHaveAttribute("aria-selected", "true");

    // Press ArrowLeft -> Should wrap around to "Knoten"
    await page.keyboard.press("ArrowLeft");
    await expect(knotenTab).toBeFocused();
    await expect(knotenTab).toHaveAttribute("aria-selected", "true");
  });
});
