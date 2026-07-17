import { test, expect } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test.describe("Tool Fan Layout", () => {
  test.beforeEach(async ({ page }) => {
    await mockApiResponses(page, {
      auth: { authenticated: true, account_id: "e2e-weber", role: "weber" },
    });
    await page.goto("/map");
    await page.waitForSelector('[data-testid="tool-fan"]', {
      timeout: 10000,
    });
  });

  test("root button is closed by default and shows a text label", async ({
    page,
  }) => {
    const trigger = page.getByTestId("tool-fan-trigger");
    await expect(trigger).toBeVisible();
    await expect(trigger).toHaveAttribute("aria-expanded", "false");
    await expect(trigger).toHaveAttribute("aria-label", "Werkzeuge öffnen");
    await expect(trigger).toContainText("Werkzeuge");

    // The fan actions exist in the DOM but are not reachable while closed.
    await expect(page.getByTestId("tool-fan-find")).toHaveAttribute(
      "tabindex",
      "-1",
    );
    await expect(page.getByTestId("tool-fan")).toHaveAttribute(
      "data-expanded",
      "false",
    );
  });

  test("opening the fan reveals actions in DOM order Finden, Sicht, Weben with text labels", async ({
    page,
  }) => {
    await page.getByTestId("tool-fan-trigger").click();
    await expect(page.getByTestId("tool-fan")).toHaveAttribute(
      "data-expanded",
      "true",
    );

    const actions = page.locator("#tool-fan-actions .fan-action");
    await expect(actions).toHaveCount(3);
    await expect(actions.nth(0)).toHaveAttribute(
      "data-testid",
      "tool-fan-find",
    );
    await expect(actions.nth(0)).toContainText("Finden");
    await expect(actions.nth(1)).toHaveAttribute(
      "data-testid",
      "tool-fan-sight",
    );
    await expect(actions.nth(1)).toContainText("Sicht");
    await expect(actions.nth(2)).toHaveAttribute(
      "data-testid",
      "tool-fan-weave",
    );
    await expect(actions.nth(2)).toContainText("Weben");

    for (const action of [actions.nth(0), actions.nth(1), actions.nth(2)]) {
      await expect(action).toHaveAttribute("tabindex", "0");
    }
  });

  test("Tab follows the visible order Finden, Sicht, Weben, Anträge", async ({
    page,
  }) => {
    const trigger = page.getByTestId("tool-fan-trigger");
    await trigger.focus();
    await trigger.press("Enter");

    await page.keyboard.press("Tab");
    await expect(page.getByTestId("tool-fan-find")).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(page.getByTestId("tool-fan-sight")).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(page.getByTestId("tool-fan-weave")).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(page.getByTestId("tool-fan-proposals")).toBeFocused();
  });

  test("Anträge appears as a secondary link inside the opened fan", async ({
    page,
  }) => {
    const link = page.getByTestId("tool-fan-proposals");
    await expect(link).toHaveAttribute("tabindex", "-1");

    await page.getByTestId("tool-fan-trigger").click();
    await expect(link).toHaveAttribute("href", "/antraege");
    await expect(link).toHaveAttribute("tabindex", "0");
    await expect(link).toContainText("Anträge");
  });

  test("Escape closes the fan and restores focus to the root button", async ({
    page,
  }) => {
    const trigger = page.getByTestId("tool-fan-trigger");
    await trigger.click();
    await expect(page.getByTestId("tool-fan")).toHaveAttribute(
      "data-expanded",
      "true",
    );

    await page.keyboard.press("Escape");
    await expect(page.getByTestId("tool-fan")).toHaveAttribute(
      "data-expanded",
      "false",
    );
    await expect(trigger).toBeFocused();
  });

  test("clicking outside the fan closes it", async ({ page }) => {
    await page.getByTestId("tool-fan-trigger").click();
    await expect(page.getByTestId("tool-fan")).toHaveAttribute(
      "data-expanded",
      "true",
    );

    await page.mouse.click(20, 20);
    await expect(page.getByTestId("tool-fan")).toHaveAttribute(
      "data-expanded",
      "false",
    );
  });

  test("Weben moves keyboard focus into the opened composition panel", async ({
    page,
  }) => {
    await page.getByTestId("tool-fan-trigger").click();
    await page.getByTestId("tool-fan-weave").click();

    const panel = page.getByTestId("context-panel");
    await expect(panel).toBeVisible();
    await expect(panel.locator("#title")).toBeFocused();
  });

  test("all opened branches stay inside a 320 pixel viewport", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 320, height: 568 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.getByTestId("tool-fan-trigger").click();

    for (const testId of [
      "tool-fan-trigger",
      "tool-fan-find",
      "tool-fan-sight",
      "tool-fan-weave",
      "tool-fan-proposals",
    ]) {
      const box = await page.getByTestId(testId).boundingBox();
      expect(box, `${testId} has no box`).not.toBeNull();
      expect(box!.x, `${testId} leaves the left edge`).toBeGreaterThanOrEqual(
        0,
      );
      expect(box!.y, `${testId} leaves the top edge`).toBeGreaterThanOrEqual(0);
      expect(
        box!.x + box!.width,
        `${testId} leaves the right edge`,
      ).toBeLessThanOrEqual(320);
      expect(
        box!.y + box!.height,
        `${testId} leaves the bottom edge`,
      ).toBeLessThanOrEqual(568);
    }
  });

  test("outside click closes only the fan while search and focus stay open", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.locator(".map-marker").first().click();
    const panel = page.getByTestId("context-panel");
    await expect(panel).toBeVisible();

    await page.getByTestId("tool-fan-trigger").click();
    await page.getByTestId("tool-fan-find").click();
    const search = page.getByTestId("search-overlay");
    await expect(search).toBeVisible();

    await page.getByTestId("tool-fan-trigger").click();
    await expect(page.getByTestId("tool-fan")).toHaveAttribute(
      "data-expanded",
      "true",
    );
    await search.getByRole("searchbox", { name: "Suchbegriff" }).click();

    await expect(page.getByTestId("tool-fan")).toHaveAttribute(
      "data-expanded",
      "false",
    );
    await expect(search).toBeVisible();
    await expect(panel).toBeVisible();
  });

  test("respects reduced motion by disabling the fan open transition", async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    const find = page.getByTestId("tool-fan-find");
    const duration = await find.evaluate(
      (el) => getComputedStyle(el).transitionDuration,
    );
    expect(duration).toMatch(/^0s(,\s*0s)*$/);
  });

  test("root button and fan actions meet the 44px touch target minimum", async ({
    page,
  }) => {
    // Settle the open transform (scale 0.76 -> 1) instantly so the measured
    // box reflects the final, resting size rather than a mid-animation frame.
    await page.emulateMedia({ reducedMotion: "reduce" });

    const trigger = page.getByTestId("tool-fan-trigger");
    const triggerBox = await trigger.boundingBox();
    expect(triggerBox?.height).toBeGreaterThanOrEqual(44);

    await trigger.click();
    for (const testId of [
      "tool-fan-find",
      "tool-fan-sight",
      "tool-fan-weave",
      "tool-fan-proposals",
    ]) {
      const box = await page.getByTestId(testId).boundingBox();
      expect(box?.height).toBeGreaterThanOrEqual(44);
    }
  });
});

test.describe("Tool Fan Layout — guest role", () => {
  test("Weben stays in place and disabled instead of shifting Finden/Sicht", async ({
    page,
  }) => {
    await mockApiResponses(page, {
      auth: { authenticated: false, role: "gast" },
    });
    await page.setViewportSize({ width: 320, height: 568 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/map");
    await page.waitForSelector('[data-testid="tool-fan"]', {
      timeout: 10000,
    });
    await page.getByTestId("tool-fan-trigger").click();

    const weave = page.getByTestId("tool-fan-weave");
    await expect(weave).toBeVisible();
    await expect(weave).toBeDisabled();
    await expect(weave).toHaveAttribute("tabindex", "-1");
    await expect(weave).toHaveAttribute(
      "aria-label",
      "Weben – Weber-Garnrolle erforderlich",
    );
    await expect(weave).toContainText("Weben · Weberstatus nötig");
    const weaveBox = await weave.boundingBox();
    expect(weaveBox).not.toBeNull();
    expect(weaveBox!.x).toBeGreaterThanOrEqual(0);
    expect(weaveBox!.x + weaveBox!.width).toBeLessThanOrEqual(320);

    const trigger = page.getByTestId("tool-fan-trigger");
    await trigger.focus();
    await page.keyboard.press("Tab");
    await expect(page.getByTestId("tool-fan-find")).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(page.getByTestId("tool-fan-sight")).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(page.getByTestId("tool-fan-proposals")).toBeFocused();

    const find = page.getByTestId("tool-fan-find");
    const sight = page.getByTestId("tool-fan-sight");
    const findBox = await find.boundingBox();
    const sightBox = await sight.boundingBox();

    // Same anchored positions as the authenticated weber case.
    expect(Math.round(findBox?.y ?? 0)).toBeGreaterThan(0);
    expect(Math.round(sightBox?.y ?? 0)).toBeGreaterThan(0);
    expect(findBox?.y).toBeLessThan(sightBox?.y ?? 0);
  });
});
