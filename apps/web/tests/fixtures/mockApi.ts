import type { Page } from "@playwright/test";
import {
  demoNodes,
  demoAccounts,
  demoEdges,
} from "../../src/lib/demo/demoData";

/**
 * Mock API responses for E2E tests.
 * This ensures tests work without a running backend API server.
 */

/**
 * Setup API mocking for a Playwright page.
 * Intercepts /api/** requests and returns demo data or empty responses.
 * This prevents ECONNREFUSED errors from the Vite proxy when backend is missing.
 */
export async function mockApiResponses(page: Page): Promise<void> {
  await page.route("**/api/**", async (route) => {
    const url = route.request().url();

    if (url.endsWith("/api/nodes")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(demoNodes),
      });
    }

    if (url.endsWith("/api/accounts")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(demoAccounts),
      });
    }

    if (url.endsWith("/api/edges")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(demoEdges),
      });
    }

    if (url.includes("/api/health")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "Ready" }),
      });
    }

    // Default: empty, no error objects
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({}),
    });
  });
}
