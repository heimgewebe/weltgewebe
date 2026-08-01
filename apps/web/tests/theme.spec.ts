import { expect, test, type Page } from "@playwright/test";

const themeRoot = (page: Page) => page.locator("html");

test.describe("Farbschema", () => {
  test("wechselt das Farbschema und teilt die Auswahl zwischen Karte und Einstellungen", async ({
    page,
  }) => {
    await page.goto("/map");

    const mapSelect = page.getByTestId("theme-compact-select");
    await expect(mapSelect).toBeVisible();

    await mapSelect.selectOption("dark");
    await expect(themeRoot(page)).toHaveAttribute("data-theme", "dark");
    await expect(themeRoot(page)).toHaveAttribute("data-color-scheme", "dark");
    await expect
      .poll(() =>
        page.evaluate(() => window.localStorage.getItem("weltgewebe.theme")),
      )
      .toBe("dark");

    await page.reload();
    await expect(themeRoot(page)).toHaveAttribute("data-theme", "dark");
    await expect(themeRoot(page)).toHaveAttribute("data-color-scheme", "dark");

    await page.getByTestId("theme-compact-select").selectOption("light");
    await expect(themeRoot(page)).toHaveAttribute("data-theme", "light");
    await expect(themeRoot(page)).toHaveAttribute("data-color-scheme", "light");

    await page.goto("/settings");
    const settingsSelect = page.getByTestId("theme-select");
    await expect(settingsSelect).toHaveValue("light");
    await settingsSelect.selectOption("system");
    await expect(themeRoot(page)).toHaveAttribute("data-theme", "system");
  });

  test("folgt im Systemmodus einer geänderten Gerätepräferenz", async ({
    page,
  }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await page.addInitScript(() => {
      window.localStorage.setItem("weltgewebe.theme", "system");
    });
    await page.goto("/map");

    await expect(themeRoot(page)).toHaveAttribute("data-theme", "system");
    await expect(themeRoot(page)).toHaveAttribute("data-color-scheme", "dark");

    await page.emulateMedia({ colorScheme: "light" });
    await expect(themeRoot(page)).toHaveAttribute("data-color-scheme", "light");
  });
});
