import { test, expect } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";
import { activateToolFanAction } from "./fixtures/toolFan";

test.describe("ContextPanel mobile compact and full states", () => {
  test.beforeEach(async ({ page }) => {
    await mockApiResponses(page, {
      auth: { authenticated: true, account_id: "e2e-weber", role: "weber" },
    });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/map");
    await page.waitForSelector(".map-marker", { timeout: 10000 });
  });

  test("Fokus opens as a compact card without mobile tabs or size buttons", async ({
    page,
  }) => {
    await page.locator(".map-marker").first().click();

    const panel = page.getByTestId("context-panel");
    const handle = page.getByTestId("sheet-handle");
    await expect(panel).toBeVisible();
    await expect(panel.locator(".panel-header h2")).toHaveCount(1);
    await expect(panel).toHaveAttribute("data-sheet-stage", "compact");
    await expect(handle).toHaveAttribute("aria-expanded", "false");
    await expect(panel.locator(".tabs")).toBeHidden();
    await expect(page.getByLabel("Panelgröße")).toHaveCount(0);
    expect((await handle.boundingBox())?.height).toBeGreaterThanOrEqual(44);
  });

  test("handle and panel title toggle directly between compact and full", async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.locator(".map-marker").first().click();

    const panel = page.getByTestId("context-panel");
    const handle = page.getByTestId("sheet-handle");
    const title = panel.locator(".mobile-panel-title");
    const compactBox = await panel.boundingBox();

    await handle.click();
    await expect(panel).toHaveAttribute("data-sheet-stage", "full");
    await expect(handle).toHaveAttribute("aria-expanded", "true");
    await expect(panel.locator(".tabs")).toBeVisible();
    const fullBox = await panel.boundingBox();
    expect(fullBox!.height).toBeGreaterThan(compactBox!.height);

    await title.click();
    await expect(panel).toHaveAttribute("data-sheet-stage", "compact");
    await expect(panel.locator(".tabs")).toBeHidden();
  });

  test("the compact card shows the overview while preserving the active full-view tab", async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.locator(".map-marker:not(.marker-account)").first().click();

    const panel = page.getByTestId("context-panel");
    const handle = page.getByTestId("sheet-handle");
    await handle.click();

    const conversationTab = panel.getByRole("tab", { name: "Gespräch" });
    await conversationTab.click();
    await expect(conversationTab).toHaveAttribute("aria-selected", "true");
    await expect(panel.locator("#panel-gespraech")).toBeVisible();

    await panel.locator(".mobile-panel-title").click();
    await expect(panel).toHaveAttribute("data-sheet-stage", "compact");
    await expect(panel.locator(".tabs")).toHaveCount(0);
    await expect(
      panel.getByRole("region", { name: "Knotenübersicht" }),
    ).toBeVisible();
    await expect(panel.locator("#panel-gespraech")).toHaveCount(0);

    await panel.locator(".mobile-panel-title").click();
    await expect(conversationTab).toHaveAttribute("aria-selected", "true");
    await expect(panel.locator("#panel-gespraech")).toBeVisible();
  });

  test("Komposition starts full and can collapse through the same handle", async ({
    page,
  }) => {
    await page.waitForSelector('[data-testid="tool-fan"]', {
      timeout: 10000,
    });
    await activateToolFanAction(page, "weave");

    const panel = page.getByTestId("context-panel");
    await expect(panel).toBeVisible();
    await expect(panel).toHaveAttribute("data-sheet-stage", "full");
    await page.getByTestId("sheet-handle").click();
    await expect(panel).toHaveAttribute("data-sheet-stage", "compact");
  });

  test("keyboard and dragging select the two states without a post-drag double toggle", async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.locator(".map-marker").first().click();
    const panel = page.getByTestId("context-panel");
    const handle = page.getByTestId("sheet-handle");

    await handle.focus();
    await handle.press("ArrowUp");
    await expect(panel).toHaveAttribute("data-sheet-stage", "full");
    await handle.press("ArrowDown");
    await expect(panel).toHaveAttribute("data-sheet-stage", "compact");
    await handle.press("End");
    await expect(panel).toHaveAttribute("data-sheet-stage", "full");
    await handle.press("Home");
    await expect(panel).toHaveAttribute("data-sheet-stage", "compact");

    const box = await handle.boundingBox();
    expect(box).not.toBeNull();
    await page.mouse.move(box!.x + box!.width / 2, box!.y + box!.height / 2);
    await page.mouse.down();
    await page.mouse.move(box!.x + box!.width / 2, box!.y - 360, { steps: 8 });
    await page.mouse.up();
    await expect(panel).toHaveAttribute("data-sheet-stage", "full");
    await handle.dispatchEvent("click", { detail: 1 });
    await expect(panel).toHaveAttribute("data-sheet-stage", "full");
  });

  test("non-primary pointers cannot start a sheet drag", async ({ page }) => {
    await page.locator(".map-marker").first().click();
    const panel = page.getByTestId("context-panel");
    const handle = page.getByTestId("sheet-handle");

    await handle.dispatchEvent("pointerdown", {
      pointerId: 23,
      pointerType: "touch",
      isPrimary: false,
      button: 0,
      clientY: 100,
    });

    await expect(panel).toHaveAttribute("data-sheet-stage", "compact");
    await expect(panel).not.toHaveClass(/dragging/);
    await expect(panel).not.toHaveAttribute("style");
  });

  test("reduced motion removes the height transition", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.locator(".map-marker").first().click();
    const transitionDuration = await page
      .getByTestId("context-panel")
      .evaluate((element) => getComputedStyle(element).transitionDuration);
    expect(transitionDuration).toBe("0s");
  });

  test("orientation change keeps the open panel inside the viewport", async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.locator(".map-marker").first().click();
    const panel = page.getByTestId("context-panel");
    await page.getByTestId("sheet-handle").click();
    await expect(panel).toHaveAttribute("data-sheet-stage", "full");

    await page.setViewportSize({ width: 740, height: 390 });
    const box = await panel.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.y).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(740);
    expect(box!.y + box!.height).toBeLessThanOrEqual(390);
    await expect(page.getByTestId("sheet-handle")).toBeVisible();
  });

  test("switching the selected marker resets the sheet to compact", async ({
    page,
  }) => {
    await page.locator(".map-marker").first().click();
    const panel = page.getByTestId("context-panel");
    await page.getByTestId("sheet-handle").click();
    await expect(panel).toHaveAttribute("data-sheet-stage", "full");

    await page.evaluate(() =>
      (
        document.querySelectorAll(".map-marker")[1] as HTMLElement
      )?.dispatchEvent(new MouseEvent("click", { bubbles: true })),
    );
    await expect(panel).toHaveAttribute("data-sheet-stage", "compact");
  });
});

test.describe("ContextPanel desktop layout stays unchanged", () => {
  test.beforeEach(async ({ page }) => {
    await mockApiResponses(page, {
      auth: { authenticated: true, account_id: "e2e-weber", role: "weber" },
    });
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/map");
    await page.waitForSelector(".map-marker", { timeout: 10000 });
  });

  test("the sheet affordances stay hidden and tabs retain their desktop behavior", async ({
    page,
  }) => {
    await page.locator(".map-marker").first().click();
    const panel = page.getByTestId("context-panel");
    await expect(panel).toBeVisible();
    await expect(page.getByTestId("sheet-handle")).toBeHidden();
    await expect(panel.locator(".mobile-panel-title")).toBeHidden();
    await expect(panel.locator(".tabs")).toBeVisible();

    const box = await panel.boundingBox();
    expect(Math.round(box!.width)).toBe(400);
  });
});

test.describe("ContextPanel touch input", () => {
  test.use({ hasTouch: true, viewport: { width: 390, height: 844 } });

  test.beforeEach(async ({ page }) => {
    await mockApiResponses(page, {
      auth: { authenticated: true, account_id: "e2e-weber", role: "weber" },
    });
    await page.goto("/map");
    await page.waitForSelector(".map-marker", { timeout: 10000 });
  });

  test("one touch tap toggles the handle exactly once", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.locator(".map-marker").first().click();
    const panel = page.getByTestId("context-panel");
    const handle = page.getByTestId("sheet-handle");
    const box = await handle.boundingBox();
    expect(box).not.toBeNull();

    await page.touchscreen.tap(
      box!.x + box!.width / 2,
      box!.y + box!.height / 2,
    );

    await expect(panel).toHaveAttribute("data-sheet-stage", "full");
  });
});
