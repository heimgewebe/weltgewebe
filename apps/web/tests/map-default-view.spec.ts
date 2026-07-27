import { test, expect } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test("guest map keeps the Hammer Park fallback", async ({ page }) => {
  await mockApiResponses(page);

  // 1. `/map` öffnen
  await page.goto("/map");

  // 2. warten bis Map geladen ist
  // We exposed window.__TEST_MAP__ on the window object
  await page.waitForFunction(
    () => (window as any).__TEST_MAP__ !== undefined,
    undefined,
    { timeout: 15000 },
  );

  // The fallback is now selected before MapLibre draws its first frame.
  await page.waitForFunction(
    () => {
      const map = (window as any).__TEST_MAP__;
      if (!map) return false;

      const center = map.getCenter();
      const targetLat = 53.5585;
      const targetLng = 10.058;
      const epsilon = 0.0005;

      return (
        Math.abs(center.lat - targetLat) < epsilon &&
        Math.abs(center.lng - targetLng) < epsilon
      );
    },
    undefined,
    { timeout: 15000 },
  );

  // 3. Map-Zentrum prüfen
  const center = await page.evaluate(() => {
    const map = (window as any).__TEST_MAP__;
    return map.getCenter();
  });

  // HAMMER_PARK_CENTER: lat: 53.5585, lon: 10.0580
  expect(center.lng).toBeCloseTo(10.058, 2);
  expect(center.lat).toBeCloseTo(53.5585, 2);
});

test("signed-in map starts on the own positioned Garnrolle", async ({
  page,
}) => {
  const ownAccountId = "7d97a42e-3704-4a33-a61f-0e0a6b4d65d8";
  await mockApiResponses(page, {
    auth: { authenticated: true, account_id: ownAccountId, role: "weber" },
  });

  await page.goto("/map");
  await page.waitForFunction(
    () => (window as any).__TEST_MAP__ !== undefined,
    undefined,
    { timeout: 15000 },
  );

  await page.waitForFunction(
    () => {
      const map = (window as any).__TEST_MAP__;
      if (!map) return false;
      const center = map.getCenter();
      return (
        Math.abs(center.lng - 10.0629844) < 0.0005 &&
        Math.abs(center.lat - 53.5604148) < 0.0005 &&
        map.getZoom() >= 14
      );
    },
    undefined,
    { timeout: 15000 },
  );

  await expect(
    page.getByTestId(`marker-garnrolle-${ownAccountId}`),
  ).toBeVisible();
  await expect(page.getByTestId("context-panel")).toHaveCount(0);
});

test("delayed authentication recenters once without blocking public map startup", async ({
  page,
}) => {
  const ownAccountId = "7d97a42e-3704-4a33-a61f-0e0a6b4d65d8";
  await mockApiResponses(page);
  let releaseAuth!: () => void;
  const authGate = new Promise<void>((resolve) => {
    releaseAuth = resolve;
  });
  await page.route("**/api/auth/me", async (route) => {
    await authGate;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        authenticated: true,
        account_id: ownAccountId,
        role: "weber",
      }),
    });
  });
  await page.goto("/map");
  await page.waitForFunction(
    () => (window as any).__TEST_MAP__ !== undefined,
    undefined,
    { timeout: 15000 },
  );
  const initialCenter = await page.evaluate(() => {
    return (window as any).__TEST_MAP__.getCenter();
  });
  expect(initialCenter.lng).toBeCloseTo(10.058, 2);
  expect(initialCenter.lat).toBeCloseTo(53.5585, 2);
  releaseAuth();
  await page.waitForFunction(
    () => {
      const map = (window as any).__TEST_MAP__;
      if (!map) return false;
      const center = map.getCenter();
      return (
        Math.abs(center.lng - 10.0629844) < 0.0005 &&
        Math.abs(center.lat - 53.5604148) < 0.0005 &&
        map.getZoom() >= 14
      );
    },
    undefined,
    { timeout: 15000 },
  );
});
