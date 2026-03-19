import { test, expect } from "@playwright/test";

test.describe("Update Banner (Kontrollierte Selbstaktualisierung)", () => {
  test("shows update banner when version changes between checks", async ({
    page,
  }) => {
    let checkCount = 0;

    // Intercept version.json and mock a change on the second request
    await page.route("**/_app/version.json", async (route) => {
      checkCount++;
      if (checkCount === 1) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ version: "old-version" }),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ version: "new-version" }),
        });
      }
    });

    // Initial page load checks for the first time
    await page.goto("/map");

    // Banner should not be visible initially
    await expect(
      page.locator("text=Eine neue Version ist verfügbar."),
    ).toHaveCount(0);

    // Wait slightly just to make sure the first check completed
    await page.waitForTimeout(500);

    // Trigger visibilitychange to force the second check
    await page.evaluate(() => {
      Object.defineProperty(document, "visibilityState", {
        get: () => "visible",
        configurable: true,
      });
      document.dispatchEvent(new Event("visibilitychange"));
    });

    // Banner should appear
    await expect(
      page.locator("text=Eine neue Version ist verfügbar."),
    ).toBeVisible({ timeout: 10000 });
    await expect(page.locator("button:has-text('Neu laden')")).toBeVisible();
  });

  test("does not show update banner when version is the same", async ({
    page,
  }) => {
    await page.route("**/_app/version.json", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ version: "same-version" }),
      });
    });

    await page.goto("/map");

    // Banner should not be visible initially
    await expect(
      page.locator("text=Eine neue Version ist verfügbar."),
    ).toHaveCount(0);

    // Wait slightly
    await page.waitForTimeout(500);

    // Trigger visibilitychange
    await page.evaluate(() => {
      Object.defineProperty(document, "visibilityState", {
        get: () => "visible",
        configurable: true,
      });
      document.dispatchEvent(new Event("visibilitychange"));
    });

    // Banner should still not be visible
    await expect(
      page.locator("text=Eine neue Version ist verfügbar."),
    ).toHaveCount(0);
  });

  test("does not show update banner when fetch fails", async ({ page }) => {
    let checkCount = 0;

    await page.route("**/_app/version.json", async (route) => {
      checkCount++;
      if (checkCount === 1) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ version: "old-version" }),
        });
      } else {
        await route.fulfill({
          status: 500,
          body: "Internal Server Error",
        });
      }
    });

    await page.goto("/map");
    await expect(
      page.locator("text=Eine neue Version ist verfügbar."),
    ).toHaveCount(0);

    // Wait slightly
    await page.waitForTimeout(500);

    // Trigger visibilitychange to force the second check (which fails)
    await page.evaluate(() => {
      Object.defineProperty(document, "visibilityState", {
        get: () => "visible",
        configurable: true,
      });
      document.dispatchEvent(new Event("visibilitychange"));
    });

    // Banner should not appear
    await expect(
      page.locator("text=Eine neue Version ist verfügbar."),
    ).toHaveCount(0);
  });
});
