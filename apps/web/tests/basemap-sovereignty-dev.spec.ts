import { expect, test } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

// This test proves that the application requests the local sovereign style
// and renders without ANY external CDN dependencies in the local-sovereign mode.
// It uses a strict deny-by-default routing logic to ensure E2E-Test-Build sovereignty without fallbacks.
test.describe("Basemap Sovereignty Verification (E2E-Test-Build Environment)", () => {
  test("client successfully fetches local style and map isStyleLoaded() resolves without external CDN dependencies", async ({
    page,
  }) => {
    // Setup mock API routing for the auth endpoints to allow the app to load
    await mockApiResponses(page);

    // Track all network requests
    const requestedUrls: string[] = [];
    let externalDependencyDetected = false;

    // Strict allowlist for dev/test context
    const allowedHosts = [
      "localhost",
      "127.0.0.1",
      "[::1]", // some IPv6 local loops
    ];

    page.on("request", (req) => {
      const url = req.url();
      requestedUrls.push(url);
    });

    // 1. ADD CATCH-ALL BLOCKER FIRST (evaluated last by Playwright)
    // DENY BY DEFAULT logic for requests to ensure true local sovereignty
    await page.route("**/*", async (route) => {
      try {
        const url = route.request().url();

        // Always allow data/blob/about
        if (
          url.startsWith("data:") ||
          url.startsWith("blob:") ||
          url.startsWith("about:")
        ) {
          return route.continue();
        }

        const routeUrlObj = new URL(url);

        // If the host is not explicitly in our allowed list, we block it to prove sovereignty.
        if (!allowedHosts.includes(routeUrlObj.hostname)) {
          externalDependencyDetected = true;
          console.warn(
            "External dependency BLOCKED by deny-by-default policy:",
            url,
          );
          return route.abort();
        }

        return route.continue();
      } catch {
        route.continue();
      }
    });

    // 2. ADD SPECIFIC MOCK LAST (evaluated first by Playwright)
    // Provide a valid empty local style mock to simulate the Caddy router serving the artifact
    await page.route("**/local-basemap/style.json", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          version: 8,
          sources: {},
          layers: [],
        }),
      });
    });

    const styleResponsePromise = page.waitForResponse((response) =>
      response.url().includes("/local-basemap/style.json"),
    );

    // We navigate to the map.
    await page.goto("/map?t=" + Date.now());

    // 1. Wait for style response to come back HTTP 200/OK
    const styleResponse = await styleResponsePromise;
    expect(
      styleResponse.ok(),
      "style.json MUST be successfully fetched",
    ).toBeTruthy();

    // 2. Wait until map container is present and loading spinner is gone
    await expect(page.locator("#map")).toBeVisible();
    await expect(page.locator(".spinner")).toHaveCount(0, { timeout: 15000 });

    // 3. Verify MapLibre explicitly registers the style as loaded via the window.__TEST_MAP__ hook
    await expect
      .poll(
        async () => {
          return await page.evaluate(() => {
            const map = (window as any).__TEST_MAP__;
            if (map && typeof map.isStyleLoaded === "function") {
              return map.isStyleLoaded();
            }
            return false;
          });
        },
        {
          message:
            "MapLibre isStyleLoaded() MUST resolve to true using the local style",
          timeout: 10000,
        },
      )
      .toBeTruthy();

    // 4. Verify that NO external domains were allowed or contacted.
    expect(
      externalDependencyDetected,
      "External map dependency detected during load. Dev/test sovereignty check failed.",
    ).toBe(false);
  });
});
