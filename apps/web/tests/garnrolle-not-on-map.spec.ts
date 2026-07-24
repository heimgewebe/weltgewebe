import { test, expect, type Page } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

const NOT_ON_MAP_ACCOUNT_ID = "00000000-0000-0000-0000-000000000003";
const EXACT_ACCOUNT_ID = "7d97a42e-3704-4a33-a61f-0e0a6b4d65d8";

async function gotoMapAsAccount(page: Page, accountId: string, role = "weber") {
  await mockApiResponses(page);
  await page.route("**/api/auth/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        authenticated: true,
        account_id: accountId,
        role,
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
  await page.waitForSelector('[data-testid="tool-fan"]', { timeout: 10000 });
}

async function expectDirectSettingsEntry(page: Page) {
  const link = page.getByRole("link", {
    name: "Meine Garnrolle einrichten",
  });
  await expect(link).toBeVisible();
  await expect(link).toHaveAttribute("href", "/settings#meine-garnrolle");
}

test.describe("Own Garnrolle settings entry", () => {
  test("uses the same direct settings entry when the Garnrolle is not on the map", async ({
    page,
  }) => {
    await gotoMapAsAccount(page, NOT_ON_MAP_ACCOUNT_ID);
    await expectDirectSettingsEntry(page);
  });

  test("guides a freshly authenticated guest from the map through the first Garnrolle decisions", async ({
    page,
  }) => {
    await gotoMapAsAccount(page, NOT_ON_MAP_ACCOUNT_ID, "gast");

    await page
      .getByRole("link", { name: "Meine Garnrolle einrichten" })
      .click();

    await expect(page).toHaveURL(/\/settings#meine-garnrolle$/);
    const section = page.locator('[data-testid="my-garnrolle-section"]');
    await expect(
      section.locator('[data-testid="garnrolle-first-user-guide"]'),
    ).toContainText("Du brauchst keine weitere Rolle");
    await expect(
      section.getByLabel("Privat – nicht öffentlich auf der Karte"),
    ).toBeChecked();
    await expect(
      section.locator('[data-testid="garnrolle-location-state"]'),
    ).toContainText("Noch kein Kartenanker gewählt");
    await expect(section.locator('[data-testid="save-garnrolle"]')).toHaveText(
      "Garnrolle speichern",
    );

    await section.getByLabel("Öffentlich exakt").check();
    await expect(
      section.locator('[data-testid="save-garnrolle"]'),
    ).toBeDisabled();
    await expect(
      section.getByText(
        "Für diese öffentliche Sichtbarkeit fehlt noch ein Kartenanker.",
      ),
    ).toBeVisible();
  });

  test("does not add a redundant map action when the Garnrolle has a public position", async ({
    page,
  }) => {
    await gotoMapAsAccount(page, EXACT_ACCOUNT_ID);
    await expectDirectSettingsEntry(page);
  });
});
