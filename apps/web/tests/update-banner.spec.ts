import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

test.describe("Update Banner (Kontrollierte Selbstaktualisierung)", () => {
  let localVersionData: any;

  test.beforeAll(() => {
    // Read the true buildVersion that was bundled into the client app
    const versionFilePath = path.resolve(
      process.cwd(),
      "src/lib/generated/buildVersion.json",
    );
    if (fs.existsSync(versionFilePath)) {
      localVersionData = JSON.parse(fs.readFileSync(versionFilePath, "utf8"));
    } else {
      localVersionData = { version: "unknown" };
    }
  });

  test("shows update banner when server version differs from local bundle version", async ({
    page,
  }) => {
    // Intercept version.json and mock a new server version
    await page.route("**/_app/version.json", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ version: "a-completely-new-version" }),
      });
    });

    // On initial page load, the app fetches the server version and compares it
    // against its bundled localVersion. Since it's different, the banner should appear.
    await page.goto("/map");

    // Banner should appear immediately without needing a second check
    await expect(
      page.locator("text=Eine neue Version ist verfügbar."),
    ).toBeVisible();
    await expect(page.locator("button:has-text('Neu laden')")).toBeVisible();
  });

  test("does not show update banner when server version is identical to local bundle version", async ({
    page,
  }) => {
    // Intercept version.json and return the EXACT same version as the bundle
    await page.route("**/_app/version.json", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ version: localVersionData.version }),
      });
    });

    await page.goto("/map");

    // Banner should not be visible initially
    await expect(
      page.locator("text=Eine neue Version ist verfügbar."),
    ).toHaveCount(0);

    // Wait slightly just to ensure async checks completed
    await page.waitForTimeout(500);

    // Trigger visibilitychange to simulate the user returning to the tab
    await page.evaluate(() => {
      Object.defineProperty(document, "visibilityState", {
        get: () => "visible",
        configurable: true,
      });
      document.dispatchEvent(new Event("visibilitychange"));
    });

    // Banner should STILL not be visible
    await expect(
      page.locator("text=Eine neue Version ist verfügbar."),
    ).toHaveCount(0);
  });

  test("shows update banner when bfcache is restored (pageshow with persisted)", async ({
    page,
  }) => {
    let checkCount = 0;

    // Intercept version.json and mock a new server version ONLY on the second check (pageshow)
    await page.route("**/_app/version.json", async (route) => {
      checkCount++;
      if (checkCount === 1) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ version: localVersionData.version }),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            version: "a-completely-new-version-from-bfcache",
          }),
        });
      }
    });

    await page.goto("/map");

    // Banner should not be visible initially
    await expect(
      page.locator("text=Eine neue Version ist verfügbar."),
    ).toHaveCount(0);

    // Wait slightly
    await page.waitForTimeout(500);

    // We manually simulate a pageshow event with `persisted: true` to mimic a back-forward cache return
    await page.evaluate(() => {
      const event = new PageTransitionEvent("pageshow", { persisted: true });
      window.dispatchEvent(event);
    });

    // Banner should appear
    await expect(
      page.locator("text=Eine neue Version ist verfügbar."),
    ).toBeVisible();
  });

  test("does not show update banner when fetch fails", async ({ page }) => {
    await page.route("**/_app/version.json", async (route) => {
      await route.fulfill({
        status: 500,
        body: "Internal Server Error",
      });
    });

    await page.goto("/map");

    // Banner should not be visible initially
    await expect(
      page.locator("text=Eine neue Version ist verfügbar."),
    ).toHaveCount(0);

    // Wait slightly
    await page.waitForTimeout(500);

    // Trigger visibilitychange to force another check (which fails)
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
