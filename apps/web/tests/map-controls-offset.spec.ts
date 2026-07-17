import { test, expect, type Locator } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

type Rect = NonNullable<Awaited<ReturnType<Locator["boundingBox"]>>>;

async function rect(locator: Locator): Promise<Rect> {
  const value = await locator.boundingBox();
  expect(value).not.toBeNull();
  return value!;
}

function overlaps(a: Rect, b: Rect) {
  return (
    a.x < b.x + b.width &&
    a.x + a.width > b.x &&
    a.y < b.y + b.height &&
    a.y + a.height > b.y
  );
}

test.describe("MapLibre control placement", () => {
  test.beforeEach(async ({ page }) => {
    await mockApiResponses(page, {
      auth: { authenticated: true, account_id: "e2e-weber", role: "weber" },
    });
    await page.setViewportSize({ width: 1180, height: 820 });
    await page.goto("/map");
    await page.waitForSelector(".map-marker", { timeout: 10000 });
  });

  test("keeps zoom controls fixed while either fan opens", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    const controls = page.locator(".maplibregl-ctrl-bottom-right").first();
    const baseline = await rect(controls);

    await page.getByTestId("tool-fan-trigger").click();
    expect(await rect(controls)).toEqual(baseline);
    await page.keyboard.press("Escape");

    await page.getByTestId("governance-fan-trigger").click();
    expect(await rect(controls)).toEqual(baseline);
  });

  test("open fans do not overlap zoom controls on iPad landscape", async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    const controls = await rect(
      page.locator(".maplibregl-ctrl-bottom-right").first(),
    );
    await page.getByTestId("tool-fan-trigger").click();
    for (const testId of [
      "tool-fan-trigger",
      "tool-fan-find",
      "tool-fan-content",
      "tool-fan-weave",
      "tool-fan-apply",
    ]) {
      expect(
        overlaps(controls, await rect(page.getByTestId(testId))),
        testId + " overlaps zoom controls",
      ).toBe(false);
    }
    await page.keyboard.press("Escape");
    await page.getByTestId("governance-fan-trigger").click();
    for (const testId of [
      "governance-fan-trigger",
      "governance-fan-proposals",
      "governance-fan-open",
      "governance-fan-voting",
    ]) {
      expect(
        overlaps(controls, await rect(page.getByTestId(testId))),
        testId + " overlaps zoom controls",
      ).toBe(false);
    }
  });

  test("desktop focus panel shifts controls and both centers into the remaining map", async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.locator(".map-marker").first().click();
    const panel = page.getByTestId("context-panel");
    await expect(panel).toBeVisible();
    const panelRect = await rect(panel);
    const mapWidth = panelRect.x;

    const controls = await rect(
      page.locator(".maplibregl-ctrl-bottom-right").first(),
    );
    expect(overlaps(controls, panelRect)).toBe(false);
    expect(controls.x + controls.width).toBeLessThanOrEqual(panelRect.x);

    const tool = await rect(page.getByTestId("tool-fan-trigger"));
    const governance = await rect(page.getByTestId("governance-fan-trigger"));
    expect(
      Math.abs(tool.x + tool.width / 2 - mapWidth / 2),
    ).toBeLessThanOrEqual(2);
    expect(
      Math.abs(governance.x + governance.width / 2 - mapWidth / 2),
    ).toBeLessThanOrEqual(2);

    await page.getByTestId("tool-fan-trigger").click();
    for (const testId of [
      "tool-fan-find",
      "tool-fan-content",
      "tool-fan-weave",
      "tool-fan-apply",
    ]) {
      const item = await rect(page.getByTestId(testId));
      expect(overlaps(item, panelRect), testId + " overlaps focus panel").toBe(
        false,
      );
      expect(overlaps(item, controls), testId + " overlaps zoom controls").toBe(
        false,
      );
    }
    await page.keyboard.press("Escape");
    await page.getByTestId("governance-fan-trigger").click();
    for (const testId of [
      "governance-fan-proposals",
      "governance-fan-open",
      "governance-fan-voting",
    ]) {
      const governanceItem = await rect(page.getByTestId(testId));
      expect(overlaps(governanceItem, panelRect), testId).toBe(false);
      expect(overlaps(governanceItem, controls), testId).toBe(false);
    }
  });

  test("Karteninhalt stays within the remaining desktop map", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 800, height: 800 });
    await page.locator(".map-marker").first().click();
    const panel = page.getByTestId("context-panel");
    await page.getByTestId("tool-fan-trigger").click();
    await page.getByTestId("tool-fan-content").click();
    const content = page.getByTestId("filter-overlay");
    await expect(content).toBeVisible();
    const contentRect = await rect(content);
    const panelRect = await rect(panel);
    expect(contentRect.x).toBeGreaterThanOrEqual(0);
    expect(contentRect.x + contentRect.width).toBeLessThanOrEqual(panelRect.x);
  });

  test("mobile sheet hides the lower fan and moves controls above the sheet", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.locator(".map-marker").first().click();
    const panel = page.getByTestId("context-panel");
    await expect(panel).toBeVisible();
    await expect(page.getByTestId("tool-fan")).toBeHidden();
    const panelRect = await rect(panel);
    const controls = await rect(
      page.locator(".maplibregl-ctrl-bottom-right").first(),
    );
    expect(overlaps(controls, panelRect)).toBe(false);
    expect(controls.y + controls.height).toBeLessThanOrEqual(panelRect.y);
  });
});
