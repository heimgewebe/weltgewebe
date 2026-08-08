import { expect, test } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test.describe("Basemap Client Integration (local-sovereign)", () => {
  test("client requests local style and PMTiles artifact in test context (mocked)", async ({
    page,
  }) => {
    // Setup generic mock routing
    await mockApiResponses(page);

    // Override the default nationwide Germany style for this specific test
    // NOTE: This intentionally mocks the network path to verify client-side behavior
    // (MapLibre config and PMTiles protocol loading), not real Edge-routing delivery.
    await page.route("**/local-basemap/style-germany.json*", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          version: 8,
          sources: {
            "basemap-germany": {
              type: "vector",
              url: "pmtiles://basemap-germany.pmtiles",
            },
          },
          layers: [
            {
              id: "germany-water",
              type: "fill",
              source: "basemap-germany",
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
    const pmtilesRangeArtifacts = new Set<string>();

    page.on("request", (req) => {
      const url = req.url();
      requestedUrls.push(url);

      const germanyArtifact = "basemap-germany.pmtiles";
      if (url.includes(`/local-basemap/${germanyArtifact}`)) {
        // PMTiles must request partial content via HTTP Range header.
        const reqHeaders = req.headers();
        if (reqHeaders["range"]?.startsWith("bytes=")) {
          pmtilesRangeArtifacts.add(germanyArtifact);
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
            url.includes("/local-basemap/style-germany.json"),
          ),
        {
          message:
            "Client should request the nationwide Germany sovereign style",
          timeout: 5000,
        },
      )
      .toBeTruthy();

    // The nationwide Germany PMTiles source must resolve to a local HTTP request.
    const germanyArtifact = "basemap-germany.pmtiles";
    await expect
      .poll(
        () =>
          requestedUrls.some((url) =>
            url.includes(`/local-basemap/${germanyArtifact}`),
          ),
        {
          message: `Client should request nationwide Germany artifact ${germanyArtifact}`,
          timeout: 5000,
        },
      )
      .toBeTruthy();

    // Final semantic validation: the PMTiles client requests byte slices rather
    // than fetching the opaque whole Germany artifact.
    await expect
      .poll(() => pmtilesRangeArtifacts.size, {
        message: "Germany PMTiles client must issue Range headers",
        timeout: 5000,
      })
      .toBe(1);
  });
});
