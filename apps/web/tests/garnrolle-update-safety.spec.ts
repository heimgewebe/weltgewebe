import { expect, test, type Page, type Route } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

const ACCOUNT_ID = "00000000-0000-0000-0000-000000000003";
const PRIVATE_ONLY_ACCOUNT_ID = "00000000-0000-0000-0000-000000000099";

type Profile = {
  id: string;
  title: string;
  summary: string;
  tags: string[];
  address?: string;
  location: { lat: number; lon: number } | null;
  map_state: "not_on_map" | "exact" | "radius";
  radius_m: number;
};

async function installProfileRoute(
  page: Page,
  profile: Profile,
  patchHandler?: (
    route: Route,
    payload: Record<string, unknown>,
  ) => Promise<void>,
) {
  await page.route("**/api/accounts/me/profile", async (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(profile),
      });
    }
    if (route.request().method() !== "PATCH") return route.fallback();

    const payload = route.request().postDataJSON() as Record<string, unknown>;
    if (patchHandler) return patchHandler(route, payload);

    profile.title = String(payload.title);
    if (typeof payload.address === "string") profile.address = payload.address;
    if (payload.clear_address === true) delete profile.address;
    profile.map_state = payload.map_state as Profile["map_state"];
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(profile),
    });
  });
}

async function openProfile(page: Page, accountId = ACCOUNT_ID) {
  await mockApiResponses(page, {
    auth: { authenticated: true, account_id: accountId, role: "weber" },
  });
  const profile: Profile = {
    id: accountId,
    title: "Bestehende Garnrolle",
    summary: "Bereits eingerichtet",
    tags: ["account", "garnrolle"],
    address: "Private Ortsnotiz",
    location: { lat: 53.5, lon: 10.0 },
    map_state: "not_on_map",
    radius_m: 0,
  };
  await installProfileRoute(page, profile);
  await page.goto("/settings#meine-garnrolle");
  const section = page.locator('[data-testid="my-garnrolle-section"]');
  await expect(section.getByLabel("Anzeigename")).toHaveValue(profile.title);
  await expect(section.locator('[data-testid="save-garnrolle"]')).toBeEnabled();
  return { section, profile };
}

test.describe("Garnrolle update safety", () => {
  test("validates trimmed Unicode lengths without hiding or truncating input", async ({
    page,
  }) => {
    const { section } = await openProfile(page);
    const displayName = section.getByLabel("Anzeigename");
    const summary = section.getByLabel("Kurzbeschreibung");
    const save = section.locator('[data-testid="save-garnrolle"]');
    const overlongName = "🐋".repeat(201);
    const validName = `  ${"🐋".repeat(200)}  `;
    const overlongSummary = "🐋".repeat(501);
    const validSummary = `  ${"🐋".repeat(500)}  `;

    await displayName.fill(overlongName);
    await expect(displayName).toHaveValue(overlongName);
    await expect(displayName).toHaveAttribute("aria-invalid", "true");
    await expect(
      section.locator("#garnrolle-display-name-length"),
    ).toContainText("201/200 Unicode-Zeichen");
    await expect(save).toBeDisabled();

    await displayName.fill(validName);
    await expect(displayName).toHaveValue(validName);
    await expect(displayName).toHaveAttribute("aria-invalid", "false");
    await expect(
      section.locator("#garnrolle-display-name-length"),
    ).toContainText("200/200 Unicode-Zeichen");

    await summary.fill(overlongSummary);
    await expect(summary).toHaveValue(overlongSummary);
    await expect(summary).toHaveAttribute("aria-invalid", "true");
    await expect(section.locator("#garnrolle-summary-length")).toContainText(
      "501/500 Unicode-Zeichen",
    );
    await expect(save).toBeDisabled();

    await summary.fill(validSummary);
    await expect(summary).toHaveValue(validSummary);
    await expect(summary).toHaveAttribute("aria-invalid", "false");
    await expect(section.locator("#garnrolle-summary-length")).toContainText(
      "500/500 Unicode-Zeichen",
    );
    await expect(save).toBeEnabled();

    const requestPromise = page.waitForRequest(
      (request) =>
        request.url().endsWith("/api/accounts/me/profile") &&
        request.method() === "PATCH",
    );
    await save.click();
    const payload = (await requestPromise).postDataJSON();
    expect(payload.title).toBe("🐋".repeat(200));
    expect(payload.summary).toBe("🐋".repeat(500));
  });

  test("keeps an overlong loaded summary visible and blocks saving until it is corrected", async ({
    page,
  }) => {
    await mockApiResponses(page, {
      auth: { authenticated: true, account_id: ACCOUNT_ID, role: "weber" },
    });
    const legacySummary = "🐋".repeat(501);
    const validSummary = "🐋".repeat(500);
    const profile: Profile = {
      id: ACCOUNT_ID,
      title: "Bestehende Garnrolle",
      summary: legacySummary,
      tags: ["account", "garnrolle"],
      location: null,
      map_state: "not_on_map",
      radius_m: 0,
    };
    let savedPayload: Record<string, unknown> | null = null;
    await installProfileRoute(page, profile, async (route, payload) => {
      savedPayload = payload;
      profile.title = String(payload.title);
      profile.summary = String(payload.summary);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(profile),
      });
    });

    await page.goto("/settings#meine-garnrolle");
    const section = page.locator('[data-testid="my-garnrolle-section"]');
    const summary = section.getByLabel("Kurzbeschreibung");
    const save = section.locator('[data-testid="save-garnrolle"]');

    await expect(summary).toHaveValue(legacySummary);
    await expect(summary).toHaveAttribute("aria-invalid", "true");
    await expect(section.locator("#garnrolle-summary-length")).toContainText(
      "501/500 Unicode-Zeichen",
    );
    await expect(save).toBeDisabled();

    await summary.fill(validSummary);
    await expect(summary).toHaveValue(validSummary);
    await expect(summary).toHaveAttribute("aria-invalid", "false");
    await expect(save).toBeEnabled();
    await save.click();

    expect(savedPayload).toMatchObject({ summary: validSummary });
  });

  test("keeps an overlong summary restored from session storage visible and invalid", async ({
    page,
  }) => {
    const legacySummary = "🐋".repeat(501);
    await page.addInitScript(
      ({ accountId, restoredSummary }) => {
        sessionStorage.setItem(
          `weltgewebe:garnrolle-draft:${accountId}`,
          JSON.stringify({ summary: restoredSummary }),
        );
      },
      { accountId: ACCOUNT_ID, restoredSummary: legacySummary },
    );
    await mockApiResponses(page, {
      auth: { authenticated: true, account_id: ACCOUNT_ID, role: "weber" },
    });
    const profile: Profile = {
      id: ACCOUNT_ID,
      title: "Bestehende Garnrolle",
      summary: "Bereits eingerichtet",
      tags: ["account", "garnrolle"],
      location: null,
      map_state: "not_on_map",
      radius_m: 0,
    };
    await installProfileRoute(page, profile);

    await page.goto("/settings#meine-garnrolle");
    const section = page.locator('[data-testid="my-garnrolle-section"]');
    const summary = section.getByLabel("Kurzbeschreibung");

    await expect(summary).toHaveValue(legacySummary);
    await expect(summary).toHaveAttribute("aria-invalid", "true");
    await expect(section.locator("#garnrolle-summary-length")).toContainText(
      "501/500 Unicode-Zeichen",
    );
    await expect(
      section.locator('[data-testid="save-garnrolle"]'),
    ).toBeDisabled();
  });

  test("keeps an overlong loaded tag visible and blocks saving until its prefixed value fits", async ({
    page,
  }) => {
    await mockApiResponses(page, {
      auth: { authenticated: true, account_id: ACCOUNT_ID, role: "weber" },
    });
    const legacyValue = "🐋".repeat(59);
    const correctedValue = "🐋".repeat(58);
    const profile: Profile = {
      id: ACCOUNT_ID,
      title: "Bestehende Garnrolle",
      summary: "Bereits eingerichtet",
      tags: [`skill:${legacyValue}`, "account", "garnrolle"],
      location: null,
      map_state: "not_on_map",
      radius_m: 0,
    };
    let savedPayload: Record<string, unknown> | null = null;
    await installProfileRoute(page, profile, async (route, payload) => {
      savedPayload = payload;
      profile.tags = payload.tags as string[];
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(profile),
      });
    });

    await page.goto("/settings#meine-garnrolle");
    const section = page.locator('[data-testid="my-garnrolle-section"]');
    const skills = section.getByLabel("Fähigkeiten");
    const save = section.locator('[data-testid="save-garnrolle"]');

    await expect(skills).toHaveValue(legacyValue);
    await expect(skills).toHaveAttribute("aria-invalid", "true");
    await expect(section.locator("#garnrolle-tags-help")).toContainText(
      "samt Präfix",
    );
    await expect(save).toBeDisabled();

    await skills.fill(correctedValue);
    await expect(skills).toHaveAttribute("aria-invalid", "false");
    await expect(save).toBeEnabled();
    await save.click();
    expect(savedPayload).toMatchObject({
      tags: [`skill:${correctedValue}`],
    });
  });

  test("counts the two required server tags before enabling save", async ({
    page,
  }) => {
    const { section } = await openProfile(page);
    const skills = section.getByLabel("Fähigkeiten");
    const save = section.locator('[data-testid="save-garnrolle"]');
    const values = Array.from({ length: 63 }, (_, index) => `Tag ${index}`);

    await skills.fill(values.join(","));
    await expect(section.locator("#garnrolle-tags-help")).toContainText(
      "Maximal 62",
    );
    await expect(skills).toHaveAttribute("aria-invalid", "true");
    await expect(save).toBeDisabled();

    await skills.fill(values.slice(0, 62).join(","));
    await expect(section.locator("#garnrolle-tags-help")).toHaveCount(0);
    await expect(skills).toHaveAttribute("aria-invalid", "false");
    await expect(save).toBeEnabled();

    const requestPromise = page.waitForRequest(
      (request) =>
        request.url().endsWith("/api/accounts/me/profile") &&
        request.method() === "PATCH",
    );
    await save.click();
    expect((await requestPromise).postDataJSON().tags).toHaveLength(62);
  });

  test("preserves an untouched private address by omission", async ({
    page,
  }) => {
    const { section } = await openProfile(page);
    await section.getByLabel("Anzeigename").fill("Nur Titel geändert");

    const requestPromise = page.waitForRequest(
      (request) =>
        request.url().endsWith("/api/accounts/me/profile") &&
        request.method() === "PATCH",
    );
    await section.locator('[data-testid="save-garnrolle"]').click();
    const payload = (await requestPromise).postDataJSON();

    expect(payload).not.toHaveProperty("address");
    expect(payload).not.toHaveProperty("clear_address");
    await expect(
      section.locator('[data-testid="garnrolle-success"]'),
    ).toContainText("gespeichert");
  });

  test("sends clear_address only after the user empties the field", async ({
    page,
  }) => {
    const { section } = await openProfile(page);
    await section.getByLabel("Adresse oder Ortsnotiz").fill("");

    const requestPromise = page.waitForRequest(
      (request) =>
        request.url().endsWith("/api/accounts/me/profile") &&
        request.method() === "PATCH",
    );
    await section.locator('[data-testid="save-garnrolle"]').click();
    const payload = (await requestPromise).postDataJSON();

    expect(payload).toMatchObject({ clear_address: true });
    expect(payload).not.toHaveProperty("address");
  });

  test("keeps saving available after a rejected save", async ({ page }) => {
    await mockApiResponses(page, {
      auth: { authenticated: true, account_id: ACCOUNT_ID, role: "weber" },
    });
    const profile: Profile = {
      id: ACCOUNT_ID,
      title: "Bestehende Garnrolle",
      summary: "Bereits eingerichtet",
      tags: ["account", "garnrolle"],
      address: "Private Ortsnotiz",
      location: { lat: 53.5, lon: 10.0 },
      map_state: "not_on_map",
      radius_m: 0,
    };
    let attempt = 0;
    await installProfileRoute(page, profile, async (route, payload) => {
      attempt += 1;
      if (attempt === 1) return route.fulfill({ status: 400 });
      profile.title = String(payload.title);
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(profile),
      });
    });
    await page.goto("/settings#meine-garnrolle");
    const section = page.locator('[data-testid="my-garnrolle-section"]');
    const save = section.locator('[data-testid="save-garnrolle"]');
    await expect(save).toBeEnabled();

    await save.click();
    await expect(
      section.locator('[data-testid="garnrolle-error"]'),
    ).toBeVisible();
    await expect(save).toBeEnabled();

    await save.click();
    await expect(
      section.locator('[data-testid="garnrolle-success"]'),
    ).toContainText("gespeichert");
    expect(attempt).toBe(2);
  });

  test("allows a matching private profile to remain editable without a public account row", async ({
    page,
  }) => {
    const { section } = await openProfile(page, PRIVATE_ONLY_ACCOUNT_ID);

    await expect(
      section.locator('[data-testid="my-garnrolle-status"]'),
    ).toContainText("Nicht verfügbar");
    await expect(
      section.locator('[data-testid="my-garnrolle-status"]'),
    ).toContainText("private Profil bleibt bearbeitbar");
    await expect(
      section.locator('[data-testid="save-garnrolle"]'),
    ).toBeEnabled();
  });
});
