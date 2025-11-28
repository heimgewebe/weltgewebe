import { expect, test } from "@playwright/test";

test("marker click opens info panel", async ({ page }) => {
  await page.addInitScript(() => {
    (window as any).__E2E__ = true;
  });

  await page.goto("/map?l=0", { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle");
  await page.waitForFunction(() => !!document.querySelector(".map-marker"));

  const markerButton = page.getByRole("button", { name: "Werkstatt Hamm" });
  await expect(markerButton).toBeVisible({ timeout: 5000 });
  await markerButton.click();

  const filterDrawer = page.locator("#filter-drawer");
  await expect(filterDrawer).toHaveAttribute("aria-hidden", "false", {
    timeout: 2000,
  });
  await expect(filterDrawer.getByText("Werkstatt Hamm")).toBeVisible({
    timeout: 2000,
  });
  await expect(
    filterDrawer.getByText("Weitere Details folgen (Stub)"),
  ).toBeVisible({ timeout: 2000 });
});

test("escape closes info panel and clears selection", async ({ page }) => {
  await page.addInitScript(() => {
    (window as any).__E2E__ = true;
  });

  await page.goto("/map?l=0", { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle");
  await page.waitForFunction(() => !!document.querySelector(".map-marker"));

  const markerButton = page.getByRole("button", { name: "Werkstatt Hamm" });
  await expect(markerButton).toBeVisible({ timeout: 5000 });
  await markerButton.click();

  const filterDrawer = page.locator("#filter-drawer");
  await expect(filterDrawer).toHaveAttribute("aria-hidden", "false", {
    timeout: 2000,
  });

  await page.keyboard.press("Escape");

  await expect(filterDrawer).toHaveAttribute("aria-hidden", "true", {
    timeout: 2000,
  });
  await expect(filterDrawer.getByText("Werkstatt Hamm")).toHaveCount(0);
});
