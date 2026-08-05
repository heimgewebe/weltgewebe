import { expect, test } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test.beforeEach(async ({ page }) => {
  await mockApiResponses(page);
  await page.goto("/map");
});

test.describe("smoke", () => {
  test("loads /map without console errors", async ({ page }) => {
    const consoleLogs: string[] = [];
    const pageErrors: string[] = [];

    page.on("console", (msg) => {
      if (msg.type() === "error") consoleLogs.push(msg.text());
    });

    page.on("pageerror", (err) => {
      pageErrors.push(err.toString());
    });

    await expect(page.locator("#map")).toBeVisible();

    // Wait for a semantic node marker. Its accessible name intentionally
    // includes the active woven participation counts after the title.
    const marker = page.locator('.map-marker[aria-label^="fairschenkbox."]');
    await expect(marker).toBeVisible();

    expect(consoleLogs).toEqual([]);
    expect(pageErrors).toEqual([]);
  });
});
