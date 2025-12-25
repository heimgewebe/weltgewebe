import { expect, test } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test.beforeEach(async ({ page }) => {
  await mockApiResponses(page);
  await page.goto("/map");
});

test("marker click opens showcase", async ({ page }) => {
  const marker = page.locator(".map-marker").first();
  await marker.waitFor({ state: "visible" });
  await marker.click();

  // Check if Showcase opens (it replaced SelectionCard, but uses .showcase-card class)
  const card = page.locator(".showcase-card");
  await expect(card).toBeVisible();

  // Check content from mockApi.ts demoNodes
  // "fairschenkbox" is the title in the new demoData.ts
  await expect(card).toContainText("fairschenkbox");

  // Check for new buttons instead of "Handeln"/"Details"
  await expect(card.locator('button', { hasText: 'Infos' })).toBeVisible();
  await expect(card.locator('button', { hasText: 'Besprechungen' })).toBeVisible();
  await expect(card.locator('button', { hasText: 'Verantwortungen' })).toBeVisible();
});

test("close button closes showcase", async ({ page }) => {
  const marker = page.locator(".map-marker").first();
  await marker.waitFor({ state: "visible" });
  await marker.click();

  const card = page.locator(".showcase-card");
  await expect(card).toBeVisible();

  // Click the close button
  await card.locator('button[aria-label="Close"]').click();

  // Card should disappear
  await expect(card).toBeHidden();
});
