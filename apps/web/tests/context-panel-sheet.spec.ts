import { test, expect, type Page } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";
import { activateToolFanAction } from "./fixtures/toolFan";

async function openFirstNode(page: Page): Promise<void> {
  await page.evaluate(() =>
    (document.querySelector(".map-marker") as HTMLElement)?.dispatchEvent(
      new MouseEvent("click", { bubbles: true }),
    ),
  );
}

test.describe("ContextPanel mobile compact and full stages", () => {
  test.beforeEach(async ({ page }) => {
    await mockApiResponses(page, {
      auth: { authenticated: true, account_id: "e2e-weber", role: "weber" },
    });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/map");
    await page.waitForSelector(".map-marker", { timeout: 10000 });
  });

  test("Fokus opens as a compact card without separate size buttons", async ({
    page,
  }) => {
    await openFirstNode(page);

    const panel = page.getByTestId("context-panel");
    const handle = page.getByTestId("sheet-handle");
    await expect(panel).toBeVisible();
    await expect(panel).toHaveAttribute("data-sheet-stage", "preview");
    await expect(handle).toBeVisible();
    await expect(handle).toHaveAttribute("aria-pressed", "false");
    expect((await handle.boundingBox())?.height).toBeGreaterThanOrEqual(44);
    await expect(page.getByLabel("Panelgröße")).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "Halbe Höhe", exact: true }),
    ).toHaveCount(0);
  });

  test("tapping the handle and title switches between compact and full", async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await openFirstNode(page);

    const panel = page.getByTestId("context-panel");
    const handle = page.getByTestId("sheet-handle");
    const compactBox = await panel.boundingBox();

    await handle.click();
    await expect(panel).toHaveAttribute("data-sheet-stage", "full");
    await expect(handle).toHaveAttribute("aria-pressed", "true");
    const fullBox = await panel.boundingBox();
    expect(fullBox!.height).toBeGreaterThan(compactBox!.height);

    const titleToggle = page.getByRole("button", {
      name: /Knoten, Vollansicht; Ansicht wechseln/,
    });
    await expect(titleToggle).toBeEnabled();
    await titleToggle.click();
    await expect(panel).toHaveAttribute("data-sheet-stage", "preview");
  });

  test("Komposition starts full but can be collapsed to a compact card", async ({
    page,
  }) => {
    await page.waitForSelector('[data-testid="tool-fan"]', {
      timeout: 10000,
    });
    await activateToolFanAction(page, "weave");

    const panel = page.getByTestId("context-panel");
    const handle = page.getByTestId("sheet-handle");
    await expect(panel).toBeVisible();
    await expect(panel).toHaveAttribute("data-sheet-stage", "full");
    await handle.click();
    await expect(panel).toHaveAttribute("data-sheet-stage", "preview");
  });

  test("the handle supports keyboard changes and pointer dragging", async ({
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
    await expect(panel).toHaveAttribute("data-sheet-stage", "preview");
    await handle.press("End");
    await expect(panel).toHaveAttribute("data-sheet-stage", "full");
    await handle.press("Home");
    await expect(panel).toHaveAttribute("data-sheet-stage", "preview");
    await handle.press("Space");
    await expect(panel).toHaveAttribute("data-sheet-stage", "full");
    await handle.press("Home");

    const box = await handle.boundingBox();
    expect(box).not.toBeNull();
    await page.mouse.move(box!.x + box!.width / 2, box!.y + box!.height / 2);
    await page.mouse.down();
    await page.mouse.move(box!.x + box!.width / 2, box!.y - 360, {
      steps: 8,
    });
    await page.mouse.up();
    await expect(panel).toHaveAttribute("data-sheet-stage", "full");
  });

  test("node tabs appear only in the full mobile view", async ({ page }) => {
    await openFirstNode(page);
    const panel = page.getByTestId("context-panel");
    const tabs = panel.locator(".tabs");

    await expect(panel).toHaveAttribute("data-sheet-stage", "preview");
    await expect(tabs).toBeHidden();
    await page.getByTestId("sheet-handle").click();
    await expect(panel).toHaveAttribute("data-sheet-stage", "full");
    await expect(tabs).toBeVisible();
  });

  test("orientation change keeps the open panel inside the viewport", async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.locator(".map-marker").first().click();
    const panel = page.getByTestId("context-panel");
    await page.getByTestId("sheet-handle").click();
    await expect(panel).toHaveAttribute("data-sheet-stage", "full");

    await page.setViewportSize({ width: 844, height: 390 });
    const box = await panel.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.y).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(844);
    expect(box!.y + box!.height).toBeLessThanOrEqual(390);
    await expect(page.getByTestId("sheet-handle")).toBeHidden();
  });

  test("switching the selected marker resets the sheet to compact", async ({
    page,
  }) => {
    await page.evaluate(() =>
      (
        document.querySelectorAll(".map-marker")[0] as HTMLElement
      )?.dispatchEvent(new MouseEvent("click", { bubbles: true })),
    );
    const panel = page.getByTestId("context-panel");
    await page.getByTestId("sheet-handle").click();
    await expect(panel).toHaveAttribute("data-sheet-stage", "full");

    await page.evaluate(() =>
      (
        document.querySelectorAll(".map-marker")[1] as HTMLElement
      )?.dispatchEvent(new MouseEvent("click", { bubbles: true })),
    );
    await expect(panel).toHaveAttribute("data-sheet-stage", "preview");
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

  test("the panel keeps its fixed width and hides mobile controls", async ({
    page,
  }) => {
    await openFirstNode(page);
    const panel = page.getByTestId("context-panel");
    await expect(panel).toBeVisible();
    await expect(page.getByTestId("sheet-handle")).toBeHidden();
    await expect(
      page.getByRole("button", {
        name: /Knoten, Kompaktkarte; Ansicht wechseln/,
      }),
    ).toBeHidden();
    await expect(panel.locator(".desktop-heading")).toHaveText("Knoten");

    const box = await panel.boundingBox();
    expect(Math.round(box!.width)).toBe(400);
  });
});
