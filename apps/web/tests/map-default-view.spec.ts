import { test, expect } from "@playwright/test";

test("map centers on hammer park by default", async ({ page }) => {
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
  await page.waitForTimeout(2000);

  // 3. Map-Zentrum prüfen
  const center = await page.evaluate(() => {
    const map = (window as any).__TEST_MAP__;
    return map.getCenter();
  });

  // HAMMER_PARK_CENTER: lat: 53.5585, lon: 10.0580
  expect(center.lng).toBeCloseTo(10.058, 2);
  expect(center.lat).toBeCloseTo(53.5585, 2);
});
