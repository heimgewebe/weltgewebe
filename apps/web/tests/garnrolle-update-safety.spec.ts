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
