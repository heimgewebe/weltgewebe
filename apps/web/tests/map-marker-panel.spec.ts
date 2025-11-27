import { expect, test } from "@playwright/test";

test("marker click opens info panel", async ({ page }) => {
  await page.addInitScript(() => {
    (window as any).__E2E__ = true;
  });

  await page.goto("/map", { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle");
  await page.waitForFunction(() => !!document.querySelector(".map-marker"));

  const markerButton = page.getByRole("button", { name: "Werkstatt Hamm" });
  await expect(markerButton).toBeVisible({ timeout: 10000 });
  await markerButton.click();

  const infoDrawer = page.getByRole("complementary", {
    name: "Suche & Filter",
  });
  await expect(infoDrawer).toBeVisible({ timeout: 5000 });
  await expect(infoDrawer.getByText("Werkstatt Hamm")).toBeVisible();
  await expect(
    infoDrawer.getByText("Weitere Details folgen (Stub)"),
  ).toBeVisible();
});

test("escape closes info panel and clears selection", async ({ page }) => {
  await page.addInitScript(() => {
    (window as any).__E2E__ = true;
  });

  await page.goto("/map", { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle");
  await page.waitForFunction(() => !!document.querySelector(".map-marker"));

  const markerButton = page.getByRole("button", { name: "Werkstatt Hamm" });
  await expect(markerButton).toBeVisible({ timeout: 10000 });
  await markerButton.click();

  const infoDrawer = page.getByRole("complementary", {
    name: "Suche & Filter",
  });
  await expect(infoDrawer).toBeVisible({ timeout: 5000 });

  await page.keyboard.press("Escape");

  await expect(infoDrawer).toHaveAttribute("aria-hidden", "true");
  await expect(infoDrawer.getByText("Werkstatt Hamm")).toHaveCount(0);
});
