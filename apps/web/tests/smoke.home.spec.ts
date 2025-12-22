import { expect, test } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test.beforeEach(async ({ page }) => {
  await mockApiResponses(page);
  await page.goto("/map");
});

test.describe("smoke", () => {
  test("loads /map without console errors", async ({ page }) => {
    const consoleLogs: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleLogs.push(msg.text());
    });

    await expect(page.locator("#map")).toBeVisible();

    // Wait for markers to appear to ensure data is loaded
    // "fairschenkbox" is the title in the new schema-compliant demo data
    const marker = page.locator('.map-marker[aria-label="fairschenkbox"]');
    await expect(marker).toBeVisible();

    expect(consoleLogs).toEqual([]);
  });
});
