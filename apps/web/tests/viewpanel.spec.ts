import { expect, test } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test("ViewPanel toggles visibility", async ({ page }) => {
  await mockApiResponses(page);
  await page.goto("/map");
  const viewButton = page.getByRole("button", { name: /Ansicht/i });

  // Initially hidden
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
  await mockApiResponses(page);
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
  await mockApiResponses(page);
  await page.goto("/map");
  await page.getByRole("button", { name: /Ansicht/i }).click();

  const viewPanel = page.locator('.view-panel');
  await expect(viewPanel).toBeVisible();

  // Focus something else to ensure global handler works
  await page.locator('body').click();

  await page.keyboard.press('Escape');

  await expect(viewPanel).toBeHidden();
});

test("Toggle showNodes hides/shows markers", async ({ page }) => {
  await mockApiResponses(page);
  await page.goto("/map");

  const marker = page.locator('.map-marker').first();
  await expect(marker).toBeVisible({ timeout: 5000 });

  // Open ViewPanel
  await page.getByRole("button", { name: /Ansicht/i }).click();

  // Toggle "Knoten anzeigen" off
  // Since we changed to a switch/checkbox with separate labels structure,
  // we need to be careful with the selector.
  // The label text is "Knoten" inside .toggle-title
  // Or we can find by input type checkbox inside the ViewPanel

  // Option 1: Selector by text "Knoten" which might be part of the label
  // Option 2: Checkbox inside ViewPanel
  const toggle = page.locator('.view-panel input[type="checkbox"]').first();
  // Assuming first toggle is nodes. A bit brittle but ViewPanel order is Nodes, Edges, Gov.

  await toggle.uncheck();

  // Marker should disappear
  await expect(marker).toBeHidden();

  // Toggle back on
  await toggle.check();

  // Marker should reappear
  await expect(marker).toBeVisible();
});
