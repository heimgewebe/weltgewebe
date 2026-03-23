import { test, expect } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test.describe("Interaction Clarity & State Feedback", () => {
  test.beforeEach(async ({ page }) => {
    await mockApiResponses(page);
    await page.goto("/map");
    await page.waitForSelector(".action-bar", { timeout: 10000 });
  });

  test("entering komposition closes open search overlay", async ({ page }) => {
    // Open search overlay
    await page.locator('.action-bar button[aria-label="Suche"]').click();
    const searchOverlay = page.locator('[data-testid="search-overlay"]');
    await expect(searchOverlay).toBeVisible();

    // Click "Neuer Knoten" while search is open
    await page.locator('button:has-text("Neuer Knoten")').click();

    // Search overlay must be closed
    await expect(searchOverlay).toHaveCount(0);

    // Context panel must be open in komposition mode
    const panel = page.locator('[data-testid="context-panel"]');
    await expect(panel).toBeVisible();
    await expect(panel.locator(".panel-header h2")).toHaveText("Neuer Knoten");
  });

  test("entering komposition closes open filter overlay", async ({ page }) => {
    // Open filter overlay
    await page.locator('.action-bar button[aria-label="Filter"]').click();
    const filterOverlay = page.locator('[data-testid="filter-overlay"]');
    await expect(filterOverlay).toBeVisible();

    // Click "Neuer Knoten" while filter is open
    await page.locator('button:has-text("Neuer Knoten")').click();

    // Filter overlay must be closed
    await expect(filterOverlay).toHaveCount(0);

    // Context panel must be open in komposition mode
    const panel = page.locator('[data-testid="context-panel"]');
    await expect(panel).toBeVisible();
  });

  test("'Neuer Knoten' button shows active state in komposition mode", async ({
    page,
  }) => {
    const newNodeBtn = page.locator('button:has-text("Neuer Knoten")');

    // Initially, button should NOT have active class
    await expect(newNodeBtn).not.toHaveClass(/active/);

    // Enter komposition mode
    await newNodeBtn.click();

    // Now button should have active class
    await expect(newNodeBtn).toHaveClass(/active/);

    // Close panel → back to navigation → button should lose active
    await page.keyboard.press("Escape");
    await expect(
      page.locator('[data-testid="context-panel"]'),
    ).toHaveCount(0);
    await expect(newNodeBtn).not.toHaveClass(/active/);
  });

  test("Garnrolle menu closes on Escape", async ({ page }) => {
    // The Garnrolle button is in the TopBar
    const garnrolleBtn = page.locator(
      '.garnrolle-container button[aria-label="Kontoeinstellungen"]',
    );
    await expect(garnrolleBtn).toBeVisible();

    // Open menu
    await garnrolleBtn.click();
    await expect(garnrolleBtn).toHaveAttribute("aria-expanded", "true");

    // Verify menu is visible
    const menu = page.locator(".garnrolle-container .menu");
    await expect(menu).toBeVisible();

    // Press Escape
    await page.keyboard.press("Escape");

    // Menu must be closed
    await expect(menu).toHaveCount(0);
    await expect(garnrolleBtn).toHaveAttribute("aria-expanded", "false");
  });

  test("Escape on Garnrolle menu does NOT close ContextPanel", async ({
    page,
  }) => {
    // Open context panel first (komposition mode)
    await page.locator('button:has-text("Neuer Knoten")').click();
    const panel = page.locator('[data-testid="context-panel"]');
    await expect(panel).toBeVisible();

    // Open Garnrolle menu
    const garnrolleBtn = page.locator(
      '.garnrolle-container button[aria-label="Kontoeinstellungen"]',
    );
    await garnrolleBtn.click();
    const menu = page.locator(".garnrolle-container .menu");
    await expect(menu).toBeVisible();

    // Press Escape should close menu only, not the panel
    await page.keyboard.press("Escape");
    await expect(menu).toHaveCount(0);
    await expect(panel).toBeVisible(); // panel must remain open
  });

  test("Escape on Garnrolle menu does NOT close SearchOverlay", async ({
    page,
  }) => {
    // Open search overlay
    await page.locator('.action-bar button[aria-label="Suche"]').click();
    const searchOverlay = page.locator('[data-testid="search-overlay"]');
    await expect(searchOverlay).toBeVisible();

    // Open Garnrolle menu while search is open
    const garnrolleBtn = page.locator(
      '.garnrolle-container button[aria-label="Kontoeinstellungen"]',
    );
    await garnrolleBtn.click();
    const menu = page.locator(".garnrolle-container .menu");
    await expect(menu).toBeVisible();

    // Press Escape: Garnrolle menu closes, search stays open
    await page.keyboard.press("Escape");
    await expect(menu).toHaveCount(0);
    await expect(searchOverlay).toBeVisible();
  });
});
