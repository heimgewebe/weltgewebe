import { test, expect } from '@playwright/test';

test('main landmark is visible and left drawer toggles via keyboard', async ({ page }) => {
  // Starte explizit mit geschlossenem linken Drawer
  await page.goto('/map?l=0', { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle');

  await expect(page.getByRole('main')).toBeVisible();

  const leftToggle = page.getByRole('button', { name: /Webrat\/Nähstübchen/ });
  await leftToggle.focus();
  await expect(leftToggle).toBeFocused();

  // Initial geschlossen
  await expect(leftToggle).toHaveAttribute('aria-expanded', 'false');
  await expect(leftToggle).toHaveAttribute('aria-pressed', 'false');
  await expect(page.getByRole('heading', { name: 'Webrat' })).toBeHidden();

  // Öffnen per Enter
  await page.keyboard.press('Enter');
  await expect(leftToggle).toHaveAttribute('aria-expanded', 'true');
  await expect(leftToggle).toHaveAttribute('aria-pressed', 'true');
  await expect(page).toHaveURL(/[?&]l=1\b/);
  await expect(page.getByRole('heading', { name: 'Webrat' })).toBeVisible();

  // Und wieder schließen (Regression-Check)
  await page.keyboard.press('Enter');
  await expect(leftToggle).toHaveAttribute('aria-expanded', 'false');
  await expect(leftToggle).toHaveAttribute('aria-pressed', 'false');
  await expect(page).toHaveURL(/[?&]l=0\b/);
  await expect(page.getByRole('heading', { name: 'Webrat' })).toBeHidden();
});
