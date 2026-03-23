import { expect, test } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test.describe("Basemap Client Integration (local-sovereign)", () => {
  test("client requests local style and PMTiles artifact in test context (mocked)", async ({
    page,
  }) => {
    // Setup full mock routing including local-basemap/style.json and *.pmtiles.
    // NOTE: This intentionally mocks the network path to verify client-side behavior
    // (MapLibre config and PMTiles protocol loading), not real Edge-routing delivery.
    await mockApiResponses(page);

    // Track network requests to confirm what MapLibre actually requests
    const requestedUrls: string[] = [];
    page.on("request", (req) => {
      requestedUrls.push(req.url());
    });

    // We navigate to the map. The Vite server and resolveBasemapMode will
    // automatically default to 'local-sovereign' during testing because MODE is 'test'.
    await page.goto("/map");

    // Wait until map container is present and loading spinner is gone
    await expect(page.locator("#map")).toBeVisible();
    await expect(page.locator(".spinner")).toHaveCount(0, { timeout: 15000 });

    // Validate that the client actually attempted to fetch the sovereign resources:
    const fetchedStyle = requestedUrls.some((url) =>
      url.includes("/local-basemap/style.json"),
    );
    const fetchedPmtiles = requestedUrls.some((url) =>
      url.includes("/local-basemap/basemap-hamburg.pmtiles"),
    );

    expect(fetchedStyle).toBeTruthy();

    // PMTiles protocol fetch check. If MapLibre + pmtiles protocol is correctly linked,
    // the source URL pmtiles://basemap-hamburg.pmtiles should be transformed to a real
    // fetch against /local-basemap/basemap-hamburg.pmtiles.
    expect(fetchedPmtiles).toBeTruthy();
  });
});
