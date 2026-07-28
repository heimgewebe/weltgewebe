import { expect, test, type Route } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test("login uses the shared page, form and state contracts without changing the request", async ({
  page,
}) => {
  await mockApiResponses(page, {
    auth: { authenticated: false },
  });

  let requestBody: unknown = null;
  await page.route("**/api/auth/magic-link/request", async (route: Route) => {
    requestBody = route.request().postDataJSON();
    await route.fulfill({ status: 204 });
  });

  await page.goto("/login");

  const loginPage = page.getByTestId("login-page");
  await expect(loginPage).toHaveClass(/wg-page/);
  await expect(loginPage.locator(".wg-card")).toHaveCount(1);
  await expect(loginPage.locator("[style]")).toHaveCount(0);
  await expect(loginPage).toHaveCSS("background-image", /radial-gradient/);
  const loginBox = await loginPage.boundingBox();
  expect(loginBox?.height).toBeGreaterThanOrEqual(
    await page.evaluate(() => window.innerHeight),
  );

  const emailInput = page.getByLabel("E-Mail");
  await page.keyboard.press("Tab");
  await expect(emailInput).toBeFocused();
  await expect
    .poll(() =>
      emailInput.evaluate((element) => getComputedStyle(element).outlineWidth),
    )
    .toBe("3px");

  await emailInput.fill("person@example.org");
  await page.getByRole("button", { name: "Login-Link senden" }).click();

  // The action module loads lazily, so observe the dispatched request rather than a synchronous implementation detail.
  await expect.poll(() => requestBody).toEqual({ email: "person@example.org" });
  await expect(page.getByRole("status")).toContainText("Postfach prüfen");
});

test("application overview uses the same surfaces, controls and empty-state contract", async ({
  page,
}) => {
  await mockApiResponses(page, {
    auth: {
      authenticated: true,
      account_id: "guest-design-system",
      role: "gast",
    },
  });
  await page.route("**/api/proposals**", async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: "[]",
    });
  });

  await page.goto("/antraege#antrag-stellen");

  const applicationsPage = page.getByTestId("applications-page");
  await expect(applicationsPage).toHaveClass(/wg-page--paper/);
  await expect
    .poll(() =>
      applicationsPage.evaluate((element) =>
        getComputedStyle(element).getPropertyValue("--wg-surface").trim(),
      ),
    )
    .toContain("color-mix");
  await expect(
    page.getByRole("heading", { name: "Anträge", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByLabel("Kurze Vorstellung oder Begründung"),
  ).toHaveClass(/wg-control/);
  const primaryAction = page.getByRole("button", {
    name: "Weberstatus beantragen",
  });
  await expect(primaryAction).toHaveClass(/wg-button--primary/);
  const primaryActionColors = await primaryAction.evaluate((element) => {
    const style = getComputedStyle(element);
    return { foreground: style.color, background: style.backgroundColor };
  });
  expect(primaryActionColors.foreground).not.toBe(
    primaryActionColors.background,
  );
  await expect(page.getByText("Noch liegen keine Anträge vor.")).toHaveClass(
    /wg-state/,
  );
  await expect(page.locator("#antrag-stellen")).toBeFocused();
  const filters = page.getByRole("navigation", {
    name: "Governance-Ereignisse filtern",
  });
  await expect(filters.getByRole("link")).toHaveCount(5);
  await expect(filters.getByRole("link", { name: "Alle" })).toHaveAttribute(
    "aria-current",
    "true",
  );
});

test("a proposal API failure is not presented as an empty list", async ({
  page,
}) => {
  await mockApiResponses(page, { auth: { authenticated: false } });
  await page.route("**/api/proposals**", async (route: Route) => {
    await route.fulfill({ status: 503, body: "temporarily unavailable" });
  });

  await page.goto("/antraege");

  await expect(page.getByRole("alert")).toContainText(
    "Das Antragssystem ist vorübergehend nicht verfügbar.",
  );
  await expect(page.getByText("Noch liegen keine Anträge vor.")).toHaveCount(0);
  await expect(
    page.getByText("Für diese Ansicht liegen keine Anträge vor."),
  ).toHaveCount(0);
});
