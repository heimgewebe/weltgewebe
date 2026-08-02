import { expect, test, type Page } from "@playwright/test";
import { mockApiResponses, mockListResponse } from "./fixtures/mockApi";

const CENTER = {
  type: "webgemeindezentrum" as const,
  id: "webgemeindezentrum-hammer-park",
  title: "Webgemeindezentrum Hammer Park",
  ortsweberei: {
    id: "ortsweberei-hamm",
    slug: "hamm",
    name: "Ortsweberei Hamm",
    gewebezelle_id: "hamm.weltgewebe.net",
  },
  location_state: "desired" as const,
  location_state_label: "Gewünschter Treffort",
  location: { lat: 53.5585, lon: 10.058 },
  location_label: "Hammer Park – gewünschter Treffpunkt auf der Grünfläche",
  meeting_note:
    "Ein bewusst gewählter öffentlicher Treffpunkt, an dem die Ortsweberei tatsächlich zusammenkommen kann. Die genaue Stelle kann später gemeinsam präzisiert werden.",
  access_note:
    "Gewünschter Treffort: Nutzung, Barrierefreiheit und regelmäßige Verfügbarkeit sind noch nicht bestätigt.",
  created_at: "2026-08-02T10:08:00.000Z",
  updated_at: "2026-08-02T10:08:00.000Z",
};

const DETAILS = {
  ...CENTER,
  location_history: [
    {
      event_id: 1,
      event_type: "placement_desired",
      location_state: "desired" as const,
      location_state_label: "Gewünschter Treffort",
      location: { lat: 53.5585, lon: 10.058 },
      location_label: "Hammer Park – gewünschter Treffpunkt auf der Grünfläche",
      reason:
        "Erste Ortsweberei: gewünschter gemeinsamer Treffpunkt auf einer Grünfläche im Hammer Park.",
      decided_at: "2026-08-02T10:08:00.000Z",
    },
  ],
};

async function mockCenter(page: Page) {
  await mockApiResponses(page, {
    auth: { authenticated: true, account_id: "e2e-weber", role: "weber" },
  });
  await page.route("**/api/webgemeindezentren*", async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname !== "/api/webgemeindezentren") {
      await route.fallback();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(mockListResponse(route.request().url(), [CENTER])),
    });
  });
  await page.route(
    "**/api/webgemeindezentren/webgemeindezentrum-hammer-park",
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(DETAILS),
      });
    },
  );
}

test.describe("Webgemeindezentrum Hammer Park", () => {
  test.beforeEach(async ({ page }) => {
    await mockCenter(page);
  });

  test("is a separately typed desired meeting place and never claims confirmation", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1200, height: 850 });
    await page.goto("/map?focus=zentrum:webgemeindezentrum-hammer-park");

    const marker = page.getByTestId(
      "marker-webgemeindezentrum-webgemeindezentrum-hammer-park",
    );
    await expect(marker).toBeVisible();
    await expect(marker).toHaveClass(/marker-webgemeindezentrum/);
    await expect(marker).toHaveAttribute("data-location-state", "desired");
    await expect(marker).toHaveAttribute(
      "data-marker-category",
      "webgemeindezentrum",
    );

    const panel = page.getByTestId("context-panel");
    await expect(panel).toBeVisible();
    await expect(panel.locator(".panel-header h2")).toContainText(
      "Webgemeindezentrum",
    );
    await expect(page.getByTestId("webgemeindezentrum-heading")).toHaveText(
      "Webgemeindezentrum Hammer Park",
    );
    await expect(
      page.getByTestId("webgemeindezentrum-location-state"),
    ).toHaveText("Gewünschter Treffort");
    await expect(panel).toContainText(
      "Hammer Park – gewünschter Treffpunkt auf der Grünfläche",
    );
    await expect(panel).toContainText("Ortsweberei Hamm");
    await expect(panel).toContainText("hamm.weltgewebe.net");
    await expect(panel).toContainText("Noch keine Bestätigung");
    await expect(panel).toContainText("tatsächlich zusammenkommen");
    await expect(panel).not.toContainText("Bestätigter Treffort");
    await expect(panel).not.toContainText("reserviert");

    await page.waitForFunction(() => {
      const map = (window as any).__TEST_MAP__;
      if (!map) return false;
      const center = map.getCenter();
      return (
        Math.abs(center.lng - 10.058) < 0.0005 &&
        Math.abs(center.lat - 53.5585) < 0.0005 &&
        map.getZoom() >= 14
      );
    });
  });

  test("opens from the map with a real keyboard action", async ({ page }) => {
    await page.goto("/map");
    const marker = page.getByTestId(
      "marker-webgemeindezentrum-webgemeindezentrum-hammer-park",
    );
    await expect(marker).toBeVisible();
    await marker.focus();
    await expect(marker).toBeFocused();
    await page.keyboard.press("Enter");

    await expect(page.getByTestId("context-panel")).toBeVisible();
    await expect(page.getByTestId("webgemeindezentrum-heading")).toBeFocused();
  });

  test("keeps the essential truth visible in the compact mobile stage", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(
      "/map?focus=webgemeindezentrum:webgemeindezentrum-hammer-park",
    );

    const summary = page.getByTestId("webgemeindezentrum-compact-summary");
    await expect(summary).toBeVisible();
    await expect(summary).toContainText("Hammer Park");
    await expect(summary).toContainText("Ortsweberei Hamm");
    await expect(
      page.getByTestId("webgemeindezentrum-location-state"),
    ).toHaveText("Gewünschter Treffort");
  });
});
