import { test, expect } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

const GOVERNANCE_TOP_ROW = [
  "governance-fan-all",
  "governance-fan-open",
  "governance-fan-vetoes",
] as const;

const GOVERNANCE_BOTTOM_ROW = [
  "governance-fan-conversations",
  "governance-fan-voting",
] as const;

const GOVERNANCE_ACTIONS = [
  ...GOVERNANCE_TOP_ROW,
  ...GOVERNANCE_BOTTOM_ROW,
] as const;

type Box = { x: number; y: number; width: number; height: number };

function horizontalCenter(boxes: Box[]): number {
  const left = Math.min(...boxes.map((box) => box.x));
  const right = Math.max(...boxes.map((box) => box.x + box.width));
  return (left + right) / 2;
}

function boxesOverlap(a: Box, b: Box): boolean {
  return (
    a.x < b.x + b.width &&
    a.x + a.width > b.x &&
    a.y < b.y + b.height &&
    a.y + a.height > b.y
  );
}

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
    test(`five governance actions form a centered non-overlapping 3 plus 2 layout at ${viewportWidth}px`, async ({
      page,
    }) => {
      await page.setViewportSize({ width: viewportWidth, height: 800 });
      await page.getByTestId("governance-fan-trigger").click();

      const actions = page.locator("#governance-fan-actions .fan-action");
      await expect(actions).toHaveCount(5);
      await expect(page.getByTestId(GOVERNANCE_ACTIONS[0])).toBeVisible();

      const boxes = await Promise.all(
        GOVERNANCE_ACTIONS.map((testId) =>
          page.getByTestId(testId).boundingBox(),
        ),
      );
      for (const [index, box] of boxes.entries()) {
        expect(
          box,
          "governance action " +
            GOVERNANCE_ACTIONS[index] +
            " must have a bounding box",
        ).not.toBeNull();
      }

      const positionedBoxes = boxes.map((box) => box!);
      const boxByAction = new Map(
        GOVERNANCE_ACTIONS.map(
          (testId, index) => [testId, positionedBoxes[index]] as const,
        ),
      );
      const topRow = GOVERNANCE_TOP_ROW.map(
        (testId) => boxByAction.get(testId)!,
      );
      const bottomRow = GOVERNANCE_BOTTOM_ROW.map(
        (testId) => boxByAction.get(testId)!,
      );
      const rowTolerancePx = 2;

      const topYs = topRow.map((box) => box.y);
      const bottomYs = bottomRow.map((box) => box.y);
      expect(Math.max(...topYs) - Math.min(...topYs)).toBeLessThanOrEqual(
        rowTolerancePx,
      );
      expect(Math.max(...bottomYs) - Math.min(...bottomYs)).toBeLessThanOrEqual(
        rowTolerancePx,
      );
      expect(Math.min(...bottomYs)).toBeGreaterThan(Math.max(...topYs));
      expect(
        Math.abs(horizontalCenter(topRow) - horizontalCenter(bottomRow)),
      ).toBeLessThanOrEqual(rowTolerancePx);

      for (
        let leftIndex = 0;
        leftIndex < positionedBoxes.length;
        leftIndex += 1
      ) {
        for (
          let rightIndex = leftIndex + 1;
          rightIndex < positionedBoxes.length;
          rightIndex += 1
        ) {
          expect(
            boxesOverlap(
              positionedBoxes[leftIndex],
              positionedBoxes[rightIndex],
            ),
            `${GOVERNANCE_ACTIONS[leftIndex]} overlaps ${GOVERNANCE_ACTIONS[rightIndex]}`,
          ).toBe(false);
        }
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

      for (const testId of GOVERNANCE_ACTIONS) {
        const label = page.getByTestId(testId).locator(".fan-label");
        const clipping = await label.evaluate((element) => ({
          horizontal: element.scrollWidth > element.clientWidth + 1,
          vertical: element.scrollHeight > element.clientHeight + 1,
        }));
        expect(clipping, `${testId} label is clipped`).toEqual({
          horizontal: false,
          vertical: false,
        });
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
