import { expect, test, type Locator, type Page } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

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

async function expectNoStripePattern(locator: Locator, label: string) {
  const backgroundImage = await locator.evaluate(
    (element) => getComputedStyle(element).backgroundImage,
  );
  expect(
    backgroundImage,
    `${label} darf kein wiederholtes Streifenmuster verwenden`,
  ).not.toContain("repeating-linear-gradient");
}

test.describe("Farbschema", () => {
  test("steuert das Farbschema im Einstellungsmenü und behält es auf der Karte", async ({
    page,
  }) => {
    await page.goto("/settings");

    const menu = page.getByTestId("settings-menu");
    const settingsSelect = page.getByTestId("theme-select");
    await expect(menu).toBeVisible();
    await expect(
      menu.getByRole("link", { name: /Meine Garnrolle/ }),
    ).toBeVisible();
    await expect(
      menu.getByRole("link", { name: /Konto & Sicherheit/ }),
    ).toBeVisible();
    await expect(
      menu.getByRole("link", { name: /Private Nachrichten/ }),
    ).toHaveCount(0);
    await expect(settingsSelect).toHaveValue("system");

    await settingsSelect.selectOption("dark");
    await expect(themeRoot(page)).toHaveAttribute("data-theme", "dark");
    await expect(themeRoot(page)).toHaveAttribute("data-color-scheme", "dark");
    await expect
      .poll(() =>
        page.evaluate(() => window.localStorage.getItem("weltgewebe.theme")),
      )
      .toBe("dark");

    await page.reload();
    await expect(themeRoot(page)).toHaveAttribute("data-theme", "dark");
    await expect(page.getByTestId("theme-select")).toHaveValue("dark");

    const basemapStyleUrls: string[] = [];
    page.on("request", (request) => {
      const url = request.url();
      if (url.includes("/local-basemap/style")) {
        basemapStyleUrls.push(url);
      }
    });

    await page.goto("/map");
    await expect(themeRoot(page)).toHaveAttribute("data-theme", "dark");
    await expect(themeRoot(page)).toHaveAttribute("data-color-scheme", "dark");
    await expect
      .poll(() =>
        basemapStyleUrls.some((url) => url.includes("style-dark.json")),
      )
      .toBe(true);
    await expect(
      page.getByRole("link", { name: "Einstellungen öffnen" }),
    ).toBeVisible();
    await expect(page.getByTestId("theme-compact-button")).toHaveCount(0);

    await page.goto("/settings");
    await page.getByTestId("theme-select").selectOption("light");
    await expect(themeRoot(page)).toHaveAttribute("data-theme", "light");
  });

  test("gibt beim Start nur die aktuelle Basemap-Stilgeneration frei", async ({
    page,
  }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("weltgewebe.theme", "dark");
    });
    await mockApiResponses(page);

    const emptyStyleBody = JSON.stringify({
      version: 8,
      sources: {},
      layers: [],
    });
    let markDarkRequested!: () => void;
    let markLightRequested!: () => void;
    let releaseDark!: () => void;
    let releaseLight!: () => void;
    const darkRequested = new Promise<void>((resolve) => {
      markDarkRequested = resolve;
    });
    const lightRequested = new Promise<void>((resolve) => {
      markLightRequested = resolve;
    });
    const darkRelease = new Promise<void>((resolve) => {
      releaseDark = resolve;
    });
    const lightRelease = new Promise<void>((resolve) => {
      releaseLight = resolve;
    });

    await page.route("**/local-basemap/style-dark.json*", async (route) => {
      markDarkRequested();
      await darkRelease;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: emptyStyleBody,
      });
    });
    await page.route("**/local-basemap/style.json*", async (route) => {
      markLightRequested();
      await lightRelease;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: emptyStyleBody,
      });
    });

    await page.goto("/map", { waitUntil: "domcontentloaded" });
    await darkRequested;
    await page.waitForFunction(() => Boolean((window as any).__TEST_MAP__));
    await expect(page.locator(".loading-overlay")).toBeVisible();

    await page.evaluate(() => {
      document.documentElement.dataset.colorScheme = "light";
    });
    await lightRequested;
    await expect(themeRoot(page)).toHaveAttribute("data-color-scheme", "light");

    // Simuliert ein verspätetes generisches load-Ereignis der überholten
    // dunklen Startkarte. Es darf den dunklen Frame nicht sichtbar machen,
    // solange der inzwischen gültige helle Stil noch lädt.
    await page.evaluate(() => {
      (window as any).__TEST_MAP__.fire("load");
    });
    await expect(page.locator(".loading-overlay")).toBeVisible();
    await expect(page.locator("#map")).toHaveClass(/map-loading/);

    releaseLight();
    await expect
      .poll(() =>
        page.evaluate(
          () => (window as any).__TEST_MAP__?.isStyleLoaded() ?? false,
        ),
      )
      .toBe(true);
    await expect(page.locator(".loading-overlay")).toHaveCount(0);
    await expect(page.locator("#map")).not.toHaveClass(/map-loading/);

    releaseDark();
  });

  test("wechselt den Kartenstil live und rehydriert die Fadenebenen", async ({
    page,
  }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("weltgewebe.theme", "light");
    });
    await mockApiResponses(page);

    const styleRequests: string[] = [];
    page.on("request", (request) => {
      const url = request.url();
      if (url.includes("/local-basemap/style")) styleRequests.push(url);
    });

    await page.goto("/map");
    await expect(themeRoot(page)).toHaveAttribute("data-color-scheme", "light");
    await page.waitForFunction(() => {
      const map = (window as any).__TEST_MAP__;
      return Boolean(
        map?.isStyleLoaded() && map.getLayer("edges-vote-highlight-layer"),
      );
    });

    const before = await page.evaluate(() => {
      const map = (window as any).__TEST_MAP__;
      const center = map.getCenter();
      return {
        lng: center.lng,
        lat: center.lat,
        zoom: map.getZoom(),
        bearing: map.getBearing(),
        pitch: map.getPitch(),
      };
    });

    const lightRequestsBeforeRapidSwitch = styleRequests.filter((url) =>
      /\/style\.json(?:\?|$)/.test(url),
    ).length;
    await page.evaluate(async () => {
      const root = document.documentElement;
      const nextTask = () =>
        new Promise<void>((resolve) => window.setTimeout(resolve, 0));
      root.dataset.colorScheme = "dark";
      await nextTask();
      root.dataset.colorScheme = "light";
      await nextTask();
      root.dataset.colorScheme = "dark";
    });
    await expect
      .poll(() => styleRequests.some((url) => url.includes("style-dark.json")))
      .toBe(true);
    await expect
      .poll(
        () =>
          styleRequests.filter((url) => /\/style\.json(?:\?|$)/.test(url))
            .length,
      )
      .toBeGreaterThan(lightRequestsBeforeRapidSwitch);
    await page.waitForFunction(() => {
      const map = (window as any).__TEST_MAP__;
      const layers = map?.getStyle()?.layers ?? [];
      const edgeLayerIds = layers
        .map((layer: { id: string }) => layer.id)
        .filter((id: string) => id.startsWith("edges-"));
      return (
        map?.isStyleLoaded() &&
        Boolean(map.getSource("edges-source")) &&
        edgeLayerIds.length === 15 &&
        new Set(edgeLayerIds).size === 15
      );
    });

    const afterDark = await page.evaluate(() => {
      const map = (window as any).__TEST_MAP__;
      const center = map.getCenter();
      return {
        lng: center.lng,
        lat: center.lat,
        zoom: map.getZoom(),
        bearing: map.getBearing(),
        pitch: map.getPitch(),
      };
    });
    expect(afterDark.lng).toBeCloseTo(before.lng, 7);
    expect(afterDark.lat).toBeCloseTo(before.lat, 7);
    expect(afterDark.zoom).toBeCloseTo(before.zoom, 7);
    expect(afterDark.bearing).toBeCloseTo(before.bearing, 7);
    expect(afterDark.pitch).toBeCloseTo(before.pitch, 7);

    const lightRequestsBeforeSwitchBack = styleRequests.filter((url) =>
      /\/style\.json(?:\?|$)/.test(url),
    ).length;
    await page.evaluate(() => {
      document.documentElement.dataset.colorScheme = "light";
    });
    await expect
      .poll(
        () =>
          styleRequests.filter((url) => /\/style\.json(?:\?|$)/.test(url))
            .length,
      )
      .toBeGreaterThan(lightRequestsBeforeSwitchBack);
    await page.waitForFunction(() => {
      const map = (window as any).__TEST_MAP__;
      const edgeLayerIds = (map?.getStyle()?.layers ?? [])
        .map((layer: { id: string }) => layer.id)
        .filter((id: string) => id.startsWith("edges-"));
      return (
        map?.isStyleLoaded() &&
        Boolean(map.getSource("edges-source")) &&
        edgeLayerIds.length === 15 &&
        new Set(edgeLayerIds).size === 15
      );
    });
  });

  test("hält Einstellungen und Anmeldung bei 320 Pixeln frei berührbar", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 320, height: 640 });
    await page.route("**/_app/version.json", (route) =>
      route.fulfill({ status: 404, body: "" }),
    );
    await page.route("**/api/auth/me", (route) =>
      route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({
          authenticated: false,
          account_id: null,
          role: "gast",
        }),
      }),
    );
    await page.goto("/map");

    const settings = page.getByRole("link", { name: "Einstellungen öffnen" });
    const login = page.getByRole("link", { name: "Anmelden" });
    const governance = page.getByTestId("governance-fan-trigger");
    await expect(settings).toBeVisible();
    await expect(login).toBeVisible();
    await expect(governance).toBeVisible();

    const settingsBox = await settings.boundingBox();
    const loginBox = await login.boundingBox();
    const governanceBox = await governance.boundingBox();
    expect(settingsBox).not.toBeNull();
    expect(loginBox).not.toBeNull();
    expect(governanceBox).not.toBeNull();
    expect(settingsBox!.x + 0.5).toBeGreaterThanOrEqual(
      governanceBox!.x + governanceBox!.width,
    );
    expect(loginBox!.x).toBeGreaterThanOrEqual(
      settingsBox!.x + settingsBox!.width,
    );
    expect(loginBox!.x + loginBox!.width).toBeLessThanOrEqual(320);

    for (const [label, target] of [
      ["Einstellungen", settings],
      ["Anmelden", login],
    ] as const) {
      const hitTest = await target.evaluate((element) => {
        const rect = element.getBoundingClientRect();
        const hit = document.elementFromPoint(
          rect.left + rect.width / 2,
          rect.top + rect.height / 2,
        );
        return {
          receivesPointer:
            hit === element || (hit !== null && element.contains(hit)),
          hitElement: hit
            ? `${hit.tagName.toLowerCase()}.${Array.from(hit.classList).join(".")}`
            : "none",
        };
      });
      expect(
        hitTest.receivesPointer,
        `${label} wird in der Mitte von ${hitTest.hitElement} überlagert`,
      ).toBe(true);
    }
  });

  test("hält Gastzugriffe bis zur sicheren Textbreite kollisionsfrei", async ({
    page,
  }) => {
    await page.route("**/_app/version.json", (route) =>
      route.fulfill({ status: 404, body: "" }),
    );
    await page.route("**/api/auth/me", (route) =>
      route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({
          authenticated: false,
          account_id: null,
          role: "gast",
        }),
      }),
    );

    for (const width of [361, 375, 390, 414, 430, 480, 510, 511]) {
      await page.setViewportSize({ width, height: 720 });
      await page.goto("/map");

      const settings = page.getByRole("link", {
        name: "Einstellungen öffnen",
      });
      const login = page.getByRole("link", { name: "Anmelden" });
      const governance = page.getByTestId("governance-fan-trigger");
      await expect(settings).toBeVisible();
      await expect(login).toBeVisible();
      await expect(governance).toBeVisible();

      const settingsBox = await settings.boundingBox();
      const loginBox = await login.boundingBox();
      const governanceBox = await governance.boundingBox();
      expect(settingsBox, `${width}px: Einstellungen fehlen`).not.toBeNull();
      expect(loginBox, `${width}px: Anmeldung fehlt`).not.toBeNull();
      expect(governanceBox, `${width}px: Mitentscheiden fehlt`).not.toBeNull();
      expect(
        settingsBox!.x + 0.5,
        `${width}px: Einstellungen überlappen Mitentscheiden`,
      ).toBeGreaterThanOrEqual(governanceBox!.x + governanceBox!.width);
      expect(
        loginBox!.x,
        `${width}px: Anmeldung überlappt Einstellungen`,
      ).toBeGreaterThanOrEqual(settingsBox!.x + settingsBox!.width);
      expect(
        loginBox!.x + loginBox!.width,
        `${width}px: Anmeldung verlässt den Bildschirm`,
      ).toBeLessThanOrEqual(width);

      for (const [label, target] of [
        ["Einstellungen", settings],
        ["Anmelden", login],
      ] as const) {
        const hitTest = await target.evaluate((element) => {
          const rect = element.getBoundingClientRect();
          const hit = document.elementFromPoint(
            rect.left + rect.width / 2,
            rect.top + rect.height / 2,
          );
          return {
            receivesPointer:
              hit === element || (hit !== null && element.contains(hit)),
            hitElement: hit
              ? `${hit.tagName.toLowerCase()}.${Array.from(hit.classList).join(".")}`
              : "none",
          };
        });
        expect(
          hitTest.receivesPointer,
          `${width}px: ${label} wird in der Mitte von ${hitTest.hitElement} überlagert`,
        ).toBe(true);
      }

      const loginLabel = login.locator(".auth-label");
      if (width <= 510) {
        await expect(loginLabel).toBeHidden();
      } else {
        await expect(loginLabel).toBeVisible();
      }
    }
  });

  test("zeigt private Nachrichten angemeldeten Webern direkt in der Kartenleiste", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 320, height: 640 });
    await page.route("**/_app/version.json", (route) =>
      route.fulfill({ status: 404, body: "" }),
    );
    await page.route("**/api/auth/me", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          authenticated: true,
          account_id: "weber-test",
          role: "weber",
        }),
      }),
    );
    await page.goto("/map");

    const messages = page.getByRole("link", { name: "Private Nachrichten" });
    const settings = page.getByRole("link", { name: "Einstellungen öffnen" });
    const governance = page.getByTestId("governance-fan-trigger");
    await expect(messages).toBeVisible();
    await expect(messages).toHaveAttribute("href", "/nachrichten");
    await expect(settings).toBeVisible();
    await expect(governance).toBeVisible();

    const messagesBox = await messages.boundingBox();
    const settingsBox = await settings.boundingBox();
    const governanceBox = await governance.boundingBox();
    expect(messagesBox).not.toBeNull();
    expect(settingsBox).not.toBeNull();
    expect(governanceBox).not.toBeNull();
    expect(messagesBox!.x + 0.5).toBeGreaterThanOrEqual(
      governanceBox!.x + governanceBox!.width,
    );
    expect(settingsBox!.x).toBeGreaterThanOrEqual(
      messagesBox!.x + messagesBox!.width,
    );
    expect(settingsBox!.x + settingsBox!.width).toBeLessThanOrEqual(320);

    for (const [label, target] of [
      ["Private Nachrichten", messages],
      ["Einstellungen", settings],
    ] as const) {
      const hitTest = await target.evaluate((element) => {
        const rect = element.getBoundingClientRect();
        const hit = document.elementFromPoint(
          rect.left + rect.width / 2,
          rect.top + rect.height / 2,
        );
        return {
          receivesPointer:
            hit === element || (hit !== null && element.contains(hit)),
          hitElement: hit
            ? `${hit.tagName.toLowerCase()}.${Array.from(hit.classList).join(".")}`
            : "none",
        };
      });
      expect(
        hitTest.receivesPointer,
        `${label} wird in der Mitte von ${hitTest.hitElement} überlagert`,
      ).toBe(true);
    }
  });

  test("ordnet Kopf und Darstellungssteuerung ohne Überlappung", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1180, height: 820 });
    await page.goto("/settings");

    const backLink = page.getByRole("link", { name: /Zur Karte/ });
    const heading = page.getByRole("heading", { name: "Einstellungen" });
    const themeSelect = page.getByTestId("theme-select");
    const diagnostics = page.getByTestId("build-diagnostics-link");

    const backLinkBox = await backLink.boundingBox();
    const headingBox = await heading.boundingBox();
    const themeSelectBox = await themeSelect.boundingBox();
    const diagnosticsBox = await diagnostics.boundingBox();

    expect(backLinkBox).not.toBeNull();
    expect(headingBox).not.toBeNull();
    expect(themeSelectBox).not.toBeNull();
    expect(diagnosticsBox).not.toBeNull();

    expect(backLinkBox!.width).toBeLessThanOrEqual(180);
    expect(headingBox!.y).toBeGreaterThanOrEqual(
      backLinkBox!.y + backLinkBox!.height,
    );
    expect(
      headingBox!.y - (backLinkBox!.y + backLinkBox!.height),
    ).toBeLessThanOrEqual(24);
    expect(diagnosticsBox!.y).toBeGreaterThanOrEqual(
      themeSelectBox!.y + themeSelectBox!.height + 8,
    );
  });

  test("hält den Rückweg zur Karte in Hell und Dunkel lesbar", async ({
    page,
  }) => {
    await page.goto("/settings");

    const backLink = page.getByRole("link", { name: /Zur Karte/ });
    const themeSelect = page.getByTestId("theme-select");
    await expect(backLink).toBeVisible();
    const backLinkBox = await backLink.boundingBox();
    expect(backLinkBox).not.toBeNull();
    expect(backLinkBox!.height).toBeGreaterThanOrEqual(44);

    for (const theme of ["dark", "light"] as const) {
      await themeSelect.selectOption(theme);
      await expectReadableSurface(backLink, `Rückweg im Modus ${theme}`);
    }
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

  test("verwendet glatte Flächen ohne wiederholte Streifen", async ({
    page,
  }) => {
    await page.goto("/settings");

    await expectNoStripePattern(page.locator("body"), "Seitenhintergrund");
    await expectNoStripePattern(
      page.getByTestId("settings-menu"),
      "Einstellungsmenü",
    );
    await expectNoStripePattern(
      page.locator(".settings-content .panel").first(),
      "Inhaltskarte",
    );
  });

  test("ordnet das Menü auf kleinen Bildschirmen ohne Überlauf unter die Überschrift", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1180, height: 820 });
    await page.goto("/settings");

    const menu = page.getByTestId("settings-menu");
    const content = page.locator("main.settings-content");
    const desktopMenu = await menu.boundingBox();
    const desktopContent = await content.boundingBox();
    expect(desktopMenu).not.toBeNull();
    expect(desktopContent).not.toBeNull();
    expect(desktopContent!.x).toBeGreaterThan(desktopMenu!.x);

    await page.setViewportSize({ width: 390, height: 844 });
    const mobileMenu = await menu.boundingBox();
    const mobileContent = await content.boundingBox();
    expect(mobileMenu).not.toBeNull();
    expect(mobileContent).not.toBeNull();
    expect(mobileContent!.y).toBeGreaterThan(mobileMenu!.y);
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBeLessThanOrEqual(390);
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
