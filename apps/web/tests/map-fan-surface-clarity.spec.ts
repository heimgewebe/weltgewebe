import { test, expect } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

async function fanSurface(
  page: import("@playwright/test").Page,
  selector: string,
) {
  return page.locator(selector).evaluate((element) => {
    const style = getComputedStyle(element);
    return {
      backgroundColor: style.backgroundColor,
      borderTopWidth: style.borderTopWidth,
      boxShadow: style.boxShadow,
      backdropFilter: style.backdropFilter,
      pointerEvents: style.pointerEvents,
    };
  });
}

test.describe("Map tool fan surface clarity", () => {
  test.beforeEach(async ({ page }) => {
    await mockApiResponses(page, {
      auth: { authenticated: true, account_id: "e2e-weber", role: "weber" },
    });
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/map");
    await page.waitForSelector('[data-testid="tool-fan"]', { timeout: 10000 });
  });

  test("root actions stay pill-shaped without an opaque carrier panel", async ({
    page,
  }) => {
    await page.getByTestId("tool-fan-trigger").click();
    await expect(page.getByTestId("tool-fan")).toHaveAttribute(
      "data-expanded",
      "true",
    );

    expect(await fanSurface(page, "#tool-fan-actions")).toEqual({
      backgroundColor: "rgba(0, 0, 0, 0)",
      borderTopWidth: "0px",
      boxShadow: "none",
      backdropFilter: "none",
      pointerEvents: "none",
    });
    await expect(page.getByTestId("tool-fan-find")).toHaveCSS(
      "pointer-events",
      "auto",
    );
    await expect(page.getByTestId("governance-fan-trigger")).toHaveCount(0);
  });

  test("root tool actions stay compact without shrinking below touch-target size", async ({
    page,
  }) => {
    await page.getByTestId("tool-fan-trigger").click();

    for (const testId of [
      "tool-fan-find",
      "tool-fan-map-content",
      "tool-fan-weave",
    ]) {
      const box = await page.getByTestId(testId).boundingBox();
      expect(box).not.toBeNull();
      expect(box!.height).toBeGreaterThanOrEqual(44);
    }

    const findBox = await page.getByTestId("tool-fan-find").boundingBox();
    expect(findBox).not.toBeNull();
    expect(findBox!.width).toBeLessThanOrEqual(106);
  });

  test("the explanatory weaving branch keeps a readable panel surface", async ({
    page,
  }) => {
    await page.getByTestId("tool-fan-trigger").click();
    await page.getByTestId("tool-fan-weave").click();

    const surface = await fanSurface(page, "#tool-fan-actions");
    expect(surface.backgroundColor).not.toBe("rgba(0, 0, 0, 0)");
    expect(surface.borderTopWidth).not.toBe("0px");
    expect(surface.pointerEvents).toBe("auto");
  });
});
