import { expect, test } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

// Epistemischer Vertrag:
// Dieser Test beweist AUSSCHLIESSLICH, dass der MapLibre-Client (im Browser)
// erfolgreich das `pmtiles://`-Protokoll verarbeitet und daraufhin
// HTTP GET-Anfragen mit `Range`-Headern an den konfigurierten lokalen Endpunkt absetzt.
//
// Er beweist NICHT:
// - die echte Produktionsroute im Caddy-Webserver
// - die physische Existenz des echten `.pmtiles`-Artefakts auf dem Server
// - das erfolgreiche Dekodieren realer Tile-Bytes in MapLibre
//
// Die Server-Antworten (Style und PMTiles-Bytes) sind in diesem Kontext hart gemockt.
test.describe("Basemap Client PMTiles Request Verification (Testbuild Mocked)", () => {
  test("client successfully requests the pmtiles artifact with a Range header under local-sovereign mode", async ({
    page,
  }) => {
    await mockApiResponses(page);

    let pmtilesRequested = false;
    let styleRequested = false;
    let capturedRangeHeader: string | null = null;

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
      const headers = route.request().headers();
      if (headers["range"]) {
        capturedRangeHeader = headers["range"];
      }

      route.fulfill({
        status: 206, // Partial Content is expected for range requests
        body: "mocked-pmtiles-bytes",
      });
    });

    await page.goto("/map?t=" + Date.now());

    await expect
      .poll(() => styleRequested, {
        message: "Client MUST fetch the sovereign style.json",
        timeout: 5000,
      })
      .toBeTruthy();

    await expect
      .poll(() => pmtilesRequested, {
        message:
          "Client MUST initiate requests for the local pmtiles artifact path",
        timeout: 15000,
      })
      .toBeTruthy();

    // The core proof of this test: MapLibre's PMTiles integration is actively firing byte-range requests
    expect(
      capturedRangeHeader,
      "Client MUST send an HTTP Range header when requesting the PMTiles artifact",
    ).not.toBeNull();
    expect(capturedRangeHeader).toMatch(/^bytes=\d+-\d*$/);
  });
});
