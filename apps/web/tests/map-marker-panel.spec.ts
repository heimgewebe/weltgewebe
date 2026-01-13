import { expect, test } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test.beforeEach(async ({ page }) => {
  await mockApiResponses(page);
  await page.goto("/map");
  // Robust wait for map
  await page.locator("#map").waitFor();
  // Ensure loading overlay is gone before interacting
  await expect(page.locator(".loading-overlay")).toBeHidden();
});

test("marker click opens schaufenster", async ({ page }) => {
  // Use robust prefix selector for ANY node marker
  const marker = page.locator('[data-testid^="marker-node-"]').first();
  await marker.waitFor({ state: "visible" });
  await marker.click();

  // Check if Schaufenster opens (it replaced SelectionCard, but uses .schaufenster-card class)
  const card = page.locator(".schaufenster-card");
  await expect(card).toBeVisible();

  // Check content from mockApi.ts demoNodes
  // "fairschenkbox" is the title in the new demoData.ts
  await expect(card).toContainText("fairschenkbox");

  // Check for new buttons instead of "Handeln"/"Details"
  await expect(card.locator("button", { hasText: "Info" })).toBeVisible();
  await expect(card.locator("button", { hasText: "Forum" })).toBeVisible();
  await expect(
    card.locator("button", { hasText: "Verantwortungen" }),
  ).toBeVisible();
});

test("can toggle lock state via lock button", async ({ page }) => {
  const marker = page.locator('[data-testid^="marker-node-"]').first();
  await marker.waitFor({ state: "visible" });
  await marker.click();

  const card = page.locator(".schaufenster-card");
  await expect(card).toBeVisible();

  // Find the 'profile' module card by ID
  // Use ID-based selector for functional test
  const moduleCard = card.locator('[data-module-id="profile"]');
  const lockBtn = moduleCard.locator(".lock-toggle");

  // Initially locked (default is now locked for safety)
  await expect(lockBtn).toHaveAttribute("aria-pressed", "true");
  await expect(lockBtn).toHaveText("🔒");

  // Click to UNLOCK
  // We might need to hover first if opacity is 0, but playwight click usually works or we force it
  // However, our CSS hides it (opacity: 0) unless hovered. Playwright might complain if it's not visible.
  // Let's hover the card first.
  await moduleCard.hover();
  await expect(lockBtn).toBeVisible();
  await lockBtn.click();

  // Verify unlocked state
  await expect(lockBtn).toHaveAttribute("aria-pressed", "false");
  await expect(lockBtn).toHaveText("🔓");
  await expect(moduleCard).not.toHaveClass(/locked/);

  // Click to LOCK
  await lockBtn.click();

  // Verify locked state
  await expect(lockBtn).toHaveAttribute("aria-pressed", "true");
  await expect(moduleCard).toHaveClass(/locked/);
});

test("lock state persists when re-opening schaufenster", async ({ page }) => {
  // Use specific marker to ensure we interact with the same entity
  const marker = page.locator('[data-testid^="marker-node-"]').first();
  await marker.waitFor({ state: "visible" });
  await marker.click();

  const card = page.locator(".schaufenster-card");
  await expect(card).toBeVisible();

  const moduleCard = card.locator('[data-module-id="profile"]');
  const lockBtn = moduleCard.locator(".lock-toggle");

  // Initially locked
  await expect(lockBtn).toHaveAttribute("aria-pressed", "true");

  // UNLOCK it
  await moduleCard.hover();
  await lockBtn.click();
  await expect(lockBtn).toHaveAttribute("aria-pressed", "false");

  // Close the card
  await card.locator('button[aria-label="Close"]').click();
  await expect(card).toBeHidden();

  // Re-open the same marker
  await marker.click();
  await expect(card).toBeVisible();

  // Re-query locators to ensure we are checking the new DOM elements
  const newModuleCard = card.locator('[data-module-id="profile"]');
  const newLockBtn = newModuleCard.locator(".lock-toggle");

  // It should STILL be unlocked (persistent session state)
  await expect(newLockBtn).toHaveAttribute("aria-pressed", "false");
});

test("close button closes schaufenster", async ({ page }) => {
  const marker = page.locator('[data-testid^="marker-node-"]').first();
  await marker.waitFor({ state: "visible" });
  await marker.click();

  const card = page.locator(".schaufenster-card");
  await expect(card).toBeVisible();

  // Click the close button
  await card.locator('button[aria-label="Close"]').click();

  // Card should disappear
  await expect(card).toBeHidden();
});
