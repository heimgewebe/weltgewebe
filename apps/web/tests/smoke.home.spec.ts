import { expect, test } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test.beforeEach(async ({ page }) => {
  await mockApiResponses(page);
  await page.goto("/map");
});

test.describe("smoke", () => {
  test("displays explicit OSM/ODbL attribution", async ({ page }) => {
    const attributionLink = page.locator(".maplibregl-ctrl-attrib-inner a", {
      hasText: "OpenStreetMap",
    });
    await expect(attributionLink).toBeVisible();
    await expect(attributionLink).toHaveAttribute(
      "href",
      "https://www.openstreetmap.org/copyright",
    );
    await expect(attributionLink).toHaveAttribute("target", "_blank");
    await expect(attributionLink).toHaveAttribute("rel", "noopener noreferrer");
  });

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

    // Wait for markers to appear to ensure data is loaded
    // "fairschenkbox" is the title in the new schema-compliant demo data
    const marker = page.locator('.map-marker[aria-label="fairschenkbox"]');
    await expect(marker).toBeVisible();

    expect(consoleLogs).toEqual([]);
    expect(pageErrors).toEqual([]);
  });
});
