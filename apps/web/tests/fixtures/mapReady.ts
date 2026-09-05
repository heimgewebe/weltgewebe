import { expect, type Locator, type Page } from "@playwright/test";

export const NODE_MARKER_SELECTOR = '.map-marker[data-marker-category="node"]';
export const ACCOUNT_MARKER_SELECTOR =
  '.map-marker[data-marker-category="account"]';

export async function waitForMapReady(page: Page): Promise<void> {
  await expect(page.locator(".loading-overlay")).toHaveCount(0, {
    timeout: 15_000,
  });
  await expect(page.locator("#map")).not.toHaveClass(/map-loading/, {
    timeout: 15_000,
  });
}

async function waitForMarker(page: Page, selector: string): Promise<Locator> {
  await waitForMapReady(page);
  const marker = page.locator(selector).first();
  await expect(marker).toBeVisible({ timeout: 10_000 });
  return marker;
}

export async function waitForNodeMarker(page: Page): Promise<Locator> {
  return waitForMarker(page, NODE_MARKER_SELECTOR);
}

export async function waitForAccountMarker(page: Page): Promise<Locator> {
  return waitForMarker(page, ACCOUNT_MARKER_SELECTOR);
}
