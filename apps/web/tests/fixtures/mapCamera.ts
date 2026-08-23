import type { Page } from "@playwright/test";
import { demoNodes } from "../../src/lib/demo/demoData";

/**
 * Move the test camera to the canonical demo node when a test needs to
 * interact with markers. Production startup deliberately stays neutral.
 */
export async function centerDemoNode(page: Page, zoom = 14): Promise<void> {
  const { lon, lat } = demoNodes[0].location;
  await page.waitForFunction(
    () => (window as any).__TEST_MAP__ !== undefined,
    undefined,
    { timeout: 15000 },
  );
  await page.evaluate(
    ({ lon, lat, zoom }) => {
      const map = (window as any).__TEST_MAP__;
      map.jumpTo({ center: [lon, lat], zoom });
    },
    { lon, lat, zoom },
  );
}

/**
 * Put a search target clearly off-screen so direction-indicator tests assert
 * their own contract instead of depending on the application's initial view.
 */
export async function moveSearchTargetOffscreen(page: Page): Promise<void> {
  await centerDemoNode(page, 14);
}
