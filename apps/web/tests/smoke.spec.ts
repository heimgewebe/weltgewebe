import { test, expect } from '@playwright/test';

test('landing responds', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle(/Weltgewebe|Home/i);
});
