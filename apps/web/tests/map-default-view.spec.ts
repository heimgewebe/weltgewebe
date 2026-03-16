import { test, expect } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test("map centers on hammer park by default", async ({ page }) => {
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
  await page.waitForFunction(
    () => (window as any).__TEST_MAP__.loaded(),
    undefined,
    { timeout: 15000 },
  );

  // Let map do the initial flyTo transition
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
