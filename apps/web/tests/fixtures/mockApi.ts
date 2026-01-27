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
  // Track auth state in the mock
  let isAuthenticated = false;
  let currentAccountId: string | null = null;

  await page.route("**/api/**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();

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

    // Handle auth/login
    if (url.includes("/api/auth/login") && method === "POST") {
      try {
        const postData = route.request().postDataJSON();
        currentAccountId = postData?.account_id || null;
        isAuthenticated = true;
        return route.fulfill({
          status: 200,
          headers: {
            "Set-Cookie":
              "gewebe_session=mock_session; Path=/; HttpOnly; SameSite=Strict; Secure",
          },
        });
      } catch {
        return route.fulfill({ status: 400 });
      }
    }

    // Handle auth/logout
    if (url.includes("/api/auth/logout") && method === "POST") {
      isAuthenticated = false;
      currentAccountId = null;
      return route.fulfill({
        status: 200,
        headers: {
          "Set-Cookie":
            "gewebe_session=; Path=/; HttpOnly; SameSite=Strict; Secure; Max-Age=0",
        },
      });
    }

    // Handle auth/me
    if (url.includes("/api/auth/me")) {
      if (isAuthenticated && currentAccountId) {
        // Demo accounts don't have explicit roles, default to "gast"
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            authenticated: true,
            account_id: currentAccountId,
            role: "gast",
          }),
        });
      } else {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            authenticated: false,
            role: "gast",
          }),
        });
      }
    }

    // Default: empty, no error objects
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({}),
    });
  });
}
