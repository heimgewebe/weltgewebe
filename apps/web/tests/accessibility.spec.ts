// apps/web/tests/accessibility.spec.ts
import { test, expect } from "@playwright/test";

test("main landmark is visible and left drawer toggles via keyboard", async ({
  page,
}) => {
  // Starte explizit mit geschlossenem linken Drawer
  await page.goto("/map?l=0", { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle");
  await expect(page).toHaveURL(/[?&]l=0\b/);

  await expect(page.getByRole("main")).toBeVisible();

  const leftToggle = page.getByRole("button", { name: /Webrat\/Nähstübchen/ });
  await leftToggle.focus();
  await expect(leftToggle).toBeFocused();

  // Initial geschlossen (weil ?l=0)
  await expect(leftToggle).toHaveAttribute("aria-expanded", "false");
  await expect(page.getByRole("heading", { name: "Webrat" })).toBeHidden();

  // Öffnen per Enter → l-Parameter verschwindet (Defaultzustand = offen)
  await page.keyboard.press("Enter");
  await expect(leftToggle).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByRole("heading", { name: "Webrat" })).toBeVisible();
  await expect(page).not.toHaveURL(/[?&]l=0\b/);

  // Schließen per Enter → ?l=0 sichtbar
  await page.keyboard.press("Enter");
  await expect(leftToggle).toHaveAttribute("aria-expanded", "false");
  await expect(page.getByRole("heading", { name: "Webrat" })).toBeHidden();
  await expect(page).toHaveURL(/[?&]l=0\b/);
});
