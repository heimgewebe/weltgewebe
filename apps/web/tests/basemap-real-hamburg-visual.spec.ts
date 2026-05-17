import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

/**
 * Visual Runtime Proof: Real Hamburg PMTiles via MapLibre
 *
 * Proves the full end-to-end pipeline:
 *   Browser → Weltgewebe App → MapLibre → pmtiles:// → /local-basemap/ →
 *   Vite dev-server middleware → build/basemap/basemap-hamburg-v0.1.0.pmtiles
 *
 * Two-part proof strategy:
 *
 *   1. SERVER RANGE CONTRACT:
 *      - Explicit direct Range request to /local-basemap/basemap-hamburg-v0.1.0.pmtiles
 *      - Must return HTTP 206 Partial Content
 *      - Must include Accept-Ranges: bytes and Content-Range headers
 *      - Proves the Vite middleware correctly delivers Range-capable files
 *
 *   2. BROWSER/MAPLIBRE VISUAL CONTRACT:
 *      - MapLibre canvas visible with non-zero dimensions
 *      - MapLibre isStyleLoaded() returns true (via window.__TEST_MAP__)
 *      - ≥1 local PMTiles request observed (proves MapLibre is using the artifact)
 *      - Zero requests to external tile providers
 *      - Proves the full browser-side pipeline works end-to-end
 *
 * Environment: Requires Vite dev or preview server with
 * local-basemap-serve middleware in vite.config.ts active (configureServer or
 * configurePreviewServer hooks).
 * Run with: PLAYWRIGHT_SKIP_WEBSERVER=1 PORT=5173
 *
 * /local-basemap/style.json and /local-basemap/*.pmtiles are NOT mocked here.
 * Only /api/** and /_app/version.json are mocked (no backend server needed).
 */

const REAL_PMTILES_FILENAME = "basemap-hamburg-v0.1.0.pmtiles";

const FORBIDDEN_REMOTE_PROVIDERS = [
  "api.maptiler.com",
  "tiles.mapbox.com",
  "api.mapbox.com",
  "basemaps.cartocdn.com",
  "tile.openstreetmap.org",
  "stamen-tiles",
  "services.arcgisonline.com",
  "maps.googleapis.com",
];

test.describe("Basemap Real Hamburg Visual Runtime Proof", () => {
  test(
    "loads real Hamburg PMTiles artifact via MapLibre with HTTP 206 Range delivery",
    { tag: "@proof" },
    async ({ page }, testInfo) => {
      const pmtilesRequests: Array<{
        url: string;
        method: string;
        rangeHeader: string | null;
      }> = [];
      const pmtilesResponses: Array<{
        url: string;
        status: number;
        acceptRanges: string | null;
        contentRange: string | null;
      }> = [];
      const remoteViolations: string[] = [];

      page.on("console", (msg) => {
        if (msg.type() === "error") {
          console.warn(`[browser-console-error] ${msg.text()}`);
        }
      });

      // Record PMTiles network events
      page.on("request", (req) => {
        const url = req.url();
        if (url.includes("/local-basemap/") && url.endsWith(".pmtiles")) {
          pmtilesRequests.push({
            url,
            method: req.method(),
            rangeHeader: req.headers()["range"] ?? null,
          });
        }
        for (const provider of FORBIDDEN_REMOTE_PROVIDERS) {
          if (url.includes(provider)) {
            remoteViolations.push(url);
          }
        }
      });

      page.on("response", (res) => {
        const url = res.url();
        if (url.includes("/local-basemap/") && url.endsWith(".pmtiles")) {
          pmtilesResponses.push({
            url,
            status: res.status(),
            acceptRanges: res.headers()["accept-ranges"] ?? null,
            contentRange: res.headers()["content-range"] ?? null,
          });
        }
      });

      // Mock /_app/version.json to suppress UpdateBanner overlay
      await page.route("**/_app/version.json", (route) => {
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ version: "proof" }),
        });
      });

      // Mock /api/** — no backend server needed
      await page.route("**/api/**", async (route) => {
        const url = route.request().url();
        if (url.includes("/api/nodes")) {
          return route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify([]),
          });
        }
        if (url.includes("/api/accounts")) {
          return route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify([]),
          });
        }
        if (url.includes("/api/edges")) {
          return route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify([]),
          });
        }
        if (url.includes("/api/health")) {
          return route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({ status: "Ready" }),
          });
        }
        if (url.includes("/api/auth/me") || url.includes("/api/me")) {
          return route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({ authenticated: false, role: "gast" }),
          });
        }
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({}),
        });
      });

      // Navigate to map — /local-basemap/style.json and *.pmtiles are NOT mocked
      await page.goto("/map?proof=1&t=" + Date.now());

      // Preflight: style endpoint must exist and point to the local Hamburg PMTiles alias
      const styleResponse = await page.request.get("/local-basemap/style.json");
      expect(
        styleResponse.status(),
        "Expected /local-basemap/style.json to return HTTP 200",
      ).toBe(200);
      const styleContentType = styleResponse.headers()["content-type"] ?? "";
      expect(
        styleContentType,
        "Expected /local-basemap/style.json to be application/json",
      ).toContain("application/json");
      const styleJson = (await styleResponse.json()) as {
        sources?: { basemap?: { url?: string } };
      };
      const styleBasemapUrl = styleJson.sources?.basemap?.url ?? "";
      expect(
        styleBasemapUrl,
        "Expected local basemap style to reference the Hamburg PMTiles file",
      ).toContain(REAL_PMTILES_FILENAME);
      expect(
        styleBasemapUrl,
        "Expected local basemap style source to use pmtiles protocol",
      ).toContain("pmtiles://");

      // === SERVER RANGE CONTRACT ===
      // Prove the Vite middleware can deliver Range requests correctly
      // This is independent of MapLibre's internal timing.
      const directRangeResponse = await page.request.get(
        `/local-basemap/${REAL_PMTILES_FILENAME}`,
        {
          headers: {
            Range: "bytes=0-511",
          },
        },
      );

      expect(
        directRangeResponse.status(),
        "Expected direct HTTP Range request to return 206 Partial Content",
      ).toBe(206);

      expect(
        directRangeResponse.headers()["accept-ranges"] ?? "",
        "Expected Accept-Ranges header for PMTiles delivery",
      ).toContain("bytes");

      expect(
        directRangeResponse.headers()["content-range"] ?? "",
        "Expected Content-Range header for PMTiles delivery",
      ).toContain("bytes 0-511/");

      // === BROWSER/MAPLIBRE VISUAL CONTRACT ===
      // Map container must be visible
      await expect(page.locator("#map")).toBeVisible({ timeout: 20000 });

      // MapLibre canvas must appear
      await expect(page.locator("#map canvas")).toBeVisible({ timeout: 25000 });

      // Wait for at least one PMTiles request (MapLibre fetches header bytes first)
      await expect
        .poll(() => pmtilesRequests.length > 0, {
          message: `Expected ≥1 request to /local-basemap/${REAL_PMTILES_FILENAME}`,
          timeout: 25000,
        })
        .toBe(true);

      // Wait for Range requests (PMTiles protocol always uses Range for tile data)
      await expect
        .poll(
          () => pmtilesRequests.filter((r) => r.rangeHeader !== null).length,
          {
            message: "Expected PMTiles Range requests to the real artifact",
            timeout: 15000,
          },
        )
        .toBeGreaterThan(0);

      // Verify HTTP 206 responses (observed from MapLibre's network activity)
      // Note: This is observed traffic and may vary depending on rendering timing.
      // The hard assertion on 206 is provided by the direct Range request above.
      const observedResponses206 = pmtilesResponses.filter(
        (r) => r.status === 206,
      );
      if (observedResponses206.length > 0) {
        console.log(
          `[MapLibre Range observation] Observed ${observedResponses206.length} HTTP 206 responses`,
        );
      }

      // No external tile providers must have been contacted
      expect(
        remoteViolations,
        `External basemap providers were contacted: ${remoteViolations.join(", ")}`,
      ).toHaveLength(0);

      // Verify canvas has non-trivial dimensions (MapLibre rendered something)
      const canvasDimensions = await page.evaluate(() => {
        const canvas = document.querySelector(
          "#map canvas",
        ) as HTMLCanvasElement | null;
        if (!canvas) return null;
        return {
          width: canvas.width,
          height: canvas.height,
          clientWidth: canvas.clientWidth,
          clientHeight: canvas.clientHeight,
        };
      });
      expect(
        canvasDimensions,
        "MapLibre WebGL canvas not found",
      ).not.toBeNull();
      expect(
        canvasDimensions!.clientWidth,
        "Canvas clientWidth must be > 0",
      ).toBeGreaterThan(0);
      expect(
        canvasDimensions!.clientHeight,
        "Canvas clientHeight must be > 0",
      ).toBeGreaterThan(0);

      // Check MapLibre isStyleLoaded() via window.__TEST_MAP__ hook
      await expect
        .poll(
          async () => {
            return await page.evaluate(() => {
              const map = (window as unknown as Record<string, unknown>)
                .__TEST_MAP__ as { isStyleLoaded?: () => boolean } | undefined;
              return map?.isStyleLoaded?.() ?? false;
            });
          },
          {
            message: "MapLibre isStyleLoaded() must resolve to true",
            timeout: 20000,
          },
        )
        .toBeTruthy();

      const styleLoaded = await page.evaluate(() => {
        const map = (window as unknown as Record<string, unknown>)
          .__TEST_MAP__ as { isStyleLoaded?: () => boolean } | undefined;
        return map?.isStyleLoaded?.() ?? false;
      });
      expect(styleLoaded, "MapLibre isStyleLoaded() must resolve to true").toBe(
        true,
      );

      // Screenshot as visual artifact
      await page.screenshot({
        path: testInfo.outputPath("screenshot.png"),
        fullPage: false,
      });

      // Build proof summary for guard consumption
      const proofSummary = {
        timestamp: new Date().toISOString(),
        verdict: "PROVEN",
        pmtiles_filename: REAL_PMTILES_FILENAME,

        // SERVER RANGE CONTRACT
        direct_range_status: directRangeResponse.status(),
        direct_range_accept_ranges:
          directRangeResponse.headers()["accept-ranges"] ?? null,
        direct_range_content_range:
          directRangeResponse.headers()["content-range"] ?? null,

        // BROWSER/MAPLIBRE VISUAL CONTRACT - OBSERVED
        pmtiles_requests_total: pmtilesRequests.length,
        pmtiles_range_requests_observed: pmtilesRequests.filter(
          (r) => r.rangeHeader !== null,
        ).length,
        pmtiles_206_responses_observed: pmtilesResponses.filter(
          (r) => r.status === 206,
        ).length,
        canvas_dimensions: canvasDimensions,
        style_loaded: styleLoaded,
        remote_violations: remoteViolations,

        // Artifacts
        screenshot: testInfo.outputPath("screenshot.png"),
        first_request: pmtilesRequests[0] ?? null,
        first_206_response:
          pmtilesResponses.find((r) => r.status === 206) ?? null,
      };

      console.log(
        "BASEMAP_PROOF_SUMMARY:",
        JSON.stringify(proofSummary, null, 2),
      );

      // Persist proof summary next to screenshot
      fs.writeFileSync(
        testInfo.outputPath("proof-summary.json"),
        JSON.stringify(proofSummary, null, 2),
      );

      // Write to build/proofs/basemap-visual/ for guard script access
      const buildProofDir = path.resolve(
        process.cwd(),
        "../../build/proofs/basemap-visual",
      );
      fs.mkdirSync(buildProofDir, { recursive: true });
      fs.writeFileSync(
        path.join(buildProofDir, "proof-summary.json"),
        JSON.stringify(proofSummary, null, 2),
      );
      fs.copyFileSync(
        testInfo.outputPath("screenshot.png"),
        path.join(buildProofDir, "screenshot.png"),
      );

      // All assertions passed → PROVEN
      // Hard assertion: direct Range request must return 206
      expect(
        proofSummary.direct_range_status,
        "Proof requires direct HTTP 206 response for Range delivery (Server Range Contract)",
      ).toBe(206);

      // Hard assertion: direct Range response must include Content-Range
      expect(
        proofSummary.direct_range_content_range,
        "Proof requires Content-Range header in Range response",
      ).toBeTruthy();

      // Hard assertion: direct Range response must include Accept-Ranges
      expect(
        proofSummary.direct_range_accept_ranges,
        "Proof requires Accept-Ranges header",
      ).toContain("bytes");

      // Hard assertion: MapLibre must have requested at least one local PMTiles file
      expect(
        proofSummary.pmtiles_requests_total,
        "Proof requires ≥1 local PMTiles request from MapLibre (Browser/MapLibre Visual Contract)",
      ).toBeGreaterThan(0);

      // Hard assertion: Canvas must have rendered
      expect(
        proofSummary.canvas_dimensions,
        "Proof requires MapLibre canvas to render",
      ).not.toBeNull();

      // Hard assertion: Style must be loaded
      expect(
        proofSummary.style_loaded,
        "Proof requires MapLibre style to be loaded",
      ).toBe(true);

      // Hard assertion: No external providers
      expect(
        proofSummary.remote_violations,
        "Proof requires zero external tile provider requests",
      ).toHaveLength(0);
    },
  );
});
