import { test, expect } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test.describe("ActionBar Layout", () => {
  test.beforeEach(async ({ page }) => {
    await mockApiResponses(page);
    await page.goto("/map");
    await page.waitForSelector(".action-bar", { timeout: 10000 });
  });

  test("buttons are ordered: Neuer Knoten, Suche, Filter", async ({
    page,
  }) => {
    const buttons = page.locator(".action-bar .action-btn");
    await expect(buttons).toHaveCount(3);
    await expect(buttons.nth(0)).toHaveAttribute("aria-label", "Neuer Knoten");
    await expect(buttons.nth(1)).toHaveAttribute("aria-label", "Suche");
    await expect(buttons.nth(2)).toHaveAttribute("aria-label", "Filter");
  });
});
