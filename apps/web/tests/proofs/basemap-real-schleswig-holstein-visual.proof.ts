import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { mockListResponse } from "../fixtures/mockApi";

/**
 * Visual Runtime Proof: real Schleswig-Holstein PMTiles via MapLibre.
 *
 * The proof moves the real MapLibre instance to Kiel and requires decoded as
 * well as visibly rendered features from the Schleswig-Holstein source. The
 * regional style, glyphs and PMTiles archive are served by the local-basemap
 * middleware; only application API calls are isolated with explicit mocks.
 */

const REGION = "schleswig-holstein";
const SOURCE_ID = "basemap-schleswig-holstein";
const PMTILES_FILENAME = "basemap-schleswig-holstein.pmtiles";
const KIEL_CENTER: [number, number] = [10.1228, 54.3233];
const REGION_LAYER_IDS = [
  "landcover-schleswig-holstein",
  "landuse-schleswig-holstein",
  "water-schleswig-holstein",
  "roads-schleswig-holstein",
  "buildings-schleswig-holstein",
  "place-labels-schleswig-holstein",
];
const SOURCE_LAYER_IDS = [
  "landcover",
  "landuse",
  "transportation",
  "water",
  "place",
];

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

type TestMap = {
  isStyleLoaded?: () => boolean;
  jumpTo?: (options: { center: [number, number]; zoom: number }) => void;
  resize?: () => void;
  triggerRepaint?: () => void;
  once?: (event: string, handler: () => void) => void;
  on?: (event: string, handler: (event: unknown) => void) => void;
  queryRenderedFeatures?: (options?: {
    layers?: string[];
  }) => Array<{ source?: string; layer?: { id?: string } }>;
  querySourceFeatures?: (
    sourceId: string,
    options?: { sourceLayer?: string },
  ) => Array<unknown>;
  isSourceLoaded?: (sourceId: string) => boolean;
  getCenter?: () => { lng: number; lat: number };
  getZoom?: () => number;
  getStyle?: () => {
    sources?: Record<string, unknown>;
    layers?: Array<{ id: string; source?: string }>;
  };
};

test.describe("Basemap Real Schleswig-Holstein Visual Runtime Proof", () => {
  test(
    "renders real Schleswig-Holstein PMTiles around Kiel with HTTP 206 Range delivery",
    { tag: "@proof" },
    async ({ page }, testInfo) => {
      const buildBasemapDir = path.resolve(
        process.cwd(),
        "../../build/basemap",
      );
      const aliasPath = path.join(buildBasemapDir, PMTILES_FILENAME);
      expect(
        fs.existsSync(aliasPath),
        `NOT_PROVEN: missing required published PMTiles alias ${aliasPath}`,
      ).toBe(true);

      const targetRequests: Array<{
        url: string;
        rangeHeader: string | null;
      }> = [];
      const targetResponses: Array<{
        url: string;
        status: number;
        contentRange: string | null;
      }> = [];
      const failedResponses: Array<{ url: string; status: number }> = [];
      const remoteViolations: string[] = [];
      const consoleErrors: string[] = [];
      const unexpectedApiRequests: string[] = [];

      page.on("console", (message) => {
        if (message.type() === "error") {
          consoleErrors.push(message.text());
        }
      });

      page.on("request", (request) => {
        const url = request.url();
        if (url.includes(`/local-basemap/${PMTILES_FILENAME}`)) {
          targetRequests.push({
            url,
            rangeHeader: request.headers()["range"] ?? null,
          });
        }
        for (const provider of FORBIDDEN_REMOTE_PROVIDERS) {
          if (url.includes(provider)) {
            remoteViolations.push(url);
          }
        }
      });

      page.on("response", (response) => {
        const url = response.url();
        const status = response.status();
        if (status >= 400) {
          failedResponses.push({ url, status });
        }
        if (url.includes(`/local-basemap/${PMTILES_FILENAME}`)) {
          targetResponses.push({
            url,
            status,
            contentRange: response.headers()["content-range"] ?? null,
          });
        }
      });

      await page.route("**/favicon.ico", (route) =>
        route.fulfill({ status: 204, body: "" }),
      );
      await page.route("**/_app/version.json", (route) =>
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ version: "proof" }),
        }),
      );
      await page.route("**/api/**", async (route) => {
        const url = new URL(route.request().url());
        const pathname = url.pathname;
        if (
          pathname === "/api/nodes" ||
          pathname.startsWith("/api/nodes/") ||
          pathname === "/api/accounts" ||
          pathname.startsWith("/api/accounts/") ||
          pathname === "/api/edges" ||
          pathname.startsWith("/api/edges/")
        ) {
          return route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify(mockListResponse(route.request().url(), [])),
          });
        }
        if (pathname === "/api/health" || pathname.startsWith("/api/health/")) {
          return route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({ status: "Ready" }),
          });
        }
        if (pathname === "/api/auth/me" || pathname === "/api/me") {
          return route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({ authenticated: false, role: "gast" }),
          });
        }
        const requestPathWithQuery = `${url.pathname}${url.search}`;
        unexpectedApiRequests.push(requestPathWithQuery);
        return route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({ error: requestPathWithQuery }),
        });
      });

      await page.goto(`/map?proof=1&region=${REGION}&t=${Date.now()}`);

      const styleResponse = await page.request.get(
        "/local-basemap/style.json?v=0.3.1",
      );
      expect(styleResponse.status()).toBe(200);
      expect(styleResponse.headers()["content-type"] ?? "").toContain(
        "application/json",
      );
      const styleJson = (await styleResponse.json()) as {
        metadata?: Record<string, string>;
        sources?: Record<string, { url?: string }>;
      };
      expect(styleJson.metadata?.["weltgewebe:version"]).toBe("0.3.1");
      expect(styleJson.sources?.[SOURCE_ID]?.url).toBe(
        `pmtiles://${PMTILES_FILENAME}`,
      );

      const directRangeResponse = await page.request.get(
        `/local-basemap/${PMTILES_FILENAME}`,
        { headers: { Range: "bytes=0-511" } },
      );
      expect(directRangeResponse.status()).toBe(206);
      expect(directRangeResponse.headers()["accept-ranges"] ?? "").toContain(
        "bytes",
      );
      expect(directRangeResponse.headers()["content-range"] ?? "").toContain(
        "bytes 0-511/",
      );
      expect(directRangeResponse.headers()["content-type"] ?? "").toContain(
        "application/octet-stream",
      );
      expect(
        Buffer.from(await directRangeResponse.body())
          .subarray(0, 7)
          .toString(),
      ).toBe("PMTiles");

      await expect(page.locator("#map")).toBeVisible({ timeout: 20_000 });
      await expect(page.locator("#map canvas")).toBeVisible({
        timeout: 25_000,
      });
      await expect
        .poll(
          () =>
            page.evaluate(() => {
              const map = (window as unknown as Record<string, unknown>)
                .__TEST_MAP__ as TestMap | undefined;
              return map?.isStyleLoaded?.() ?? false;
            }),
          {
            message: "MapLibre style must load before moving to Kiel",
            timeout: 20_000,
          },
        )
        .toBeTruthy();

      await page.evaluate(() => {
        const map = (window as unknown as Record<string, unknown>)
          .__TEST_MAP__ as TestMap | undefined;
        const errors: string[] = [];
        (window as unknown as Record<string, unknown>).__SH_MAP_ERRORS__ =
          errors;
        map?.on?.("error", (event: unknown) => {
          const candidate = event as {
            error?: { message?: string };
            message?: string;
          };
          errors.push(
            candidate.error?.message ??
              candidate.message ??
              JSON.stringify(event),
          );
        });
      });

      await page.evaluate(
        async ({ center }) => {
          const map = (window as unknown as Record<string, unknown>)
            .__TEST_MAP__ as TestMap | undefined;
          if (!map?.jumpTo || !map.once) {
            throw new Error(
              "MapLibre test hook does not expose jumpTo() and once()",
            );
          }
          await new Promise<void>((resolve, reject) => {
            const timer = window.setTimeout(
              () =>
                reject(new Error("MapLibre did not become idle around Kiel")),
              30_000,
            );
            map.once?.("idle", () => {
              window.clearTimeout(timer);
              resolve();
            });
            map.resize?.();
            map.jumpTo?.({ center, zoom: 12 });
            map.triggerRepaint?.();
          });
        },
        { center: KIEL_CENTER },
      );

      await expect
        .poll(
          () =>
            targetRequests.filter((request) =>
              request.rangeHeader?.startsWith("bytes="),
            ).length,
          {
            message: `Expected Range requests for ${PMTILES_FILENAME}`,
            timeout: 30_000,
          },
        )
        .toBeGreaterThan(0);

      await expect
        .poll(
          () =>
            targetResponses.filter((response) => response.status === 206)
              .length,
          {
            message: `Expected HTTP 206 responses for ${PMTILES_FILENAME}`,
            timeout: 30_000,
          },
        )
        .toBeGreaterThan(0);

      await expect
        .poll(
          () =>
            page.evaluate((sourceId) => {
              const map = (window as unknown as Record<string, unknown>)
                .__TEST_MAP__ as TestMap | undefined;
              return map?.isSourceLoaded?.(sourceId) ?? false;
            }, SOURCE_ID),
          {
            message: "Schleswig-Holstein vector source must finish loading",
            timeout: 30_000,
          },
        )
        .toBeTruthy();

      const readFeatureEvidence = () =>
        page.evaluate(
          ({ sourceId, layerIds, sourceLayerIds }) => {
            const map = (window as unknown as Record<string, unknown>)
              .__TEST_MAP__ as TestMap | undefined;
            const renderedFeatures =
              map?.queryRenderedFeatures?.({ layers: layerIds }) ?? [];
            const sourceFeatureCounts = Object.fromEntries(
              sourceLayerIds.map((sourceLayer) => [
                sourceLayer,
                map?.querySourceFeatures?.(sourceId, { sourceLayer })?.length ??
                  0,
              ]),
            );
            return {
              renderedFeatureCount: renderedFeatures.length,
              renderedFromExpectedSource: renderedFeatures.filter(
                (feature) => feature.source === sourceId,
              ).length,
              renderedLayerIds: Array.from(
                new Set(
                  renderedFeatures
                    .map((feature) => feature.layer?.id)
                    .filter((layerId): layerId is string => Boolean(layerId)),
                ),
              ),
              sourceFeatureCounts,
              sourceFeatureCount: Object.values(sourceFeatureCounts).reduce(
                (sum, count) => sum + count,
                0,
              ),
            };
          },
          {
            sourceId: SOURCE_ID,
            layerIds: REGION_LAYER_IDS,
            sourceLayerIds: SOURCE_LAYER_IDS,
          },
        );

      await expect
        .poll(
          async () => (await readFeatureEvidence()).renderedFromExpectedSource,
          {
            message:
              "Expected rendered features from the Schleswig-Holstein source around Kiel",
            timeout: 30_000,
          },
        )
        .toBeGreaterThan(0);

      await expect
        .poll(async () => (await readFeatureEvidence()).sourceFeatureCount, {
          message:
            "Expected decoded vector features from Schleswig-Holstein source-layers around Kiel",
          timeout: 30_000,
        })
        .toBeGreaterThan(0);

      const featureEvidence = await readFeatureEvidence();
      const mapDiagnostics = await page.evaluate(
        ({ sourceId }) => {
          const map = (window as unknown as Record<string, unknown>)
            .__TEST_MAP__ as TestMap | undefined;
          const style = map?.getStyle?.();
          return {
            center: map?.getCenter?.() ?? null,
            zoom: map?.getZoom?.() ?? null,
            sourceLoaded: map?.isSourceLoaded?.(sourceId) ?? false,
            styleHasSource: Boolean(style?.sources?.[sourceId]),
            mapErrors:
              ((window as unknown as Record<string, unknown>)
                .__SH_MAP_ERRORS__ as string[] | undefined) ?? [],
            styleRegionLayers:
              style?.layers
                ?.filter((layer) => layer.source === sourceId)
                .map((layer) => layer.id) ?? [],
          };
        },
        { sourceId: SOURCE_ID },
      );

      expect(mapDiagnostics.center?.lng).toBeCloseTo(KIEL_CENTER[0], 3);
      expect(mapDiagnostics.center?.lat).toBeCloseTo(KIEL_CENTER[1], 3);
      expect(mapDiagnostics.zoom).toBeCloseTo(12, 1);
      expect(mapDiagnostics.sourceLoaded).toBe(true);
      expect(mapDiagnostics.styleHasSource).toBe(true);
      expect(mapDiagnostics.styleRegionLayers).toEqual(
        expect.arrayContaining(REGION_LAYER_IDS),
      );
      expect(featureEvidence.renderedFromExpectedSource).toBeGreaterThan(0);
      expect(featureEvidence.renderedLayerIds).toEqual(
        expect.arrayContaining([
          "landcover-schleswig-holstein",
          "landuse-schleswig-holstein",
        ]),
      );
      expect(
        featureEvidence.sourceFeatureCounts.transportation,
      ).toBeGreaterThan(0);
      expect(featureEvidence.sourceFeatureCounts.landcover).toBeGreaterThan(0);
      expect(featureEvidence.sourceFeatureCounts.landuse).toBeGreaterThan(0);
      expect(featureEvidence.sourceFeatureCounts.water).toBeGreaterThan(0);
      expect(featureEvidence.sourceFeatureCounts.place).toBeGreaterThan(0);
      expect(mapDiagnostics.mapErrors).toHaveLength(0);
      expect(remoteViolations).toHaveLength(0);
      expect(unexpectedApiRequests).toHaveLength(0);
      expect(failedResponses).toHaveLength(0);
      expect(consoleErrors).toHaveLength(0);

      const screenshotPath = testInfo.outputPath("screenshot.png");
      await page.screenshot({ path: screenshotPath, fullPage: false });

      const proofSummary = {
        timestamp: new Date().toISOString(),
        verdict: "PROVEN",
        region: REGION,
        center: mapDiagnostics.center,
        zoom: mapDiagnostics.zoom,
        source_id: SOURCE_ID,
        source_loaded: mapDiagnostics.sourceLoaded,
        style_region_layers: mapDiagnostics.styleRegionLayers,
        pmtiles_filename: PMTILES_FILENAME,
        direct_range_status: directRangeResponse.status(),
        direct_range_content_range:
          directRangeResponse.headers()["content-range"] ?? null,
        direct_range_content_type:
          directRangeResponse.headers()["content-type"] ?? null,
        pmtiles_range_requests_observed: targetRequests.filter((request) =>
          request.rangeHeader?.startsWith("bytes="),
        ).length,
        pmtiles_206_responses_observed: targetResponses.filter(
          (response) => response.status === 206,
        ).length,
        rendered_feature_count: featureEvidence.renderedFeatureCount,
        rendered_from_expected_source:
          featureEvidence.renderedFromExpectedSource,
        rendered_layer_ids: featureEvidence.renderedLayerIds,
        decoded_source_feature_count: featureEvidence.sourceFeatureCount,
        decoded_source_feature_counts_by_layer:
          featureEvidence.sourceFeatureCounts,
        map_errors: mapDiagnostics.mapErrors,
        failed_responses: failedResponses,
        remote_violations: remoteViolations,
        unexpected_api_requests: unexpectedApiRequests,
        console_errors: consoleErrors,
      };
      const proofSummaryJson = JSON.stringify(proofSummary, null, 2);
      const testSummaryPath = testInfo.outputPath("proof-summary.json");
      fs.writeFileSync(testSummaryPath, proofSummaryJson);

      await testInfo.attach("schleswig-holstein-proof-summary", {
        body: Buffer.from(proofSummaryJson),
        contentType: "application/json",
      });
      await testInfo.attach("schleswig-holstein-screenshot", {
        path: screenshotPath,
        contentType: "image/png",
      });

      const buildProofDir = path.resolve(
        process.cwd(),
        "../../build/proofs/basemap-visual",
      );
      fs.mkdirSync(buildProofDir, { recursive: true });
      fs.writeFileSync(
        path.join(buildProofDir, "schleswig-holstein-proof-summary.json"),
        proofSummaryJson,
      );
      fs.copyFileSync(
        screenshotPath,
        path.join(buildProofDir, "schleswig-holstein-screenshot.png"),
      );

      console.log(
        "BASEMAP_SCHLESWIG_HOLSTEIN_PROOF_SUMMARY:",
        proofSummaryJson,
      );
    },
  );
});
