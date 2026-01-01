import { expect, test } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test.beforeEach(async ({ page }) => {
  await mockApiResponses(page);
  await page.goto("/map");
});

test("marker click opens schaufenster", async ({ page }) => {
  const marker = page.locator(".map-marker").first();
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
  const marker = page.locator(".map-marker").first();
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

test("close button closes schaufenster", async ({ page }) => {
  const marker = page.locator(".map-marker").first();
  await marker.waitFor({ state: "visible" });
  await marker.click();

  const card = page.locator(".schaufenster-card");
  await expect(card).toBeVisible();

  // Click the close button
  await card.locator('button[aria-label="Close"]').click();

  // Card should disappear
  await expect(card).toBeHidden();
});
