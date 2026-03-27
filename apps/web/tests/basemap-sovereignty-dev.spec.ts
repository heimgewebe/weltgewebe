import { expect, test } from "@playwright/test";

// This test proves that the application requests the local sovereign style
// and renders without ANY external CDN dependencies in the local-sovereign mode.
// It explicitly intercepts and ABORTS any requests to external domains
// (like cartocdn, mapbox, unpkg) to ensure dev/test sovereignty without fallbacks.
test.describe("Basemap Sovereignty Verification (Dev/Test Environment)", () => {
  test("client successfully requests local style path and renders without external CDN dependencies", async ({
    page,
  }) => {
    // Track all network requests
    const requestedUrls: string[] = [];
    let externalDependencyDetected = false;

    page.on("request", (req) => {
      const url = req.url();
      requestedUrls.push(url);

      try {
        const urlObj = new URL(url);
        const isLocalHost =
          urlObj.hostname === "localhost" || urlObj.hostname === "127.0.0.1";

        // Exclude data URIs, blob URIs, and our local dev server
        if (
          !isLocalHost &&
          !url.startsWith("data:") &&
          !url.startsWith("blob:") &&
          !urlObj.hostname.includes("localhost")
        ) {
          externalDependencyDetected = true;
          console.warn("External dependency detected:", url);
        }
      } catch {
        // ignore invalid URLs
      }
    });

    // Abort external tile/style providers to ensure we don't accidentally fall back
    await page.route("**/*", (route) => {
      try {
        const routeUrlObj = new URL(route.request().url());
        if (
          routeUrlObj.hostname === "cartocdn.com" ||
          routeUrlObj.hostname.endsWith(".cartocdn.com") ||
          routeUrlObj.hostname === "mapbox.com" ||
          routeUrlObj.hostname.endsWith(".mapbox.com") ||
          routeUrlObj.hostname.includes("maptiles")
        ) {
          route.abort();
        } else {
          route.continue();
        }
      } catch {
        route.continue();
      }
    });

    // We navigate to the map. The Vite server and resolveBasemapMode will
    // automatically default to 'local-sovereign' during testing because MODE is 'test'.
    // We append a timestamp to avoid any browser caching of the HTML.
    await page.goto("/map?t=" + Date.now());

    // Wait until map container is present and loading spinner is gone
    await expect(page.locator("#map")).toBeVisible();
    await expect(page.locator(".spinner")).toHaveCount(0, { timeout: 15000 });

    // Validate that the client actually attempted to fetch the sovereign style.json:
    await expect
      .poll(
        () =>
          requestedUrls.some((url) =>
            url.includes("/local-basemap/style.json"),
          ),
        {
          message:
            "Client MUST request the local sovereign style.json from the dev server",
          timeout: 5000,
        },
      )
      .toBeTruthy();

    // Verify that NO external domains were contacted during the map load process.
    // This proves dev/test sovereignty (no external CDN dependencies during browser run).
    expect(
      externalDependencyDetected,
      "External map dependency detected during load. Dev/test sovereignty check failed.",
    ).toBe(false);
  });
});
