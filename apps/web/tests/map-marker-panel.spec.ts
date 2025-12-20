import { expect, test } from '@playwright/test';
import { mockApiResponses } from "./fixtures/mockApi";

test.beforeEach(async ({ page }) => {
  await mockApiResponses(page);
  await page.goto('/map');
});

test('marker click opens selection card', async ({ page }) => {
  const marker = page.locator('.map-marker').first();
  await marker.waitFor({ state: 'visible' });
  await marker.click();

  // Check if SelectionCard opens (it replaced the drawer)
  // We identify it by its specific class since we didn't give it an ID
  const card = page.locator('.selection-card');
  await expect(card).toBeVisible();

  // Check content from mockApi.ts demoNodes
  await expect(card).toContainText('Marktplatz Hamburg');
});

test('close button closes selection card', async ({ page }) => {
  const marker = page.locator('.map-marker').first();
  await marker.waitFor({ state: 'visible' });
  await marker.click();

  const card = page.locator('.selection-card');
  await expect(card).toBeVisible();

  // Click the close button
  await card.locator('button[aria-label="Close"]').click();

  // Card should disappear
  await expect(card).toBeHidden();
});
