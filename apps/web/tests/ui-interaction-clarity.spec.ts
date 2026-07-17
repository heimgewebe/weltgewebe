import { test, expect } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";
import { activateToolFanAction } from "./fixtures/toolFan";

test.describe("Interaction Clarity & State Feedback", () => {
  test.beforeEach(async ({ page }) => {
    await mockApiResponses(page, {
      auth: { authenticated: true, account_id: "e2e-weber", role: "weber" },
    });
    await page.goto("/map");
    await page.waitForSelector('[data-testid="tool-fan"]', {
      timeout: 10000,
    });
  });

  test("entering komposition closes open search overlay", async ({ page }) => {
    // Open search overlay via the tool fan
    await activateToolFanAction(page, "find");
    const searchOverlay = page.locator('[data-testid="search-overlay"]');
    await expect(searchOverlay).toBeVisible();

    // Open the fan again and trigger "Weben" while search is open
    await activateToolFanAction(page, "weave");

    // Search overlay must be closed
    await expect(searchOverlay).toHaveCount(0);

    // Context panel must be open in komposition mode
    const panel = page.locator('[data-testid="context-panel"]');
    await expect(panel).toBeVisible();
    await expect(panel.locator(".panel-header h2")).toHaveText(
      "Knoten knüpfen",
    );
  });

  test("entering komposition closes open filter overlay", async ({ page }) => {
    // Open filter overlay via the tool fan
    await activateToolFanAction(page, "content");
    const filterOverlay = page.locator('[data-testid="filter-overlay"]');
    await expect(filterOverlay).toBeVisible();

    // Open the fan again and trigger "Weben" while Karteninhalt is open
    await activateToolFanAction(page, "weave");

    // Filter overlay must be closed
    await expect(filterOverlay).toHaveCount(0);

    // Context panel must be open in komposition mode
    const panel = page.locator('[data-testid="context-panel"]');
    await expect(panel).toBeVisible();
  });

  test("'Weben' action shows active state in komposition mode", async ({
    page,
  }) => {
    await page.getByTestId("tool-fan-trigger").click();
    const weaveBtn = page.getByTestId("tool-fan-weave");

    // Initially, the action should NOT have active state
    await expect(weaveBtn).toHaveAttribute("aria-pressed", "false");

    // Enter komposition mode
    await weaveBtn.click();

    // Now the action should report active state
    await expect(weaveBtn).toHaveAttribute("aria-pressed", "true");

    // Close panel → back to navigation → active state clears
    await page.keyboard.press("Escape");
    await expect(page.locator('[data-testid="context-panel"]')).toHaveCount(0);
    await expect(weaveBtn).toHaveAttribute("aria-pressed", "false");
  });

  test("Garnrolle führt ohne Zwischenmenü direkt zu ihren Einstellungen", async ({
    page,
  }) => {
    const garnrolleLink = page.locator(
      '.garnrolle-container a[aria-label="Meine Garnrolle einstellen"]',
    );

    await expect(garnrolleLink).toBeVisible();
    await expect(garnrolleLink).toHaveAttribute(
      "href",
      "/settings#meine-garnrolle",
    );
    await expect(page.locator(".garnrolle-container .menu")).toHaveCount(0);
  });

  test("focus does not return to the tool fan trigger when entering komposition from Finden", async ({
    page,
  }) => {
    const trigger = page.getByTestId("tool-fan-trigger");

    // Open search overlay (sets restore target to the tool fan trigger)
    await trigger.click();
    await page.getByTestId("tool-fan-find").click();
    const searchOverlay = page.locator('[data-testid="search-overlay"]');
    await expect(searchOverlay).toBeVisible();

    // Trigger "Weben" — suppressNextRestore should prevent focus restore
    await trigger.click();
    await page.getByTestId("tool-fan-weave").click();
    await expect(searchOverlay).toHaveCount(0);

    // Focus must NOT be on the tool fan trigger
    await expect(trigger).not.toBeFocused();
  });

  test("focus does not return to the tool fan trigger when entering komposition from Karteninhalt", async ({
    page,
  }) => {
    const trigger = page.getByTestId("tool-fan-trigger");

    // Open filter overlay (sets restore target to the tool fan trigger)
    await trigger.click();
    await page.getByTestId("tool-fan-content").click();
    const filterOverlay = page.locator('[data-testid="filter-overlay"]');
    await expect(filterOverlay).toBeVisible();

    // Trigger "Weben" — suppressNextRestore should prevent focus restore
    await trigger.click();
    await page.getByTestId("tool-fan-weave").click();
    await expect(filterOverlay).toHaveCount(0);

    // Focus must NOT be on the tool fan trigger
    await expect(trigger).not.toBeFocused();
  });
});
