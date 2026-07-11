import { test, expect, type Page } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

const NOT_ON_MAP_ACCOUNT_ID = "00000000-0000-0000-0000-000000000003";
const EXACT_ACCOUNT_ID = "7d97a42e-3704-4a33-a61f-0e0a6b4d65d8";

async function gotoMapAsAccount(page: Page, accountId: string) {
  await mockApiResponses(page);
  await page.route("**/api/auth/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        authenticated: true,
        account_id: accountId,
        role: "weber",
      }),
    }),
  );
  await page.route("https://demotiles.maplibre.org/style.json", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ version: 8, sources: {}, layers: [] }),
    });
  });
  await page.goto("/map");
  await page.waitForSelector(".action-bar", { timeout: 10000 });
}

test.describe("Own Garnrolle discoverability when not_on_map", () => {
  test("TopBar surfaces a settings link instead of a dead 'auf Karte zeigen' action", async ({
    page,
  }) => {
    await gotoMapAsAccount(page, NOT_ON_MAP_ACCOUNT_ID);

    await page.click(
      '.garnrolle-container button[aria-label="Kontoeinstellungen"]',
    );
    const menu = page.locator(".garnrolle-container .menu");
    await expect(menu).toBeVisible();

    // No dead-click "auf Karte zeigen" action when there is no public position —
    // inventing a map position is not an option, so the control simply isn't
    // offered.
    await expect(
      menu.locator('button:has-text("Meine Garnrolle auf Karte zeigen")'),
    ).toHaveCount(0);

    // The Garnrolle stays discoverable via the existing settings surface,
    // with wording that honestly reflects the not-on-map state.
    const settingsLink = menu.locator(
      'a:has-text("Meine Garnrolle (noch nicht auf der Karte)")',
    );
    await expect(settingsLink).toBeVisible();
    await expect(settingsLink).toHaveAttribute(
      "href",
      "/settings#meine-garnrolle",
    );
  });

  test("TopBar keeps the zoom action for an account with a public position", async ({
    page,
  }) => {
    await gotoMapAsAccount(page, EXACT_ACCOUNT_ID);

    await page.click(
      '.garnrolle-container button[aria-label="Kontoeinstellungen"]',
    );
    const menu = page.locator(".garnrolle-container .menu");
    await expect(menu).toBeVisible();

    await expect(
      menu.locator('button:has-text("Meine Garnrolle auf Karte zeigen")'),
    ).toBeVisible();
    await expect(menu.locator('a:has-text("Meine Garnrolle")')).toBeVisible();
  });
});
