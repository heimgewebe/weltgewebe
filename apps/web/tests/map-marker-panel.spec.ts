import { expect, test } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test.beforeEach(async ({ page }) => {
  // Mock API responses to avoid needing a running backend
  await mockApiResponses(page);
});

test("marker click opens info panel", async ({ page }) => {
  await page.addInitScript(() => {
    (window as any).__E2E__ = true;
  });

  await page.goto("/map?l=0", { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle");
  // Wait explicitly for markers to be rendered
  await page.waitForSelector(".map-marker", { timeout: 10000 });

  const markerButton = page.getByRole("button", { name: "Marktplatz Hamburg" });
  await expect(markerButton).toBeVisible({ timeout: 10000 });
  await markerButton.click();

  // SelectionCard replaces the old filter-drawer
  const selectionCard = page.locator(".selection-card");
  await expect(selectionCard).toBeVisible({ timeout: 3000 });
  await expect(selectionCard.getByText("Marktplatz Hamburg")).toBeVisible({
    timeout: 3000,
  });
  // The new UI doesn't have "Weitere Details folgen" stub text
  // Instead it shows "Keine Beschreibung verfügbar." when no description exists
});

test("escape closes info panel and clears selection", async ({ page }) => {
  await page.addInitScript(() => {
    (window as any).__E2E__ = true;
  });

  await page.goto("/map?l=0", { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle");
  await page.waitForSelector(".map-marker", { timeout: 10000 });

  const markerButton = page.getByRole("button", { name: "Marktplatz Hamburg" });
  await expect(markerButton).toBeVisible({ timeout: 10000 });
  await markerButton.click();

  const selectionCard = page.locator(".selection-card");
  // Wait for card to appear
  await expect(selectionCard).toBeVisible({ timeout: 3000 });

  await page.keyboard.press("Escape");

  // Wait for animation to complete before checking closed state
  await page.waitForTimeout(300);
  await expect(selectionCard).toBeHidden({ timeout: 3000 });
});
