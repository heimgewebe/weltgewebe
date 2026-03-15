import { test, expect } from '@playwright/test';

test.describe('Version Diagnostics', () => {
  test('displays build ID when version.json is successfully fetched', async ({ page }) => {
    await page.route('**/_app/version.json', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          version: 'test-build-12345',
          release: '1.2.0',
          built_at: '2026-03-15T12:00:00Z'
        })
      });
    });

    await page.goto('/settings');
    await expect(page.locator('[data-testid="version-text"]')).toHaveText('Release 1.2.0 · Build test-build-12345');
    await expect(page.locator('[data-testid="version-date"]')).toContainText('15.03.2026');
  });

  test('displays fallback when version.json fetch fails', async ({ page }) => {
    await page.route('**/_app/version.json', async (route) => {
      await route.fulfill({
        status: 500,
        body: 'Internal Server Error'
      });
    });

    await page.goto('/settings');
    await expect(page.locator('[data-testid="version-text"]')).toHaveText('Version unbekannt');
  });

  test('displays only build ID when release is missing', async ({ page }) => {
    await page.route('**/_app/version.json', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          version: 'test-build-67890'
        })
      });
    });

    await page.goto('/settings');
    await expect(page.locator('[data-testid="version-text"]')).toHaveText('Build test-build-67890');
    // The timestamp element should not be rendered if built_at is missing
    await expect(page.locator('[data-testid="version-date"]')).toHaveCount(0);
  });
});
