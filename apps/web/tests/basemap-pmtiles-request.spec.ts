import { expect, test } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test.describe("Basemap PMTiles Request E2E Verification", () => {
  test("client successfully requests the pmtiles artifact and style under local-sovereign mode", async ({
    page,
  }) => {
    await mockApiResponses(page);

    let pmtilesRequested = false;
    let styleRequested = false;

    // Provide a valid empty local style mock to simulate the Caddy router serving the artifact
    await page.route("**/local-basemap/style.json", (route) => {
      styleRequested = true;
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
          },
          layers: [],
        }),
      });
    });

    // Wait for the client to parse the pmtiles protocol and make range requests
    await page.route("**/local-basemap/basemap-hamburg.pmtiles", (route) => {
      pmtilesRequested = true;
      route.fulfill({
        status: 206, // Partial Content is expected for range requests
        body: "mocked-pmtiles-bytes",
      });
    });

    await page.goto("/map?t=" + Date.now());

    await expect.poll(() => styleRequested, {
      message: "Client MUST fetch the sovereign style.json",
      timeout: 5000,
    }).toBeTruthy();

    await expect.poll(() => pmtilesRequested, {
      message: "Client MUST initiate range requests for the local pmtiles artifact",
      timeout: 15000,
    }).toBeTruthy();
  });
});
