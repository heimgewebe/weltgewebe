import { test, expect } from '@playwright/test';

test('main landmark is visible and left drawer toggles via keyboard', async ({ page }) => {
  await page.goto('/map', { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle');

  await expect(page.getByRole('main')).toBeVisible();

  const leftToggle = page.getByRole('button', { name: /Webrat\/Nähstübchen/ });
  await leftToggle.focus();
  await expect(leftToggle).toBeFocused();
  await expect(leftToggle).toHaveAttribute('aria-expanded', /false|undefined/i);

  await page.keyboard.press('Enter');
  // Nach dem Öffnen: Drawer-Inhalt sichtbar & ARIA-Expanded aktualisiert
  await expect(page.getByRole('heading', { name: 'Webrat' })).toBeVisible();
  await expect(leftToggle).toHaveAttribute('aria-expanded', 'true');

  // Optional: Container-Attribut prüfen (robust gegen Render-Timing)
  const leftStack = page.locator('#left-stack');
  await expect(leftStack).toHaveClass(/open/);
});
