import { test, expect, type Page, type Route } from "@playwright/test";

type AuthState = {
  authenticated: boolean;
  account_id?: string;
  role: string;
};

type DeviceInfo = {
  device_id: string;
  created_at: string;
  last_active: string;
  current: boolean;
};

interface MockOptions {
  initial: AuthState;
  devices?: DeviceInfo[];
  logoutAllResponse?: { status: number; body: unknown };
  stepUpRequestStatus?: number;
}

async function setupAuthMocks(page: Page, opts: MockOptions): Promise<void> {
  let authState: AuthState = opts.initial;
  const devices = opts.devices ?? [];
  const logoutAllResponse = opts.logoutAllResponse ?? {
    status: 403,
    body: {
      error: "STEP_UP_REQUIRED",
      challenge_id: "challenge-123",
    },
  };
  const stepUpRequestStatus = opts.stepUpRequestStatus ?? 200;

  // Pin a stable build version mock so the update banner does not appear.
  await page.route("**/_app/version.json", (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ version: "test-bundle" }),
    }),
  );

  await page.route("**/api/auth/me", (route: Route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(authState),
    });
  });

  await page.route("**/api/auth/devices", (route: Route) => {
    if (!authState.authenticated) {
      route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ error: "UNAUTHORIZED" }),
      });
      return;
    }
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(devices),
    });
  });

  await page.route("**/api/auth/logout", (route: Route) => {
    authState = { authenticated: false, role: "gast" };
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({}),
    });
  });

  await page.route("**/api/auth/logout-all", (route: Route) => {
    route.fulfill({
      status: logoutAllResponse.status,
      contentType: "application/json",
      body: JSON.stringify(logoutAllResponse.body),
    });
  });

  await page.route("**/api/auth/step-up/magic-link/request", (route: Route) => {
    route.fulfill({
      status: stepUpRequestStatus,
      contentType: "application/json",
      body: JSON.stringify({}),
    });
  });
}

test.describe("Settings — AccountSection", () => {
  test("shows login prompt when unauthenticated", async ({ page }) => {
    await setupAuthMocks(page, {
      initial: { authenticated: false, role: "gast" },
    });

    await page.goto("/settings");

    const section = page.locator('[data-testid="account-section"]');
    await expect(section).toBeVisible();
    await expect(
      section.locator('[data-testid="account-section-anonymous"]'),
    ).toBeVisible();
    await expect(section.locator('a[href="/login"]')).toBeVisible();
    await expect(
      section.locator('[data-testid="account-section-status"]'),
    ).toHaveCount(0);
  });

  test("shows account status, devices and logout when authenticated", async ({
    page,
  }) => {
    await setupAuthMocks(page, {
      initial: {
        authenticated: true,
        account_id: "acc-1",
        role: "weber",
      },
      devices: [
        {
          device_id: "device-current-abcdef1234",
          created_at: "2026-04-01T12:00:00Z",
          last_active: "2026-05-08T08:30:00Z",
          current: true,
        },
        {
          device_id: "device-other-987654321",
          created_at: "2026-03-12T07:00:00Z",
          last_active: "2026-04-25T17:15:00Z",
          current: false,
        },
      ],
    });

    await page.goto("/settings");

    const section = page.locator('[data-testid="account-section"]');
    await expect(
      section.locator('[data-testid="account-section-account-id"]'),
    ).toHaveText("acc-1");
    await expect(
      section.locator('[data-testid="account-section-role"]'),
    ).toHaveText("weber");

    const deviceItems = section.locator(
      '[data-testid="account-section-device"]',
    );
    await expect(deviceItems).toHaveCount(2);
    await expect(
      section.locator('[data-testid="account-section-device-current"]'),
    ).toHaveCount(1);
    await expect(deviceItems.first()).toHaveAttribute(
      "data-device-current",
      "true",
    );
  });

  test("logout-all surfaces step-up confirmation message", async ({ page }) => {
    await setupAuthMocks(page, {
      initial: {
        authenticated: true,
        account_id: "acc-2",
        role: "gast",
      },
      devices: [
        {
          device_id: "device-only",
          created_at: "2026-04-01T12:00:00Z",
          last_active: "2026-05-08T08:30:00Z",
          current: true,
        },
      ],
    });

    await page.goto("/settings");

    const section = page.locator('[data-testid="account-section"]');
    await section.locator('[data-testid="account-section-logout-all"]').click();

    await expect(
      section.locator('[data-testid="account-section-action-message"]'),
    ).toContainText("Bestätigungslink");
  });

  test("logout button removes authenticated section", async ({ page }) => {
    await setupAuthMocks(page, {
      initial: {
        authenticated: true,
        account_id: "acc-3",
        role: "gast",
      },
    });

    await page.goto("/settings");

    const section = page.locator('[data-testid="account-section"]');
    await expect(
      section.locator('[data-testid="account-section-status"]'),
    ).toBeVisible();

    await section.locator('[data-testid="account-section-logout"]').click();

    await expect(
      section.locator('[data-testid="account-section-anonymous"]'),
    ).toBeVisible();
  });

  test("passkey entry stub is present and disabled", async ({ page }) => {
    await setupAuthMocks(page, {
      initial: {
        authenticated: true,
        account_id: "acc-4",
        role: "gast",
      },
    });

    await page.goto("/settings");

    const cta = page.locator('[data-testid="account-section-passkey-cta"]');
    await expect(cta).toBeVisible();
    await expect(cta).toBeDisabled();
  });

  test("regression: devices fetched exactly once on initial load", async ({
    page,
  }) => {
    let devicesCalls = 0;
    await page.route("**/api/auth/devices", (route: Route) => {
      devicesCalls += 1;
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            device_id: "device-1",
            created_at: "2026-04-01T12:00:00Z",
            last_active: "2026-05-08T08:30:00Z",
            current: true,
          },
        ]),
      });
    });

    await setupAuthMocks(page, {
      initial: {
        authenticated: true,
        account_id: "acc-5",
        role: "weber",
      },
      devices: [
        {
          device_id: "device-1",
          created_at: "2026-04-01T12:00:00Z",
          last_active: "2026-05-08T08:30:00Z",
          current: true,
        },
      ],
    });

    await page.goto("/settings");
    await page.locator('[data-testid="account-section"]').waitFor();

    expect(devicesCalls).toBe(1);
  });

  test("logout-all error when step-up request fails", async ({ page }) => {
    await setupAuthMocks(page, {
      initial: {
        authenticated: true,
        account_id: "acc-6",
        role: "gast",
      },
      devices: [
        {
          device_id: "device-fail",
          created_at: "2026-04-01T12:00:00Z",
          last_active: "2026-05-08T08:30:00Z",
          current: true,
        },
      ],
      stepUpRequestStatus: 500,
    });

    await page.goto("/settings");

    const section = page.locator('[data-testid="account-section"]');
    await section.locator('[data-testid="account-section-logout-all"]').click();

    const message = section.locator(
      '[data-testid="account-section-action-message"]',
    );
    await expect(message).toBeVisible();
    await expect(message).toContainText("konnte nicht versendet werden");
  });
});
