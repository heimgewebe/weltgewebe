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

  for (const viewportWidth of [900, 520, 320] as const) {
    test(`five governance actions form an ordered 3 plus 2 layout at ${viewportWidth}px`, async ({
      page,
    }) => {
      await page.setViewportSize({ width: viewportWidth, height: 800 });
      await page.getByTestId("governance-fan-trigger").click();

      const boxes = await Promise.all(
        [
          "governance-fan-all",
          "governance-fan-open",
          "governance-fan-vetoes",
          "governance-fan-conversations",
          "governance-fan-voting",
        ].map((testId) => page.getByTestId(testId).boundingBox()),
      );
      expect(boxes.every(Boolean)).toBe(true);

      const positionedBoxes = boxes.map((box) => box!);
      const rows: Array<{ y: number; count: number }> = [];
      const rowTolerancePx = 4;

      for (const box of [...positionedBoxes].sort((a, b) => a.y - b.y)) {
        const matchingRow = rows.find(
          (row) => Math.abs(row.y - box.y) <= rowTolerancePx,
        );
        if (matchingRow) {
          matchingRow.count += 1;
        } else {
          rows.push({ y: box.y, count: 1 });
        }
      }

      expect(rows.map((row) => row.count)).toEqual([3, 2]);
      for (const box of positionedBoxes.slice(0, 3)) {
        expect(Math.abs(box.y - rows[0].y)).toBeLessThanOrEqual(rowTolerancePx);
      }
      for (const box of positionedBoxes.slice(3)) {
        expect(Math.abs(box.y - rows[1].y)).toBeLessThanOrEqual(rowTolerancePx);
      }

      const menuBox = await page
        .locator("#governance-fan-actions")
        .boundingBox();
      expect(menuBox).not.toBeNull();
      expect(menuBox!.x).toBeGreaterThanOrEqual(0);
      expect(menuBox!.x + menuBox!.width).toBeLessThanOrEqual(viewportWidth);
      for (const box of positionedBoxes) {
        expect(box.x).toBeGreaterThanOrEqual(0);
        expect(box.x + box.width).toBeLessThanOrEqual(viewportWidth);
      }
    });
  }

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
