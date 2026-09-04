import { expect, test, type Page, type Route } from "@playwright/test";
import { performance } from "node:perf_hooks";
import { readFileSync } from "node:fs";
import { mockApiResponses } from "../fixtures/mockApi";
import {
  assertExactGitCheckout,
  resolveExactSourceRevision,
} from "../../scripts/web-runtime-evidence.mjs";
// The evidence builder stays Node-native JavaScript so its contract can be
// executed directly by node --test. Keep the typed browser seam explicit here.
// @ts-expect-error The sibling .mjs module is runtime-validated by its Node tests.
import * as mapCardinalityEvidenceRuntime from "../../scripts/map-cardinality-evidence.mjs";

const {
  MAP_CARDINALITY_BUDGETS,
  MAP_CARDINALITY_PAGE_SIZE,
  buildMapCardinalityEvidence,
  writeMapCardinalityEvidence,
} = mapCardinalityEvidenceRuntime as unknown as {
  MAP_CARDINALITY_BUDGETS: Record<
    1000 | 10000 | 100000,
    {
      readiness_ms: number;
      interaction_to_next_paint_ms: number;
      max_dom_markers: number;
      max_api_response_bytes: number;
    }
  >;
  MAP_CARDINALITY_PAGE_SIZE: number;
  buildMapCardinalityEvidence: (input: {
    sourceRevision: string;
    generatedAt: string;
    browser: { name: string; version: string; headless: boolean };
    samples: CardinalitySample[];
  }) => Record<string, unknown>;
  writeMapCardinalityEvidence: (evidence: Record<string, unknown>) => string;
};

type Cardinality = 1000 | 10000 | 100000;

type CardinalitySample = {
  cardinality: Cardinality;
  page_size: number;
  api_request_count: number;
  api_response_bytes: number;
  readiness_ms: number;
  interaction_to_next_paint_ms: number;
  dom_marker_count: number;
  native_layer_expected: boolean;
};

const CARDINALITIES: Cardinality[] = [1000, 10000, 100000];
const EMPTY_CURSOR_PAGE = {
  items: [],
  page: {
    limit: MAP_CARDINALITY_PAGE_SIZE,
    next_cursor: null,
    has_more: false,
  },
};

function roundMilliseconds(value: number): number {
  return Math.round(value * 1000) / 1000;
}

function benchmarkNode(index: number) {
  const anchors = [
    [0, 0],
    [10.4515, 51.1657],
    [9.9, 54.2],
    [10.06, 53.56],
  ] as const;
  const anchor = anchors[index % anchors.length];
  const ring = Math.floor(index / anchors.length);
  const offset = (ring % 400) * 0.00002;
  return {
    id: `benchmark-node-${index.toString().padStart(6, "0")}`,
    kind: "Knoten",
    title: `Benchmark ${index}`,
    summary: "Deterministic map cardinality proof node",
    location: {
      lon: anchor[0] + offset,
      lat: anchor[1] + offset,
    },
    created_at: "2026-09-04T00:00:00Z",
    updated_at: "2026-09-04T00:00:00Z",
    modules: [],
  };
}

async function fulfillEmptyList(route: Route): Promise<void> {
  const url = new URL(route.request().url());
  const cursorMode =
    url.searchParams.get("pagination") === "cursor" ||
    url.searchParams.has("cursor");
  await route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(cursorMode ? EMPTY_CURSOR_PAGE : []),
  });
}

async function installCardinalityApi(page: Page, cardinality: Cardinality) {
  let apiRequestCount = 0;
  let apiResponseBytes = 0;
  let finalPageServed = false;

  await page.route("**/api/**", async (route) => {
    const request = route.request();
    if (request.method() !== "GET") {
      await route.fallback();
      return;
    }
    const url = new URL(request.url());
    if (url.pathname === "/api/nodes") {
      const requestedLimit = Number(
        url.searchParams.get("limit") ?? MAP_CARDINALITY_PAGE_SIZE,
      );
      const limit = Math.min(
        MAP_CARDINALITY_PAGE_SIZE,
        Number.isInteger(requestedLimit) && requestedLimit > 0
          ? requestedLimit
          : MAP_CARDINALITY_PAGE_SIZE,
      );
      const rawCursor = url.searchParams.get("cursor");
      const offset = rawCursor === null ? 0 : Number(rawCursor);
      if (!Number.isInteger(offset) || offset < 0 || offset >= cardinality) {
        throw new Error(`invalid benchmark cursor ${rawCursor}`);
      }
      const end = Math.min(cardinality, offset + limit);
      const items = Array.from({ length: end - offset }, (_, localIndex) =>
        benchmarkNode(offset + localIndex),
      );
      const hasMore = end < cardinality;
      const body = JSON.stringify({
        items,
        page: {
          limit,
          next_cursor: hasMore ? String(end) : null,
          has_more: hasMore,
        },
      });
      apiRequestCount += 1;
      apiResponseBytes += Buffer.byteLength(body);
      if (!hasMore) finalPageServed = true;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body,
      });
      return;
    }
    if (
      url.pathname === "/api/accounts" ||
      url.pathname === "/api/edges" ||
      url.pathname === "/api/webgemeindezentren"
    ) {
      await fulfillEmptyList(route);
      return;
    }
    await route.fallback();
  });

  return {
    snapshot: () => ({ apiRequestCount, apiResponseBytes, finalPageServed }),
  };
}

async function settleFrames(page: Page, frames: number): Promise<void> {
  await page.evaluate(
    (count) =>
      new Promise<void>((resolve) => {
        const next = (remaining: number): void => {
          if (remaining <= 0) {
            resolve();
            return;
          }
          requestAnimationFrame(() => next(remaining - 1));
        };
        next(count);
      }),
    frames,
  );
}

async function measureWheelToNextPaint(page: Page): Promise<number> {
  await page.evaluate(() => {
    const state = window as Window & {
      __mapCardinalityWheelMs?: number | null;
    };
    state.__mapCardinalityWheelMs = null;
    window.addEventListener(
      "wheel",
      () => {
        const startedAt = performance.now();
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            state.__mapCardinalityWheelMs = performance.now() - startedAt;
          });
        });
      },
      { once: true, capture: true },
    );
  });
  const canvas = page.locator("canvas.maplibregl-canvas").first();
  const box = await canvas.boundingBox();
  if (!box) throw new Error("map canvas bounding box is unavailable");
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.wheel(0, -320);
  await page.waitForFunction(
    () => {
      const state = window as Window & {
        __mapCardinalityWheelMs?: number | null;
      };
      return typeof state.__mapCardinalityWheelMs === "number";
    },
    undefined,
    { timeout: 5000 },
  );
  return page.evaluate(() => {
    const value = (
      window as Window & { __mapCardinalityWheelMs?: number | null }
    ).__mapCardinalityWheelMs;
    if (typeof value !== "number")
      throw new Error("wheel paint sample missing");
    return value;
  });
}

test("keeps 1k/10k/100k map cardinalities inside fixed browser budgets", async ({
  browser,
}, testInfo) => {
  const sourceRevision = resolveExactSourceRevision();
  assertExactGitCheckout({ revision: sourceRevision });
  const samples: CardinalitySample[] = [];

  for (const cardinality of CARDINALITIES) {
    const budget = MAP_CARDINALITY_BUDGETS[cardinality];
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      serviceWorkers: "block",
    });
    try {
      const page = await context.newPage();
      await mockApiResponses(page);
      const api = await installCardinalityApi(page, cardinality);
      const startedAt = performance.now();
      await page.goto("/map", { waitUntil: "domcontentloaded" });
      await page.locator("canvas.maplibregl-canvas").first().waitFor({
        state: "visible",
        timeout: budget.readiness_ms,
      });
      await expect
        .poll(() => api.snapshot().finalPageServed, {
          timeout: budget.readiness_ms,
          message: `final ${cardinality}-node cursor page was not consumed`,
        })
        .toBe(true);
      await settleFrames(page, 4);
      const readinessMs = performance.now() - startedAt;
      const domMarkerCount = await page.locator(".map-marker").count();
      if (cardinality === 1000) {
        expect(domMarkerCount).toBeGreaterThan(0);
      }
      const interactionMs = await measureWheelToNextPaint(page);
      const snapshot = api.snapshot();
      samples.push({
        cardinality,
        page_size: MAP_CARDINALITY_PAGE_SIZE,
        api_request_count: snapshot.apiRequestCount,
        api_response_bytes: snapshot.apiResponseBytes,
        readiness_ms: roundMilliseconds(readinessMs),
        interaction_to_next_paint_ms: roundMilliseconds(interactionMs),
        dom_marker_count: domMarkerCount,
        native_layer_expected: cardinality > MAP_CARDINALITY_PAGE_SIZE,
      });
    } finally {
      await context.close();
    }
  }

  const evidence = buildMapCardinalityEvidence({
    sourceRevision,
    generatedAt: new Date().toISOString(),
    browser: { name: "chromium", version: browser.version(), headless: true },
    samples,
  });
  const evidencePath = writeMapCardinalityEvidence(evidence);
  await testInfo.attach("map-cardinality-evidence", {
    body: readFileSync(evidencePath),
    contentType: "application/json",
  });
});
