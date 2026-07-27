import { expect, test, type BrowserContext, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { mockApiResponses } from "../fixtures/mockApi";
import { loadPerformanceContract } from "../../scripts/performance-contract.mjs";
import {
  assertExactGitCheckout,
  resolveExactSourceRevision,
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
  interaction_metric_source:
    | "event-timing-and-next-paint-fallback"
    | "next-paint-fallback";
  observed_interactions: number;
  observed_event_entries: number;
  observed_fallback_samples: number;
  observed_fallback_test_ids: string[];
  observed_event_timing_test_ids: string[];
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
        startTime: number;
        targetTestId: string | null;
      }>,
      scriptedFallbacks: [] as Array<{
        index: number;
        testId: string;
        duration: number;
      }>,
      expectedScriptedTestIds: [] as string[],
      nextScriptedIndex: 0,
      unexpectedClicks: [] as string[],
      measurementStartedAt: 0,
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
            target?: EventTarget | null;
          };
          if ((eventEntry.interactionId ?? 0) > 0) {
            const target =
              eventEntry.target instanceof Element
                ? eventEntry.target.closest<HTMLElement>("[data-testid]")
                : null;
            state.eventEntries.push({
              interactionId: eventEntry.interactionId ?? 0,
              duration: eventEntry.duration,
              name: eventEntry.name,
              startTime: eventEntry.startTime,
              targetTestId: target?.dataset.testid ?? null,
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
        if (state.expectedScriptedTestIds.length === 0) return;
        const expectedTestId =
          state.expectedScriptedTestIds[state.nextScriptedIndex];
        const target =
          event.target instanceof Element
            ? event.target.closest<HTMLElement>("[data-testid]")
            : null;
        const targetTestId = target?.dataset.testid ?? "<unknown>";
        if (!expectedTestId || targetTestId !== expectedTestId) {
          state.unexpectedClicks.push(targetTestId);
          return;
        }
        const index = state.nextScriptedIndex;
        state.nextScriptedIndex += 1;
        const startedAt = event.timeStamp;
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            state.scriptedFallbacks.push({
              index,
              testId: expectedTestId,
              duration: Math.max(0, performance.now() - startedAt),
            });
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

async function startScriptedInteractionMeasurement(
  page: Page,
  expectedTestIds: string[],
): Promise<void> {
  await page.evaluate((testIds) => {
    const state = (
      window as Window & {
        __weltgewebeRuntimePerformance?: {
          eventEntries: unknown[];
          scriptedFallbacks: unknown[];
          expectedScriptedTestIds: string[];
          nextScriptedIndex: number;
          unexpectedClicks: string[];
          measurementStartedAt: number;
        };
      }
    ).__weltgewebeRuntimePerformance;
    if (!state) throw new Error("runtime performance state is unavailable");
    state.eventEntries.length = 0;
    state.scriptedFallbacks.length = 0;
    state.expectedScriptedTestIds = [...testIds];
    state.nextScriptedIndex = 0;
    state.unexpectedClicks.length = 0;
    state.measurementStartedAt = performance.now();
  }, expectedTestIds);
}

async function collectSample(
  page: Page,
  runIndex: number,
  usableMapMs: number,
  expectedTestIds: string[],
): Promise<RuntimeSample> {
  const result = await page.evaluate((requiredTestIds) => {
    const state = (
      window as Window & {
        __weltgewebeRuntimePerformance?: {
          lcp: number[];
          eventEntries: Array<{
            interactionId: number;
            duration: number;
            name: string;
            startTime: number;
            targetTestId: string | null;
          }>;
          scriptedFallbacks: Array<{
            index: number;
            testId: string;
            duration: number;
          }>;
          expectedScriptedTestIds: string[];
          nextScriptedIndex: number;
          unexpectedClicks: string[];
          measurementStartedAt: number;
        };
      }
    ).__weltgewebeRuntimePerformance;
    if (!state || state.lcp.length === 0) {
      throw new Error("largest-contentful-paint was not observed");
    }
    if (
      state.nextScriptedIndex !== requiredTestIds.length ||
      state.unexpectedClicks.length > 0
    ) {
      throw new Error(
        `scripted click sequence is incomplete or contaminated: completed=${state.nextScriptedIndex}, unexpected=${state.unexpectedClicks.join(",")}`,
      );
    }
    const fallbacks = [...state.scriptedFallbacks].sort(
      (left, right) => left.index - right.index,
    );
    const fallbackTestIds = fallbacks.map((fallback) => fallback.testId);
    if (
      fallbacks.length !== requiredTestIds.length ||
      fallbackTestIds.some((testId, index) => testId !== requiredTestIds[index])
    ) {
      throw new Error(
        "next-paint fallbacks do not match scripted interactions",
      );
    }
    const eventEntries = state.eventEntries.filter(
      (entry) =>
        entry.startTime >= state.measurementStartedAt &&
        entry.targetTestId !== null &&
        requiredTestIds.includes(entry.targetTestId),
    );
    const eventTimingByTestId = new Map<string, number>();
    for (const entry of eventEntries) {
      const testId = entry.targetTestId;
      if (testId === null) continue;
      eventTimingByTestId.set(
        testId,
        Math.max(eventTimingByTestId.get(testId) ?? 0, entry.duration),
      );
    }
    const eventTimingTestIds = requiredTestIds.filter((testId) =>
      eventTimingByTestId.has(testId),
    );
    const eventTimingValue = Math.max(0, ...eventTimingByTestId.values());
    const fallbackValue = Math.max(
      0,
      ...fallbacks.map((fallback) => fallback.duration),
    );
    if (fallbackValue <= 0) {
      throw new Error("scripted next-paint fallback was not observed");
    }
    return {
      largest_contentful_paint_ms: state.lcp.at(-1) ?? 0,
      interaction_to_next_paint_ms: Math.max(eventTimingValue, fallbackValue),
      interaction_metric_source:
        eventTimingTestIds.length > 0
          ? ("event-timing-and-next-paint-fallback" as const)
          : ("next-paint-fallback" as const),
      observed_interactions: eventTimingTestIds.length,
      observed_event_entries: eventEntries.length,
      observed_fallback_samples: fallbacks.length,
      observed_fallback_test_ids: fallbackTestIds,
      observed_event_timing_test_ids: eventTimingTestIds,
      lcp_entry_count: state.lcp.length,
    };
  }, expectedTestIds);
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
    observed_fallback_samples: result.observed_fallback_samples,
    observed_fallback_test_ids: result.observed_fallback_test_ids,
    observed_event_timing_test_ids: result.observed_event_timing_test_ids,
    lcp_entry_count: result.lcp_entry_count,
  };
}

test("creates exact-revision web runtime evidence", async ({
  browser,
}, testInfo) => {
  const sourceRevision = resolveExactSourceRevision();
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
        await startScriptedInteractionMeasurement(
          page,
          scenario.interaction.test_ids,
        );
        for (const testId of scenario.interaction.test_ids) {
          await page.getByTestId(testId).click();
        }
        await expect(
          page.getByTestId(scenario.interaction.expected_test_id),
        ).toBeVisible();
        await settleAnimationFrames(page, scenario.interaction.settle_frames);
        const sample = await collectSample(
          page,
          runIndex,
          usableMapMs,
          scenario.interaction.test_ids,
        );
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
