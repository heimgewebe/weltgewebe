import { expect, test } from "@playwright/test";

test.describe("smoke", () => {
  test.beforeEach(() => {
    test.setTimeout(10_000);
  });

  test("loads /map without console errors", async ({ page }) => {
    const consoleErrors: string[] = [];
    const pageErrors: string[] = [];

    page.on("console", (message) => {
      if (message.type() === "error") {
        consoleErrors.push(message.text());
      }
    });

    page.on("pageerror", (error) => {
      pageErrors.push(error.message ?? String(error));
    });

    await page.goto("/map", { waitUntil: "domcontentloaded" });
    await page.waitForLoadState("networkidle");

    const main = page.getByRole("main");
    await expect(main).toBeVisible();

    // Die Karte hängt in einem stabilen Container mit der ID #map.
    await expect(page.locator("#map")).toBeVisible();
    // Hinweis: Die /map-Route rendert bewusst keine Überschrift-Elemente.
    // Der Smoke-Test prüft nur Rendering + Fehlerfreiheit, keine Headline-Präsenz.

    expect(consoleErrors, consoleErrors.join("\n")).toHaveLength(0);
    expect(pageErrors, pageErrors.join("\n")).toHaveLength(0);
  });
});
