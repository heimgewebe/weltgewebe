import { expect, test } from "@playwright/test";

test("ViewPanel toggles visibility", async ({ page }) => {
  await page.goto("/map");
  const viewButton = page.getByRole("button", { name: /Ansicht/i });

  // Initially hidden (assuming default state is closed, although uiView.ts has viewPanelOpen false)
  const viewPanel = page.locator('.view-panel');
  await expect(viewPanel).toBeHidden();

  // Click to open
  await viewButton.click();
  await expect(viewPanel).toBeVisible();

  // Click again to close
  await viewButton.click();
  await expect(viewPanel).toBeHidden();
});

test("Backdrop click closes ViewPanel", async ({ page }) => {
  await page.goto("/map");
  await page.getByRole("button", { name: /Ansicht/i }).click();

  const viewPanel = page.locator('.view-panel');
  await expect(viewPanel).toBeVisible();

  // Click backdrop
  const backdrop = page.locator('.backdrop');
  await backdrop.click({ position: { x: 10, y: 10 } });

  await expect(viewPanel).toBeHidden();
});

test("Escape key closes ViewPanel reliably", async ({ page }) => {
  await page.goto("/map");
  await page.getByRole("button", { name: /Ansicht/i }).click();

  const viewPanel = page.locator('.view-panel');
  await expect(viewPanel).toBeVisible();

  // Focus something else to ensure global handler works
  // Just clicking the map or body might change focus context
  await page.locator('body').click();

  await page.keyboard.press('Escape');

  await expect(viewPanel).toBeHidden();
});

test("Toggle showNodes hides/shows markers", async ({ page }) => {
  // Mock data to ensure we have markers
  await page.route("**/api/nodes", async (route) => {
      await route.fulfill({
        json: [{ id: "n1", title: "N1", location: { lat: 53.55, lon: 10.0 } }]
      });
  });

  await page.goto("/map");

  const marker = page.locator('.map-marker').first();
  await expect(marker).toBeVisible({ timeout: 5000 });

  // Open ViewPanel
  await page.getByRole("button", { name: /Ansicht/i }).click();

  // Toggle "Knoten anzeigen" off
  const toggle = page.getByLabel("Knoten anzeigen");
  await toggle.uncheck();

  // Marker should disappear
  await expect(marker).toBeHidden();

  // Toggle back on
  await toggle.check();

  // Marker should reappear
  await expect(marker).toBeVisible();
});
