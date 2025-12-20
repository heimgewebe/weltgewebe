import { expect, test } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test("ViewPanel toggles visibility", async ({ page }) => {
  await mockApiResponses(page);
  await page.goto("/map");
  const viewButton = page.getByRole("button", { name: /Ansicht öffnen/i });

  // Initially hidden
  const viewPanel = page.locator(".view-panel");
  await expect(viewPanel).toBeHidden();

  // Click to open
  await viewButton.click();
  await expect(viewPanel).toBeVisible();

  // Click again to close (now it has "Ansicht schließen" text)
  await page.getByRole("button", { name: /Ansicht schließen/i }).click();
  await expect(viewPanel).toBeHidden();
});

test("Backdrop click closes ViewPanel", async ({ page }) => {
  await mockApiResponses(page);
  await page.goto("/map");
  await page.getByRole("button", { name: /Ansicht öffnen/i }).click();

  const viewPanel = page.locator(".view-panel");
  await expect(viewPanel).toBeVisible();

  // Click backdrop
  const backdrop = page.locator(".backdrop");
  await backdrop.click({ position: { x: 10, y: 10 } });

  await expect(viewPanel).toBeHidden();
});

test("Escape key closes ViewPanel reliably", async ({ page }) => {
  await mockApiResponses(page);
  await page.goto("/map");
  await page.getByRole("button", { name: /Ansicht öffnen/i }).click();

  const viewPanel = page.locator(".view-panel");
  await expect(viewPanel).toBeVisible();

  // Focus something else to ensure global handler works
  await page.locator("body").click();

  await page.keyboard.press("Escape");

  await expect(viewPanel).toBeHidden();
});

test("Toggle showNodes hides/shows markers", async ({ page }) => {
  await mockApiResponses(page);
  await page.goto("/map");

  const marker = page.locator(".map-marker").first();
  await expect(marker).toBeVisible({ timeout: 5000 });

  // Open ViewPanel
  await page.getByRole("button", { name: /Ansicht öffnen/i }).click();

  // Use robust test-id selector and ensure it's in view
  const toggle = page.getByTestId("toggle-nodes");
  await toggle.scrollIntoViewIfNeeded();

  await toggle.uncheck({ force: true });

  // Marker should disappear
  await expect(marker).toBeHidden();

  // Toggle back on
  await toggle.check({ force: true });

  // Marker should reappear
  await expect(marker).toBeVisible();
});
