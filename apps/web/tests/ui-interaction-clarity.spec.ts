import { test, expect } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test.describe("Interaction Clarity & State Feedback", () => {
  test.beforeEach(async ({ page }) => {
    await mockApiResponses(page, {
      auth: { authenticated: true, account_id: "e2e-weber", role: "weber" },
    });
    await page.goto("/map");
    await page.waitForSelector(".action-bar", { timeout: 10000 });
  });

  test("entering komposition closes open search overlay", async ({ page }) => {
    // Open search overlay
    await page.locator('.action-bar button[aria-label="Suche"]').click();
    const searchOverlay = page.locator('[data-testid="search-overlay"]');
    await expect(searchOverlay).toBeVisible();

    // Click "Knoten knüpfen" while search is open
    await page
      .locator('.action-bar button[aria-label="Knoten knüpfen"]')
      .click();

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
    // Open filter overlay
    await page.locator('.action-bar button[aria-label="Filter"]').click();
    const filterOverlay = page.locator('[data-testid="filter-overlay"]');
    await expect(filterOverlay).toBeVisible();

    // Click "Knoten knüpfen" while filter is open
    await page
      .locator('.action-bar button[aria-label="Knoten knüpfen"]')
      .click();

    // Filter overlay must be closed
    await expect(filterOverlay).toHaveCount(0);

    // Context panel must be open in komposition mode
    const panel = page.locator('[data-testid="context-panel"]');
    await expect(panel).toBeVisible();
  });

  test("'Knoten knüpfen' button shows active state in komposition mode", async ({
    page,
  }) => {
    const newNodeBtn = page.locator(
      '.action-bar button[aria-label="Knoten knüpfen"]',
    );

    // Initially, button should NOT have active class
    await expect(newNodeBtn).not.toHaveClass(/active/);

    // Enter komposition mode
    await newNodeBtn.click();

    // Now button should have active class
    await expect(newNodeBtn).toHaveClass(/active/);

    // Close panel → back to navigation → button should lose active
    await page.keyboard.press("Escape");
    await expect(page.locator('[data-testid="context-panel"]')).toHaveCount(0);
    await expect(newNodeBtn).not.toHaveClass(/active/);
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

  test("focus does not return to Search button when entering komposition", async ({
    page,
  }) => {
    const searchBtn = page.locator('.action-bar button[aria-label="Suche"]');

    // Open search overlay (sets restore target to searchBtn)
    await searchBtn.click();
    const searchOverlay = page.locator('[data-testid="search-overlay"]');
    await expect(searchOverlay).toBeVisible();

    // Click "Knoten knüpfen" — suppressNextRestore should prevent focus restore
    await page
      .locator('.action-bar button[aria-label="Knoten knüpfen"]')
      .click();
    await expect(searchOverlay).toHaveCount(0);

    // Focus must NOT be on the Search button
    await expect(searchBtn).not.toBeFocused();
  });

  test("focus does not return to Filter button when entering komposition", async ({
    page,
  }) => {
    const filterBtn = page.locator('.action-bar button[aria-label="Filter"]');

    // Open filter overlay (sets restore target to filterBtn)
    await filterBtn.click();
    const filterOverlay = page.locator('[data-testid="filter-overlay"]');
    await expect(filterOverlay).toBeVisible();

    // Click "Knoten knüpfen" — suppressNextRestore should prevent focus restore
    await page
      .locator('.action-bar button[aria-label="Knoten knüpfen"]')
      .click();
    await expect(filterOverlay).toHaveCount(0);

    // Focus must NOT be on the Filter button
    await expect(filterBtn).not.toBeFocused();
  });
});
