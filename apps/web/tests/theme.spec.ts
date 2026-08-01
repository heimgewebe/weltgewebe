import { expect, test, type Locator, type Page } from "@playwright/test";

const themeRoot = (page: Page) => page.locator("html");

type Rgba = [number, number, number, number];

function parseColor(value: string): Rgba {
  const hex = value.match(/^#([0-9a-f]{6})$/i)?.[1];
  if (hex) {
    return [
      Number.parseInt(hex.slice(0, 2), 16),
      Number.parseInt(hex.slice(2, 4), 16),
      Number.parseInt(hex.slice(4, 6), 16),
      1,
    ];
  }

  const components = value.match(/[\d.]+/g)?.map(Number);
  if (!components || components.length < 3) {
    throw new Error(`Nicht unterstützte CSS-Farbe: ${value}`);
  }
  return [components[0], components[1], components[2], components[3] ?? 1];
}

function composite([red, green, blue, alpha]: Rgba, underlay: Rgba): Rgba {
  return [
    red * alpha + underlay[0] * (1 - alpha),
    green * alpha + underlay[1] * (1 - alpha),
    blue * alpha + underlay[2] * (1 - alpha),
    1,
  ];
}

function relativeLuminance([red, green, blue]: Rgba): number {
  const linear = [red, green, blue].map((value) => {
    const channel = value / 255;
    return channel <= 0.04045
      ? channel / 12.92
      : ((channel + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
}

function contrastRatio(first: Rgba, second: Rgba): number {
  const lighter = Math.max(relativeLuminance(first), relativeLuminance(second));
  const darker = Math.min(relativeLuminance(first), relativeLuminance(second));
  return (lighter + 0.05) / (darker + 0.05);
}

async function expectReadableSurface(locator: Locator, label: string) {
  const colors = await locator.evaluate((element) => {
    const style = getComputedStyle(element);
    const rootStyle = getComputedStyle(document.documentElement);
    return {
      foreground: style.color,
      background: style.backgroundColor,
      underlay: rootStyle.getPropertyValue("--bg").trim(),
    };
  });
  const underlay = parseColor(colors.underlay);
  const background = composite(parseColor(colors.background), underlay);
  expect(
    contrastRatio(parseColor(colors.foreground), background),
    `${label} muss im hellen Farbschema lesbar bleiben`,
  ).toBeGreaterThanOrEqual(4.5);
}

test.describe("Farbschema", () => {
  test("wechselt das Farbschema und teilt die Auswahl zwischen Karte und Einstellungen", async ({
    page,
  }) => {
    await page.goto("/map");

    const mapButton = page.getByTestId("theme-compact-button");
    await expect(mapButton).toBeVisible();
    await expect(mapButton).toHaveAttribute("data-theme", "system");
    await expect(page.getByRole("option")).toHaveCount(0);

    await mapButton.click();
    await expect(themeRoot(page)).toHaveAttribute("data-theme", "light");
    await expect(themeRoot(page)).toHaveAttribute("data-color-scheme", "light");

    await mapButton.click();
    await expect(themeRoot(page)).toHaveAttribute("data-theme", "dark");
    await expect(themeRoot(page)).toHaveAttribute("data-color-scheme", "dark");
    await expect
      .poll(() =>
        page.evaluate(() => window.localStorage.getItem("weltgewebe.theme")),
      )
      .toBe("dark");

    await page.reload();
    await expect(themeRoot(page)).toHaveAttribute("data-theme", "dark");
    await expect(page.getByTestId("theme-compact-button")).toHaveAttribute(
      "data-theme",
      "dark",
    );

    await page.goto("/settings");
    const settingsSelect = page.getByTestId("theme-select");
    await expect(settingsSelect).toHaveValue("dark");
    await settingsSelect.selectOption("light");
    await expect(themeRoot(page)).toHaveAttribute("data-theme", "light");

    await page.goto("/map");
    await expect(page.getByTestId("theme-compact-button")).toHaveAttribute(
      "data-theme",
      "light",
    );
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

  test("hält die zentralen Kartenflächen im hellen Farbschema lesbar", async ({
    page,
  }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("weltgewebe.theme", "light");
    });
    await page.goto("/map");

    await expectReadableSurface(
      page.getByTestId("tool-fan-trigger"),
      "Werkzeugauslöser",
    );
    await expectReadableSurface(
      page.getByTestId("governance-fan-trigger"),
      "Governance-Auslöser",
    );

    await page.getByTestId("tool-fan-trigger").click();
    await expectReadableSurface(
      page.getByTestId("tool-fan-find"),
      "Werkzeugaktion",
    );

    await page.getByTestId("tool-fan-find").click();
    await expectReadableSurface(
      page.getByTestId("search-overlay"),
      "Suchfläche",
    );
    await page.getByRole("button", { name: "Finden schließen" }).click();

    await page.getByTestId("tool-fan-trigger").click();
    await page.getByTestId("tool-fan-map-content").click();
    await expectReadableSurface(
      page.getByTestId("filter-overlay"),
      "Filterfläche",
    );
  });
});
