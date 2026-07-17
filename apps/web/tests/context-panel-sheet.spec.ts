import { test, expect } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";
import { activateToolFanAction } from "./fixtures/toolFan";

test.describe("ContextPanel mobile sheet stages", () => {
  test.beforeEach(async ({ page }) => {
    await mockApiResponses(page, {
      auth: { authenticated: true, account_id: "e2e-weber", role: "weber" },
    });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/map");
    await page.waitForSelector(".map-marker", { timeout: 10000 });
  });

  test("Fokus opens in the compact preview stage on mobile", async ({
    page,
  }) => {
    await page.evaluate(() =>
      (document.querySelector(".map-marker") as HTMLElement)?.dispatchEvent(
        new MouseEvent("click", { bubbles: true }),
      ),
    );

    const panel = page.getByTestId("context-panel");
    await expect(panel).toBeVisible();
    await expect(panel).toHaveAttribute("data-sheet-stage", "preview");

    const preview = page.getByRole("button", { name: "Vorschau" });
    await expect(preview).toHaveAttribute("aria-pressed", "true");
    await expect(panel.locator(".sheet-handle")).toHaveCount(0);
  });

  test("the accessible toggle switches between preview, half and full", async ({
    page,
  }) => {
    // Settle the height transition instantly so bounding boxes reflect the
    // resting size of each stage rather than a mid-animation frame.
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.evaluate(() =>
      (document.querySelector(".map-marker") as HTMLElement)?.dispatchEvent(
        new MouseEvent("click", { bubbles: true }),
      ),
    );

    const panel = page.getByTestId("context-panel");
    const half = page.getByRole("button", { name: "Halbe Höhe" });
    const full = page.getByRole("button", { name: "Vollbild" });

    const previewBox = await panel.boundingBox();

    await half.click();
    await expect(panel).toHaveAttribute("data-sheet-stage", "half");
    await expect(half).toHaveAttribute("aria-pressed", "true");
    const halfBox = await panel.boundingBox();
    expect(halfBox!.height).toBeGreaterThan(previewBox!.height);

    await full.click();
    await expect(panel).toHaveAttribute("data-sheet-stage", "full");
    await expect(full).toHaveAttribute("aria-pressed", "true");
    const fullBox = await panel.boundingBox();
    expect(fullBox!.height).toBeGreaterThan(halfBox!.height);
  });

  test("Komposition always opens the full stage, without a stage toggle", async ({
    page,
  }) => {
    await page.waitForSelector('[data-testid="tool-fan"]', {
      timeout: 10000,
    });
    // The tool fan collapses on mobile once the panel is open, so open
    // komposition first.
    await activateToolFanAction(page, "weave");

    const panel = page.getByTestId("context-panel");
    await expect(panel).toBeVisible();
    await expect(panel).toHaveAttribute("data-sheet-stage", "full");
    await expect(page.getByLabel("Panelgröße")).toHaveCount(0);
  });

  test("orientation change keeps the open panel inside the viewport", async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.locator(".map-marker").first().click();
    const panel = page.getByTestId("context-panel");
    await page.getByRole("button", { name: "Vollbild" }).click();
    await expect(panel).toHaveAttribute("data-sheet-stage", "full");

    await page.setViewportSize({ width: 844, height: 390 });
    const box = await panel.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.y).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(844);
    expect(box!.y + box!.height).toBeLessThanOrEqual(390);
    await expect(page.getByLabel("Panelgröße")).toBeHidden();
  });

  test("switching the selected marker resets the sheet back to preview", async ({
    page,
  }) => {
    await page.evaluate(() =>
      (
        document.querySelectorAll(".map-marker")[0] as HTMLElement
      )?.dispatchEvent(new MouseEvent("click", { bubbles: true })),
    );
    const panel = page.getByTestId("context-panel");
    await page.getByRole("button", { name: "Vollbild" }).click();
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

  test("no sheet-size toggle is shown, and the panel keeps its fixed width", async ({
    page,
  }) => {
    await page.evaluate(() =>
      (document.querySelector(".map-marker") as HTMLElement)?.dispatchEvent(
        new MouseEvent("click", { bubbles: true }),
      ),
    );
    const panel = page.getByTestId("context-panel");
    await expect(panel).toBeVisible();
    await expect(page.getByLabel("Panelgröße")).toBeHidden();

    const box = await panel.boundingBox();
    expect(Math.round(box!.width)).toBe(400);
  });
});
