import { expect, test, type BrowserContext, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { mockApiResponses } from "../fixtures/mockApi";
import { loadPerformanceContract } from "../../scripts/performance-contract.mjs";
import {
  assertExactGitCheckout,
  buildWebRuntimeEvidence,
  writeWebRuntimeEvidence,
} from "../../scripts/web-runtime-evidence.mjs";

type NetworkConditions =
  | {
      throttled: false;
      latency_ms: 0;
      download_kbps: 0;
      upload_kbps: 0;
      connection_type: "none";
    }
  | {
      throttled: true;
      latency_ms: number;
      download_kbps: number;
      upload_kbps: number;
      connection_type:
        | "bluetooth"
        | "cellular2g"
        | "cellular3g"
        | "cellular4g"
        | "ethernet"
        | "wifi"
        | "wimax"
        | "other";
    };

type RuntimeProfile = {
  viewport: { width: number; height: number };
  network_profile: string;
  network_conditions: NetworkConditions;
  runs: number;
};

type RuntimeSample = {
  run_index: number;
  largest_contentful_paint_ms: number;
  interaction_to_next_paint_ms: number;
  usable_map_ms: number;
  interaction_metric_source: "event-timing" | "next-paint-fallback";
  observed_interactions: number;
  observed_event_entries: number;
  lcp_entry_count: number;
};

function roundMilliseconds(value: number): number {
  return Math.round(value * 1000) / 1000;
}

async function installPerformanceObservers(
  context: BrowserContext,
): Promise<void> {
  await context.addInitScript(() => {
    const state = {
      lcp: [] as number[],
      eventEntries: [] as Array<{
        interactionId: number;
        duration: number;
        name: string;
      }>,
      nextPaintFallback: [] as number[],
    };
    Object.defineProperty(window, "__weltgewebeRuntimePerformance", {
      value: state,
      configurable: false,
      enumerable: false,
      writable: false,
    });

    try {
      const lcpObserver = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) state.lcp.push(entry.startTime);
      });
      lcpObserver.observe({ type: "largest-contentful-paint", buffered: true });
    } catch {
      // Validation fails closed later when no LCP entry exists.
    }

    try {
      const eventObserver = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          const eventEntry = entry as PerformanceEntry & {
            interactionId?: number;
            duration: number;
          };
          if ((eventEntry.interactionId ?? 0) > 0) {
            state.eventEntries.push({
              interactionId: eventEntry.interactionId ?? 0,
              duration: eventEntry.duration,
              name: eventEntry.name,
            });
          }
        }
      });
      eventObserver.observe({
        type: "event",
        buffered: true,
        durationThreshold: 16,
      } as PerformanceObserverInit & { durationThreshold: number });
    } catch {
      // The two-animation-frame listener below remains as an explicit fallback.
    }

    document.addEventListener(
      "click",
      (event) => {
        const startedAt = event.timeStamp;
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            state.nextPaintFallback.push(
              Math.max(0, performance.now() - startedAt),
            );
          });
        });
      },
      { capture: true },
    );
  });
}

async function applyNetworkProfile(
  context: BrowserContext,
  page: Page,
  conditions: NetworkConditions,
): Promise<void> {
  if (!conditions.throttled) return;
  const session = await context.newCDPSession(page);
  await session.send("Network.enable");
  await session.send("Network.emulateNetworkConditions", {
    offline: false,
    latency: conditions.latency_ms,
    downloadThroughput: (conditions.download_kbps * 1024) / 8,
    uploadThroughput: (conditions.upload_kbps * 1024) / 8,
    connectionType: conditions.connection_type,
  });
}

async function settleAnimationFrames(
  page: Page,
  frames: number,
): Promise<void> {
  await page.evaluate(
    (frameCount) =>
      new Promise<void>((resolve) => {
        const advance = (remaining: number): void => {
          if (remaining <= 0) {
            resolve();
            return;
          }
          requestAnimationFrame(() => advance(remaining - 1));
        };
        advance(frameCount);
      }),
    frames,
  );
}

async function collectSample(
  page: Page,
  runIndex: number,
  usableMapMs: number,
): Promise<RuntimeSample> {
  const result = await page.evaluate(() => {
    const state = (
      window as Window & {
        __weltgewebeRuntimePerformance?: {
          lcp: number[];
          eventEntries: Array<{
            interactionId: number;
            duration: number;
            name: string;
          }>;
          nextPaintFallback: number[];
        };
      }
    ).__weltgewebeRuntimePerformance;
    if (!state || state.lcp.length === 0) {
      throw new Error("largest-contentful-paint was not observed");
    }
    const interactions = new Map<number, number>();
    for (const entry of state.eventEntries) {
      interactions.set(
        entry.interactionId,
        Math.max(interactions.get(entry.interactionId) ?? 0, entry.duration),
      );
    }
    const eventTimingValue = Math.max(0, ...interactions.values());
    const fallbackValue = Math.max(0, ...state.nextPaintFallback);
    if (eventTimingValue === 0 && fallbackValue === 0) {
      throw new Error("no interaction-to-next-paint measurement was observed");
    }
    return {
      largest_contentful_paint_ms: state.lcp.at(-1) ?? 0,
      interaction_to_next_paint_ms:
        eventTimingValue > 0 ? eventTimingValue : fallbackValue,
      interaction_metric_source:
        eventTimingValue > 0
          ? ("event-timing" as const)
          : ("next-paint-fallback" as const),
      observed_interactions: interactions.size,
      observed_event_entries: state.eventEntries.length,
      lcp_entry_count: state.lcp.length,
    };
  });
  return {
    run_index: runIndex,
    usable_map_ms: roundMilliseconds(usableMapMs),
    largest_contentful_paint_ms: roundMilliseconds(
      result.largest_contentful_paint_ms,
    ),
    interaction_to_next_paint_ms: roundMilliseconds(
      result.interaction_to_next_paint_ms,
    ),
    interaction_metric_source: result.interaction_metric_source,
    observed_interactions: result.observed_interactions,
    observed_event_entries: result.observed_event_entries,
    lcp_entry_count: result.lcp_entry_count,
  };
}

test("creates exact-revision web runtime evidence", async ({
  browser,
}, testInfo) => {
  const sourceRevision =
    process.env.GIT_COMMIT_SHA ?? process.env.GITHUB_SHA ?? "";
  expect(sourceRevision).toMatch(/^[0-9a-f]{40}$/);
  assertExactGitCheckout({ revision: sourceRevision });

  const contract = loadPerformanceContract();
  const runtime = contract.measurements.web_runtime;
  const scenario = runtime.scenarios.public_map;
  const samplesByProfile: Record<string, RuntimeSample[]> = {};

  for (const [profileId, untypedProfile] of Object.entries(runtime.profiles)) {
    const profile = untypedProfile as RuntimeProfile;
    const samples: RuntimeSample[] = [];
    for (let runIndex = 1; runIndex <= profile.runs; runIndex += 1) {
      const context = await browser.newContext({
        viewport: profile.viewport,
        serviceWorkers: "block",
      });
      try {
        await installPerformanceObservers(context);
        const page = await context.newPage();
        await applyNetworkProfile(context, page, profile.network_conditions);
        await mockApiResponses(page);
        await page.goto(scenario.path, { waitUntil: "domcontentloaded" });
        for (const selector of scenario.readiness.required_selectors) {
          await page.locator(selector).first().waitFor({
            state: "visible",
            timeout: scenario.readiness.timeout_ms,
          });
        }
        const usableMapMs = await page.evaluate(() => performance.now());
        for (const testId of scenario.interaction.test_ids) {
          await page.getByTestId(testId).click();
        }
        await expect(
          page.getByTestId(scenario.interaction.expected_test_id),
        ).toBeVisible();
        await settleAnimationFrames(page, scenario.interaction.settle_frames);
        const sample = await collectSample(page, runIndex, usableMapMs);
        samples.push(sample);
      } finally {
        await context.close();
      }
    }
    samplesByProfile[profileId] = samples;
  }

  const evidence = buildWebRuntimeEvidence({
    contract,
    sourceRevision,
    generatedAt: new Date().toISOString(),
    browser: {
      name: "chromium",
      version: browser.version(),
      headless: true,
    },
    samplesByProfile,
  });
  const evidencePath = writeWebRuntimeEvidence(evidence);
  await testInfo.attach("web-runtime-evidence", {
    body: readFileSync(evidencePath),
    contentType: "application/json",
  });
});
