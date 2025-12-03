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

  const filterDrawer = page.locator("#filter-drawer");
  // Wait for drawer to open and content to render
  await expect(filterDrawer).toHaveAttribute("aria-hidden", "false", {
    timeout: 3000,
  });
  await expect(filterDrawer.getByText("Marktplatz Hamburg")).toBeVisible({
    timeout: 3000,
  });
  await expect(
    filterDrawer.getByText("Weitere Details folgen (Stub)"),
  ).toBeVisible({ timeout: 5000 });
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

  const filterDrawer = page.locator("#filter-drawer");
  // Wait for drawer to open
  await expect(filterDrawer).toHaveAttribute("aria-hidden", "false", {
    timeout: 3000,
  });

  await page.keyboard.press("Escape");

  // Wait for animation to complete before checking closed state
  await page.waitForTimeout(300);
  await expect(filterDrawer).toHaveAttribute("aria-hidden", "true", {
    timeout: 3000,
  });
  await expect(filterDrawer.getByText("Marktplatz Hamburg")).toHaveCount(0);
});
