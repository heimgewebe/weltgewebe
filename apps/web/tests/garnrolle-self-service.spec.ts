import { expect, test, type Page } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

const ACCOUNT_ID = "00000000-0000-0000-0000-000000000003";

async function openSettingsAsWeber(page: Page) {
  await mockApiResponses(page, {
    auth: {
      authenticated: true,
      account_id: ACCOUNT_ID,
      role: "weber",
    },
  });
  const profileResponse = page.waitForResponse((response) =>
    response.url().endsWith("/api/accounts/me/profile"),
  );
  await page.goto("/settings#meine-garnrolle");
  expect((await profileResponse).status()).toBe(200);
  const section = page.locator('[data-testid="my-garnrolle-section"]');
  await expect(section).toBeVisible();
  await expect(section.getByLabel("Anzeigename")).not.toHaveValue("");
  await expect(section.locator('[data-testid="save-garnrolle"]')).toBeEnabled();
  return section;
}

async function longPressMapCenter(page: Page) {
  const map = page.locator("#map");
  await expect(map).toBeVisible();
  await map.hover({ position: { x: 50, y: 50 } });
  await page.mouse.down();
  await page.waitForTimeout(950);
  await page.mouse.up();
}

test.describe("Eigene Garnrolle speichern", () => {
  test("clears sensitive Garnrolle drafts on logout", async ({ page }) => {
    await mockApiResponses(page, {
      auth: {
        authenticated: true,
        account_id: ACCOUNT_ID,
        role: "weber",
      },
    });
    await page.goto("/settings#meine-garnrolle");
    await page.evaluate((accountId) => {
      sessionStorage.setItem(
        `weltgewebe:garnrolle-draft:${accountId}`,
        JSON.stringify({ address: "private draft" }),
      );
      sessionStorage.setItem(
        "weltgewebe:garnrolle-draft:previous-account",
        JSON.stringify({ address: "stale private draft" }),
      );
      sessionStorage.setItem("weltgewebe:unrelated-test", "keep");
    }, ACCOUNT_ID);
    await page.reload();
    await expect(
      page.locator('[data-testid="account-section-status"]'),
    ).toBeVisible();
    const afterAuthenticatedReload = await page.evaluate(
      (accountId) => ({
        current: sessionStorage.getItem(
          `weltgewebe:garnrolle-draft:${accountId}`,
        ),
        previous: sessionStorage.getItem(
          "weltgewebe:garnrolle-draft:previous-account",
        ),
      }),
      ACCOUNT_ID,
    );
    expect(afterAuthenticatedReload.current).not.toBeNull();
    expect(afterAuthenticatedReload.previous).toBeNull();
    await page.evaluate((accountId) => {
      sessionStorage.setItem(
        `weltgewebe:garnrolle-return-location:${accountId}`,
        JSON.stringify({ lat: 53.5, lon: 10.0 }),
      );
    }, ACCOUNT_ID);

    await page.locator('[data-testid="account-section-logout"]').click();
    await expect(
      page.locator('[data-testid="account-section-anonymous"]'),
    ).toBeVisible();
    const remaining = await page.evaluate(
      (accountId) => ({
        draft: sessionStorage.getItem(
          `weltgewebe:garnrolle-draft:${accountId}`,
        ),
        location: sessionStorage.getItem(
          `weltgewebe:garnrolle-return-location:${accountId}`,
        ),
        unrelated: sessionStorage.getItem("weltgewebe:unrelated-test"),
      }),
      ACCOUNT_ID,
    );
    expect(remaining).toEqual({
      draft: null,
      location: null,
      unrelated: "keep",
    });
  });

  test("keeps the form read-only for a guest account", async ({ page }) => {
    await mockApiResponses(page, {
      auth: {
        authenticated: true,
        account_id: ACCOUNT_ID,
        role: "gast",
      },
    });
    await page.goto("/settings#meine-garnrolle");
    const section = page.locator('[data-testid="my-garnrolle-section"]');
    await expect(
      section.locator('[data-testid="garnrolle-role-warning"]'),
    ).toContainText("keine Weber-Berechtigung");
    await expect(
      section.locator('[data-testid="save-garnrolle"]'),
    ).toBeDisabled();
  });

  test("saves a not-on-map profile and reloads the persisted values", async ({
    page,
  }) => {
    const section = await openSettingsAsWeber(page);
    const save = section.locator('[data-testid="save-garnrolle"]');

    await section.getByLabel("Anzeigename").fill("Alex im Weltgewebe");
    await section
      .getByLabel("Kurzbeschreibung")
      .fill("Ich beginne meine Garnrolle selbst.");
    await section.getByLabel("Fähigkeiten").fill("Organisation, Kochen");
    await section.getByLabel("Güter").fill("Werkzeug");
    await section.getByLabel("Interessen").fill("Commons");
    await section.getByLabel("Noch nicht auf der Karte").check();
    await expect(save).toBeEnabled();

    const requestPromise = page.waitForRequest(
      (request) =>
        request.url().endsWith("/api/accounts/me/profile") &&
        request.method() === "PATCH",
    );
    await save.click();
    const request = await requestPromise;
    expect(request.postDataJSON()).toMatchObject({
      title: "Alex im Weltgewebe",
      summary: "Ich beginne meine Garnrolle selbst.",
      map_state: "not_on_map",
      tags: [
        "skill:Organisation",
        "skill:Kochen",
        "good:Werkzeug",
        "interest:Commons",
      ],
    });
    await expect(
      section.locator('[data-testid="garnrolle-success"]'),
    ).toContainText("gespeichert");

    await page.reload();
    await expect(page.getByLabel("Anzeigename")).toHaveValue(
      "Alex im Weltgewebe",
    );
    await expect(page.getByLabel("Fähigkeiten")).toHaveValue(
      "Organisation, Kochen",
    );
  });

  test("requires a self-selected map point and preserves the draft across map navigation", async ({
    page,
  }) => {
    const section = await openSettingsAsWeber(page);
    await section.getByLabel("Anzeigename").fill("Garnrolle am gewählten Ort");
    await section.getByLabel("Adresse").fill("Poelsweg 2, Hamburg");
    await section.getByLabel("Fähigkeiten").fill("Nachbarschaftshilfe");
    await section.getByLabel("Exakt sichtbar").check();

    const save = section.locator('[data-testid="save-garnrolle"]');
    // The address is not silently geocoded. A point chosen by the user is required.
    await expect(save).toBeDisabled();
    await section.locator('[data-testid="choose-garnrolle-location"]').click();

    await expect(page).toHaveURL(/\/map\?compose=garnrolle/);
    const placement = page.locator('[data-testid="garnrolle-placement"]');
    await expect(placement).toContainText("Kartenpunkt ausstehend");
    await longPressMapCenter(page);
    await expect(placement).toContainText("Kartenpunkt gewählt");
    await placement
      .locator('[data-testid="confirm-garnrolle-location"]')
      .click();

    await expect(page).toHaveURL(/\/settings#meine-garnrolle$/);
    const returned = page.locator('[data-testid="my-garnrolle-section"]');
    await expect(returned.getByLabel("Anzeigename")).toHaveValue(
      "Garnrolle am gewählten Ort",
    );
    await expect(returned.getByLabel("Adresse")).toHaveValue(
      "Poelsweg 2, Hamburg",
    );
    await expect(
      returned.locator('[data-testid="garnrolle-location-state"]'),
    ).toContainText("Kartenpunkt gewählt");
    await expect(
      returned.locator('[data-testid="save-garnrolle"]'),
    ).toBeEnabled();

    const requestPromise = page.waitForRequest(
      (request) =>
        request.url().endsWith("/api/accounts/me/profile") &&
        request.method() === "PATCH",
    );
    await returned.locator('[data-testid="save-garnrolle"]').click();
    const payload = (await requestPromise).postDataJSON();
    expect(payload).toMatchObject({
      title: "Garnrolle am gewählten Ort",
      address: "Poelsweg 2, Hamburg",
      map_state: "exact",
      tags: ["skill:Nachbarschaftshilfe"],
    });
    expect(typeof payload.location?.lat).toBe("number");
    expect(typeof payload.location?.lon).toBe("number");
    await expect(
      returned.locator('[data-testid="garnrolle-success"]'),
    ).toContainText("gespeichert");

    await page.goto(`/map?focus=garnrolle:${ACCOUNT_ID}`);
    const panel = page.locator('[data-testid="context-panel"]');
    await expect(panel).toContainText("Fähigkeiten: Nachbarschaftshilfe");
    await expect(panel).not.toContainText("skill:Nachbarschaftshilfe");
  });
});

test.describe("Garnrollen-Kartenpunkt per Touch", () => {
  test.use({ hasTouch: true });

  test("accepts an iPad-style touch longpress", async ({ page }) => {
    await mockApiResponses(page, {
      auth: {
        authenticated: true,
        account_id: ACCOUNT_ID,
        role: "weber",
      },
    });
    await page.goto("/map?compose=garnrolle");
    const placement = page.locator('[data-testid="garnrolle-placement"]');
    await expect(placement).toContainText("Kartenpunkt ausstehend");

    const map = page.locator("#map canvas").first();
    const box = await map.boundingBox();
    if (!box) throw new Error("map has no bounding box");
    const touchPoint = { x: box.x + 50, y: box.y + 50 };
    const client = await page.context().newCDPSession(page);
    await client.send("Input.dispatchTouchEvent", {
      type: "touchStart",
      touchPoints: [touchPoint],
    });
    await page.waitForTimeout(950);
    await client.send("Input.dispatchTouchEvent", {
      type: "touchEnd",
      touchPoints: [],
    });
    await expect(placement).toContainText("Kartenpunkt gewählt");
  });
});
