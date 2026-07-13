import { test, expect } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test.describe("UI detail remediation", () => {
  test.beforeEach(async ({ page }) => {
    await mockApiResponses(page, {
      auth: { authenticated: true, account_id: "e2e-weber", role: "weber" },
    });
    await page.goto("/map");
    await page.waitForSelector(".map-marker");
  });

  test("keeps map controls and attribution outside desktop focus panel", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.evaluate(() =>
      (document.querySelector(".map-marker") as HTMLElement)?.click(),
    );
    const panel = page.getByTestId("context-panel");
    const navigation = page.locator(".maplibregl-ctrl-group").first();
    const attribution = page.locator(".maplibregl-ctrl-attrib");
    await expect(panel).toBeVisible();
    await expect(navigation).toBeVisible();
    await expect(attribution).toBeVisible();
    const [panelBox, navigationBox, attributionBox] = await Promise.all([
      panel.boundingBox(),
      navigation.boundingBox(),
      attribution.boundingBox(),
    ]);
    expect(panelBox).not.toBeNull();
    for (const box of [navigationBox, attributionBox]) {
      expect(box).not.toBeNull();
      expect((box?.x ?? 0) + (box?.width ?? 0)).toBeLessThanOrEqual(
        panelBox?.x ?? 0,
      );
    }
  });

  test("hides the action bar while a mobile focus sheet is open", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.evaluate(() =>
      (document.querySelector(".map-marker") as HTMLElement)?.click(),
    );
    await expect(page.getByTestId("context-panel")).toBeVisible();
    await expect(page.locator(".action-bar")).toBeHidden();
  });

  test("uses 44 pixel interaction targets for markers, map controls and tabs", async ({
    page,
  }) => {
    const marker = await page.locator(".map-marker").first().boundingBox();
    const control = await page
      .locator(".maplibregl-ctrl-group button")
      .first()
      .boundingBox();
    await page.evaluate(() =>
      (document.querySelector(".map-marker") as HTMLElement)?.click(),
    );
    const tab = await page.getByRole("tab").first().boundingBox();
    expect(marker?.width).toBeGreaterThanOrEqual(44);
    expect(marker?.height).toBeGreaterThanOrEqual(44);
    expect(control?.width).toBeGreaterThanOrEqual(44);
    expect(control?.height).toBeGreaterThanOrEqual(44);
    expect(tab?.height).toBeGreaterThanOrEqual(44);
  });

  test("keeps the visible node marker on the original bottom anchor", async ({
    page,
  }) => {
    const marker = page.locator(".map-marker:not(.marker-account)").first();
    const visual = marker.locator(".map-marker__visual");
    const [markerBox, visualBox] = await Promise.all([
      marker.boundingBox(),
      visual.boundingBox(),
    ]);
    expect(markerBox).not.toBeNull();
    expect(visualBox).not.toBeNull();
    expect(Math.round((visualBox?.y ?? 0) + (visualBox?.height ?? 0))).toBe(
      Math.round((markerBox?.y ?? 0) + (markerBox?.height ?? 0)),
    );
  });

  test("does not expose unfinished node tabs or raw coordinates", async ({
    page,
  }) => {
    const node = page.locator(".map-marker:not(.marker-account)").first();
    await node.click({ force: true });
    const panel = page.getByTestId("context-panel");
    await expect(panel.getByRole("tab", { name: "Gespräch" })).toHaveCount(0);
    await expect(panel.getByRole("tab", { name: "Anträge" })).toHaveCount(0);
    await expect(panel).not.toContainText("Koordinaten:");
    await expect(panel).not.toContainText("Art: event");
  });

  test("keeps filter results hidden until a filter is selected", async ({
    page,
  }) => {
    await page.getByRole("button", { name: "Filter" }).click();
    await expect(page.getByText(/Wähle mindestens eine Art/)).toBeVisible();
    await expect(page.locator(".filter-result")).toHaveCount(0);
  });
});
