import { expect, test } from "@playwright/test";

// This test proves that the application can render the map without ANY
// external map styling dependencies when using the local-sovereign mode.
// It explicitly intercepts and ABORTS any requests to external domains
// (like cartocdn, mapbox, unpkg) to ensure true sovereignty.
test.describe("Basemap Sovereign End-to-End Verification", () => {
  test("client successfully requests and renders local artifacts without external dependencies", async ({
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
          routeUrlObj.hostname.endsWith("cartocdn.com") ||
          routeUrlObj.hostname.endsWith("mapbox.com") ||
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
    // This is the true proof of "Sovereignty" (no CDN dependencies).
    expect(
      externalDependencyDetected,
      "External map dependency detected during load. True sovereignty violated.",
    ).toBe(false);
  });
});
