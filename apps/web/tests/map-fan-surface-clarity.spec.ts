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

test.describe("Map fan surface clarity", () => {
  test.beforeEach(async ({ page }) => {
    await mockApiResponses(page, {
      auth: { authenticated: true, account_id: "e2e-weber", role: "weber" },
    });
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/map");
    await page.waitForSelector('[data-testid="tool-fan"]', { timeout: 10000 });
  });

  test("root fans expose only their action pills without opaque carrier panels", async ({
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

    await page.getByTestId("governance-fan-trigger").click();
    const governanceTrigger = page.getByTestId("governance-fan-trigger");
    await expect(governanceTrigger).toContainText("Mitentscheiden");
    await expect(governanceTrigger).not.toContainText("Gemeinsam");
    await expect(governanceTrigger).toHaveAccessibleName(
      "Gemeinsame Entscheidungen schließen",
    );

    expect(await fanSurface(page, "#governance-fan-actions")).toEqual({
      backgroundColor: "rgba(0, 0, 0, 0)",
      borderTopWidth: "0px",
      boxShadow: "none",
      backdropFilter: "none",
      pointerEvents: "none",
    });
    await expect(page.getByTestId("governance-fan-all")).toHaveCSS(
      "pointer-events",
      "auto",
    );
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
