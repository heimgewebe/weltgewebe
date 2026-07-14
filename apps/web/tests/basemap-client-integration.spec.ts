import { expect, test } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test.describe("Basemap Client Integration (local-sovereign)", () => {
  test("client requests local style and PMTiles artifact in test context (mocked)", async ({
    page,
  }) => {
    // Setup generic mock routing
    await mockApiResponses(page);

    // Override local-basemap/style.json for this specific test
    // NOTE: This intentionally mocks the network path to verify client-side behavior
    // (MapLibre config and PMTiles protocol loading), not real Edge-routing delivery.
    await page.route("**/local-basemap/style.json*", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          version: 8,
          sources: {
            basemap: {
              type: "vector",
              url: "pmtiles://basemap-hamburg.pmtiles",
            },
            "basemap-schleswig-holstein": {
              type: "vector",
              url: "pmtiles://basemap-schleswig-holstein.pmtiles",
            },
          },
          layers: [
            {
              id: "hamburg-water",
              type: "fill",
              source: "basemap",
              "source-layer": "water",
            },
            {
              id: "schleswig-holstein-water",
              type: "fill",
              source: "basemap-schleswig-holstein",
              "source-layer": "water",
            },
          ],
        }),
      });
    });

    // Mock PMTiles requests locally to prove the PMTiles integration requests the artifact
    await page.route("**/local-basemap/*.pmtiles", async (route) => {
      // PMTiles protocol requests bytes via Range headers
      const req = route.request();
      const method = req.method();

      const headers = {
        "Accept-Ranges": "bytes",
        "Content-Range": "bytes 0-16383/512000", // fake minimal metadata chunk
        "Content-Length": "16384",
        "Content-Type": "application/octet-stream",
      };

      if (method === "GET") {
        await route.fulfill({
          status: 206,
          headers,
          // Supply a real 16KB byte buffer to satisfy the Content-Length contract
          body: Buffer.alloc(16384),
        });
      } else if (method === "HEAD") {
        await route.fulfill({
          status: 206,
          headers,
          // HEAD expects no body
          body: "",
        });
      } else {
        await route.fulfill({ status: 200 });
      }
    });

    // Track network requests to confirm what MapLibre actually requests
    // and whether PMTiles correctly issues Range headers.
    const requestedUrls: string[] = [];
    const pmtilesRangeRegions = new Set<string>();

    page.on("request", (req) => {
      const url = req.url();
      requestedUrls.push(url);

      const regionalArtifact = [
        "basemap-hamburg.pmtiles",
        "basemap-schleswig-holstein.pmtiles",
      ].find((artifact) => url.includes(`/local-basemap/${artifact}`));
      if (regionalArtifact) {
        // PMTiles must request partial content via HTTP Range header
        const reqHeaders = req.headers();
        if (reqHeaders["range"]?.startsWith("bytes=")) {
          pmtilesRangeRegions.add(regionalArtifact);
        }
      }
    });

    // We navigate to the map. The Vite server and resolveBasemapMode will
    // automatically default to 'local-sovereign' during testing because MODE is 'test'.
    await page.goto("/map");

    // Wait until map container is present and loading spinner is gone
    await expect(page.locator("#map")).toBeVisible();
    await expect(page.locator(".spinner")).toHaveCount(0, { timeout: 15000 });

    // Use expect.poll to wait for asynchronous MapLibre background requests to settle
    // and validate that the client actually attempted to fetch the sovereign resources:
    await expect
      .poll(
        () =>
          requestedUrls.some((url) =>
            url.includes("/local-basemap/style.json"),
          ),
        {
          message: "Client should request the local sovereign style.json",
          timeout: 5000,
        },
      )
      .toBeTruthy();

    // Both regional PMTiles sources must be resolved to local HTTP requests.
    for (const artifact of [
      "basemap-hamburg.pmtiles",
      "basemap-schleswig-holstein.pmtiles",
    ]) {
      await expect
        .poll(
          () =>
            requestedUrls.some((url) =>
              url.includes(`/local-basemap/${artifact}`),
            ),
          {
            message: `Client should request local regional artifact ${artifact}`,
            timeout: 5000,
          },
        )
        .toBeTruthy();
    }

    // Final semantic validation: both sources behave like PMTiles clients and
    // request byte slices rather than fetching opaque whole files.
    await expect
      .poll(() => pmtilesRangeRegions.size, {
        message: "Both regional PMTiles clients must issue Range headers",
        timeout: 5000,
      })
      .toBe(2);
  });
});
