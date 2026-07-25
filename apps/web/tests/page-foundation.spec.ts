import { expect, test } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test("login uses the shared page, form and status foundation", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/login");

  await expect(page).toHaveTitle("Anmelden · Weltgewebe");
  await expect(
    page.getByRole("heading", { name: "Anmelden", level: 1 }),
  ).toBeVisible();
  await expect(page.locator("main.wg-page")).toBeVisible();
  await expect(page.locator("main [style]")).toHaveCount(0);

  const email = page.getByLabel("E-Mail-Adresse");
  const submit = page.getByRole("button", { name: "Anmeldelink senden" });
  expect((await email.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  expect((await submit.boundingBox())!.height).toBeGreaterThanOrEqual(44);

  const background = await page
    .locator("body")
    .evaluate((element) => getComputedStyle(element).backgroundColor);
  expect(background).toBe("rgb(15, 17, 21)");
});

test("the proposal overview uses the same responsive page foundation", async ({
  page,
}) => {
  await mockApiResponses(page, {
    auth: { authenticated: false },
  });
  await page.route("**/api/proposals**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: "[]",
    });
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/antraege");

  await expect(page.locator("main.wg-page")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Anträge", level: 1 }),
  ).toBeVisible();
  await expect(page.getByText("Noch liegen keine Anträge vor.")).toBeVisible();

  const filters = page.getByRole("navigation", {
    name: "Governance-Ereignisse filtern",
  });
  for (const link of await filters.getByRole("link").all()) {
    expect((await link.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  }

  const active = filters.getByRole("link", { name: "Alle", exact: true });
  await expect(active).toHaveAttribute("aria-current", "page");
  const background = await page
    .locator("body")
    .evaluate((element) => getComputedStyle(element).backgroundColor);
  expect(background).toBe("rgb(15, 17, 21)");
});

test("a proposal API failure does not masquerade as an empty list", async ({
  page,
}) => {
  await mockApiResponses(page, {
    auth: { authenticated: false },
  });
  await page.route("**/api/proposals**", async (route) => {
    await route.fulfill({ status: 503, body: "temporarily unavailable" });
  });
  await page.goto("/antraege");

  await expect(
    page.getByRole("alert").filter({
      hasText: "Das Antragssystem ist vorübergehend nicht verfügbar.",
    }),
  ).toBeVisible();
  await expect(page.getByText("Noch liegen keine Anträge vor.")).toHaveCount(0);
  await expect(
    page.getByText("Für diese Ansicht liegen keine Anträge vor."),
  ).toHaveCount(0);
});
