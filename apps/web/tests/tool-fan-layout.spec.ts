import { test, expect, type Locator, type Page } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

async function box(locator: Locator) {
  const value = await locator.boundingBox();
  expect(value).not.toBeNull();
  return value!;
}

function overlaps(
  first: { x: number; y: number; width: number; height: number },
  second: { x: number; y: number; width: number; height: number },
) {
  return (
    first.x < second.x + second.width &&
    first.x + first.width > second.x &&
    first.y < second.y + second.height &&
    first.y + first.height > second.y
  );
}

async function expectInsideViewport(page: Page, testIds: string[]) {
  const viewport = page.viewportSize();
  expect(viewport).not.toBeNull();
  for (const testId of testIds) {
    const rect = await box(page.getByTestId(testId));
    expect(rect.x, testId + " leaves the left edge").toBeGreaterThanOrEqual(0);
    expect(rect.y, testId + " leaves the top edge").toBeGreaterThanOrEqual(0);
    expect(
      rect.x + rect.width,
      testId + " leaves the right edge",
    ).toBeLessThanOrEqual(viewport!.width);
    expect(
      rect.y + rect.height,
      testId + " leaves the bottom edge",
    ).toBeLessThanOrEqual(viewport!.height);
  }
}

test.describe("separated map fans", () => {
  test.beforeEach(async ({ page }) => {
    await mockApiResponses(page, {
      auth: { authenticated: true, account_id: "e2e-weber", role: "weber" },
    });
    await page.setViewportSize({ width: 1180, height: 820 });
    await page.goto("/map");
    await page.waitForSelector('[data-testid="tool-fan"]', { timeout: 10000 });
    await page.waitForSelector('[data-testid="governance-fan"]', {
      timeout: 10000,
    });
  });

  test("places governance at top center and tools at bottom center", async ({
    page,
  }) => {
    const tool = await box(page.getByTestId("tool-fan-trigger"));
    const governance = await box(page.getByTestId("governance-fan-trigger"));
    expect(Math.abs(tool.x + tool.width / 2 - 590)).toBeLessThanOrEqual(2);
    expect(
      Math.abs(governance.x + governance.width / 2 - 590),
    ).toBeLessThanOrEqual(2);
    expect(governance.y).toBeLessThan(180);
    expect(tool.y).toBeGreaterThan(700);
  });

  test("opens both action groups as shallow fans rather than flat bars", async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.getByTestId("tool-fan-trigger").click();
    const toolActions = await Promise.all(
      ["find", "content", "weave", "apply"].map((id) =>
        box(page.getByTestId("tool-fan-" + id)),
      ),
    );
    expect(toolActions[0].x).toBeLessThan(toolActions[1].x);
    expect(toolActions[1].x).toBeLessThan(toolActions[2].x);
    expect(toolActions[2].x).toBeLessThan(toolActions[3].x);
    expect(toolActions[1].y).toBeLessThan(toolActions[0].y - 8);
    expect(toolActions[2].y).toBeLessThan(toolActions[3].y - 8);

    await page.keyboard.press("Escape");
    await page.getByTestId("governance-fan-trigger").click();
    const governanceEvents = await Promise.all(
      ["proposals", "open", "voting"].map((id) =>
        box(page.getByTestId("governance-fan-" + id)),
      ),
    );
    expect(governanceEvents[0].x).toBeLessThan(governanceEvents[1].x);
    expect(governanceEvents[1].x).toBeLessThan(governanceEvents[2].x);
    expect(governanceEvents[1].y).toBeGreaterThan(governanceEvents[0].y + 8);
    expect(governanceEvents[1].y).toBeGreaterThan(governanceEvents[2].y + 8);
  });

  test("keeps governance events out of the tool fan", async ({ page }) => {
    await page.getByTestId("tool-fan-trigger").click();
    const actions = page.locator("#tool-fan-actions .fan-action");
    await expect(actions).toHaveCount(4);
    await expect(actions.nth(0)).toHaveAttribute(
      "data-testid",
      "tool-fan-find",
    );
    await expect(actions.nth(0)).toContainText("Finden");
    await expect(actions.nth(1)).toHaveAttribute(
      "data-testid",
      "tool-fan-content",
    );
    await expect(actions.nth(1)).toContainText("Karteninhalt");
    await expect(actions.nth(2)).toHaveAttribute(
      "data-testid",
      "tool-fan-weave",
    );
    await expect(actions.nth(2)).toContainText("Knoten knüpfen");
    await expect(actions.nth(3)).toHaveAttribute(
      "data-testid",
      "tool-fan-apply",
    );
    await expect(actions.nth(3)).toContainText("Antrag stellen");
    await expect(
      page.getByTestId("tool-fan").getByText("Anträge", { exact: true }),
    ).toHaveCount(0);

    const governanceLinks = [
      ["governance-fan-proposals", "/antraege", "Alle Anträge"],
      ["governance-fan-open", "/antraege?sicht=offen", "Offene Entscheidungen"],
      [
        "governance-fan-voting",
        "/antraege?sicht=abstimmung",
        "Gespräch & Abstimmung",
      ],
    ] as const;
    for (const [testId] of governanceLinks) {
      await expect(page.getByTestId(testId)).toHaveAttribute("tabindex", "-1");
    }
    await page.getByTestId("governance-fan-trigger").click();
    await expect(page.getByTestId("tool-fan")).toHaveAttribute(
      "data-expanded",
      "false",
    );
    for (const [testId, href, label] of governanceLinks) {
      const link = page.getByTestId(testId);
      await expect(link).toHaveAttribute("tabindex", "0");
      await expect(link).toHaveAttribute("href", href);
      await expect(link).toContainText(label);
    }
  });

  test("fans and card lenses are mutually exclusive", async ({ page }) => {
    await page.getByTestId("tool-fan-trigger").click();
    await expect(page.getByTestId("tool-fan")).toHaveAttribute(
      "data-expanded",
      "true",
    );
    await page.getByTestId("governance-fan-trigger").click();
    await expect(page.getByTestId("tool-fan")).toHaveAttribute(
      "data-expanded",
      "false",
    );
    await expect(page.getByTestId("governance-fan")).toHaveAttribute(
      "data-expanded",
      "true",
    );

    await page.getByTestId("tool-fan-trigger").click();
    await expect(page.getByTestId("governance-fan")).toHaveAttribute(
      "data-expanded",
      "false",
    );
    await page.getByTestId("tool-fan-find").click();
    await expect(page.getByTestId("search-overlay")).toBeVisible();
    await page.getByTestId("governance-fan-trigger").click();
    await expect(page.getByTestId("search-overlay")).toBeHidden();
    await expect(page.getByTestId("governance-fan")).toHaveAttribute(
      "data-expanded",
      "true",
    );
  });

  test("closed branches are not tabbable and open tools follow their visible order", async ({
    page,
  }) => {
    for (const testId of [
      "tool-fan-find",
      "tool-fan-content",
      "tool-fan-weave",
      "tool-fan-apply",
    ]) {
      await expect(page.getByTestId(testId)).toHaveAttribute("tabindex", "-1");
    }
    const trigger = page.getByTestId("tool-fan-trigger");
    await trigger.focus();
    await trigger.press("Enter");
    for (const testId of [
      "tool-fan-find",
      "tool-fan-content",
      "tool-fan-weave",
      "tool-fan-apply",
    ]) {
      await page.keyboard.press("Tab");
      await expect(page.getByTestId(testId)).toBeFocused();
    }
  });

  test("Escape closes each fan and returns focus to its trigger", async ({
    page,
  }) => {
    const toolTrigger = page.getByTestId("tool-fan-trigger");
    await toolTrigger.click();
    await page.getByTestId("tool-fan-content").focus();
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("tool-fan")).toHaveAttribute(
      "data-expanded",
      "false",
    );
    await expect(toolTrigger).toBeFocused();

    const governanceTrigger = page.getByTestId("governance-fan-trigger");
    await governanceTrigger.click();
    await page.getByTestId("governance-fan-proposals").focus();
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("governance-fan")).toHaveAttribute(
      "data-expanded",
      "false",
    );
    await expect(governanceTrigger).toBeFocused();
  });

  test("the Karteninhalt accessible name includes the active selection count", async ({
    page,
  }) => {
    await page.getByTestId("tool-fan-trigger").click();
    await page.getByTestId("tool-fan-content").click();
    const choices = page
      .getByTestId("filter-overlay")
      .locator('input[type="checkbox"]');
    expect(await choices.count()).toBeGreaterThanOrEqual(2);
    await choices.nth(0).check();
    await choices.nth(1).check();
    await page.getByRole("button", { name: "Karteninhalt schließen" }).click();
    await page.getByTestId("tool-fan-trigger").click();
    await expect(page.getByTestId("tool-fan-content")).toHaveAccessibleName(
      /Karteninhalt.*2 Auswahlen aktiv/,
    );
  });

  test("Antrag stellen opens and focuses the real application target", async ({
    page,
  }) => {
    await page.getByTestId("tool-fan-trigger").click();
    await page.getByTestId("tool-fan-apply").click();
    await expect(page).toHaveURL(/\/antraege\?intent=stellen#antrag-stellen$/);
    const target = page.locator("#antrag-stellen");
    await expect(target).toBeVisible();
    await expect(target).toBeFocused();
    await expect(target).toContainText(
      "Aktuell unterstützt das System als neue Antragsart nur den Weberstatus-Antrag für Gäste",
    );
  });

  test("Knoten knüpfen moves focus into the composition panel", async ({
    page,
  }) => {
    await page.getByTestId("tool-fan-trigger").click();
    await page.getByTestId("tool-fan-weave").click();
    await expect(page.getByTestId("context-panel")).toBeVisible();
    await expect(page.locator("#title")).toBeFocused();
  });

  for (const viewport of [
    { name: "iPad landscape", width: 1180, height: 820 },
    { name: "narrow mobile", width: 320, height: 568 },
  ]) {
    test("keeps each fan inside " + viewport.name, async ({ page }) => {
      await page.setViewportSize({
        width: viewport.width,
        height: viewport.height,
      });
      await page.emulateMedia({ reducedMotion: "reduce" });
      await page.getByTestId("tool-fan-trigger").click();
      await expectInsideViewport(page, [
        "tool-fan-trigger",
        "tool-fan-find",
        "tool-fan-content",
        "tool-fan-weave",
        "tool-fan-apply",
      ]);
      await page.keyboard.press("Escape");
      await page.getByTestId("governance-fan-trigger").click();
      const governanceIds = [
        "governance-fan-trigger",
        "governance-fan-proposals",
        "governance-fan-open",
        "governance-fan-voting",
      ];
      await expectInsideViewport(page, governanceIds);
      if (viewport.width <= 620) {
        const identity = await box(page.locator(".garnrolle-container"));
        for (const testId of governanceIds) {
          expect(
            overlaps(await box(page.getByTestId(testId)), identity),
            testId + " overlaps the identity access",
          ).toBe(false);
        }
      }
    });
  }

  test("all fan and sheet controls meet the 44px touch target", async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.getByTestId("tool-fan-trigger").click();
    for (const testId of [
      "tool-fan-trigger",
      "tool-fan-find",
      "tool-fan-content",
      "tool-fan-weave",
      "tool-fan-apply",
    ]) {
      const rect = await box(page.getByTestId(testId));
      expect(rect.height, testId + " is too short").toBeGreaterThanOrEqual(44);
    }
    await page.keyboard.press("Escape");
    await page.getByTestId("governance-fan-trigger").click();
    for (const testId of [
      "governance-fan-trigger",
      "governance-fan-proposals",
      "governance-fan-open",
      "governance-fan-voting",
    ]) {
      const rect = await box(page.getByTestId(testId));
      expect(rect.height, testId + " is too short").toBeGreaterThanOrEqual(44);
    }
    await page.keyboard.press("Escape");

    await page.setViewportSize({ width: 390, height: 844 });
    await page.locator(".map-marker").first().click();
    const sheetButtons = page
      .getByTestId("context-panel")
      .locator(".sheet-controls button:visible");
    expect(await sheetButtons.count()).toBeGreaterThan(0);
    for (let index = 0; index < (await sheetButtons.count()); index += 1) {
      const rect = await box(sheetButtons.nth(index));
      expect(rect.width).toBeGreaterThanOrEqual(44);
      expect(rect.height).toBeGreaterThanOrEqual(44);
    }
  });
});

test.describe("tool fan guest role", () => {
  test("keeps Knoten knüpfen disabled without removing Antrag stellen", async ({
    page,
  }) => {
    await mockApiResponses(page, {
      auth: { authenticated: false, role: "gast" },
    });
    await page.setViewportSize({ width: 320, height: 568 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/map");
    await page.getByTestId("tool-fan-trigger").click();
    const weave = page.getByTestId("tool-fan-weave");
    await expect(weave).toBeDisabled();
    await expect(weave).toHaveAttribute("tabindex", "-1");
    await expect(weave).toHaveAttribute(
      "aria-label",
      "Knoten knüpfen – Weber-Garnrolle erforderlich",
    );
    await expect(page.getByTestId("tool-fan-apply")).toHaveAttribute(
      "tabindex",
      "0",
    );
    await expectInsideViewport(page, [
      "tool-fan-find",
      "tool-fan-content",
      "tool-fan-weave",
      "tool-fan-apply",
    ]);
  });
});
