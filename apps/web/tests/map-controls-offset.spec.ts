import { test, expect } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test.describe("MapLibre control placement", () => {
  test.beforeEach(async ({ page }) => {
    await mockApiResponses(page, {
      auth: { authenticated: true, account_id: "e2e-weber", role: "weber" },
    });
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/map");
    await page.waitForSelector(".map-marker", { timeout: 10000 });
  });

  test("zoom controls never overlap the persistently visible tool fan trigger", async ({
    page,
  }) => {
    const controls = page.locator(".maplibregl-ctrl-bottom-right").first();
    const trigger = page.getByTestId("tool-fan-trigger");
    const [controlsBox, triggerBox] = await Promise.all([
      controls.boundingBox(),
      trigger.boundingBox(),
    ]);
    expect(controlsBox).not.toBeNull();
    expect(triggerBox).not.toBeNull();
    const overlaps =
      controlsBox!.x < triggerBox!.x + triggerBox!.width &&
      controlsBox!.x + controlsBox!.width > triggerBox!.x &&
      controlsBox!.y < triggerBox!.y + triggerBox!.height &&
      controlsBox!.y + controlsBox!.height > triggerBox!.y;
    expect(overlaps).toBe(false);
  });

  test("opening the fan moves controls clear of every visible branch", async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.getByTestId("tool-fan-trigger").click();

    const controls = page.locator(".maplibregl-ctrl-bottom-right").first();
    const controlsBox = await controls.boundingBox();
    expect(controlsBox).not.toBeNull();

    for (const testId of [
      "tool-fan-find",
      "tool-fan-sight",
      "tool-fan-weave",
      "tool-fan-proposals",
    ]) {
      const branchBox = await page.getByTestId(testId).boundingBox();
      expect(branchBox).not.toBeNull();
      const overlaps =
        controlsBox!.x < branchBox!.x + branchBox!.width &&
        controlsBox!.x + controlsBox!.width > branchBox!.x &&
        controlsBox!.y < branchBox!.y + branchBox!.height &&
        controlsBox!.y + controlsBox!.height > branchBox!.y;
      expect(overlaps, `${testId} overlaps map controls`).toBe(false);
    }
  });

  test("expanded fan and desktop focus panel both keep controls unobstructed", async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.locator(".map-marker").first().click();
    const panel = page.getByTestId("context-panel");
    await expect(panel).toBeVisible();

    await page.getByTestId("tool-fan-trigger").click();
    const controls = page.locator(".maplibregl-ctrl-bottom-right").first();
    const controlsBox = await controls.boundingBox();
    const panelBox = await panel.boundingBox();
    expect(controlsBox).not.toBeNull();
    expect(panelBox).not.toBeNull();

    const overlaps = (
      a: NonNullable<typeof controlsBox>,
      b: NonNullable<typeof panelBox>,
    ) =>
      a.x < b.x + b.width &&
      a.x + a.width > b.x &&
      a.y < b.y + b.height &&
      a.y + a.height > b.y;

    expect(
      overlaps(controlsBox!, panelBox!),
      "controls overlap focus panel",
    ).toBe(false);
    for (const testId of [
      "tool-fan-find",
      "tool-fan-sight",
      "tool-fan-weave",
      "tool-fan-proposals",
    ]) {
      const branchBox = await page.getByTestId(testId).boundingBox();
      expect(branchBox).not.toBeNull();
      expect(
        overlaps(controlsBox!, branchBox!),
        `${testId} overlaps map controls while focus panel is open`,
      ).toBe(false);
    }
  });

  test("Sicht stays inside the remaining desktop map beside the focus panel", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 800, height: 800 });
    await page.locator(".map-marker").first().click();
    const panel = page.getByTestId("context-panel");
    await expect(panel).toBeVisible();

    await page.getByTestId("tool-fan-trigger").click();
    await page.getByTestId("tool-fan-sight").click();
    const sight = page.getByTestId("filter-overlay");
    await expect(sight).toBeVisible();

    const [sightBox, panelBox] = await Promise.all([
      sight.boundingBox(),
      panel.boundingBox(),
    ]);
    expect(sightBox).not.toBeNull();
    expect(panelBox).not.toBeNull();
    expect(sightBox!.x).toBeGreaterThanOrEqual(0);
    expect(sightBox!.x + sightBox!.width).toBeLessThanOrEqual(panelBox!.x);
  });

  test("opening Finden or Sicht returns zoom controls to the compact position", async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    const controls = page.locator(".maplibregl-ctrl-bottom-right").first();
    const baseline = await controls.boundingBox();

    await page.getByTestId("tool-fan-trigger").click();
    await page.getByTestId("tool-fan-find").click();
    await expect(page.getByTestId("search-overlay")).toBeVisible();
    const withSearchOpen = await controls.boundingBox();
    expect(withSearchOpen).toEqual(baseline);

    await page.getByTestId("tool-fan-trigger").click();
    await page.getByTestId("tool-fan-sight").click();
    await expect(page.getByTestId("filter-overlay")).toBeVisible();
    const withSichtOpen = await controls.boundingBox();
    expect(withSichtOpen).toEqual(baseline);
  });
});
