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
  faden_endpoint_id: "22222222-2222-5222-8222-222222222222",
  conversation_id: "33333333-3333-5333-8333-333333333333",
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
  governance: {
    proposal_count: 2,
    open_proposal_count: 1,
    voting_proposal_count: 1,
    conversation_message_count: 0,
  },
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
  await page.route("**/api/webgemeindezentren**", async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === "/api/webgemeindezentren") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          mockListResponse(route.request().url(), [DETAILS]),
        ),
      });
      return;
    }
    if (pathname === "/api/webgemeindezentren/webgemeindezentrum-hammer-park") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(DETAILS),
      });
      return;
    }
    await route.fallback();
  });
  await page.route("**/api/proposals", async (route) => {
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON() as Record<string, unknown>;
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          id: "center-sachantrag",
          ...body,
          webgemeindezentrum_id: CENTER.id,
          applicant_account_id: "e2e-weber",
          applicant_title: "E2E Weber",
          status: "consent",
          created_at: "2026-08-08T12:00:00Z",
          consent_until: "2026-08-15T12:00:00Z",
          veto_count: 0,
          message_count: 0,
          yes_votes: 0,
          no_votes: 0,
          abstain_votes: 0,
          remaining_seconds: 604800,
        }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });
  await page.route(
    "**/api/conversations/33333333-3333-5333-8333-333333333333",
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "33333333-3333-5333-8333-333333333333",
          conversation_type: "webgemeindezentrum",
          lifecycle_state: "active",
          node_id: null,
          node_id_snapshot: null,
          node_title_snapshot: null,
          visibility: "public",
          created_at: "2026-08-02T10:08:00.000Z",
          updated_at: "2026-08-02T10:08:00.000Z",
          archived_at: null,
          deleted_at: null,
        }),
      });
    },
  );
  await page.route(
    "**/api/conversations/33333333-3333-5333-8333-333333333333/messages*",
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [],
          page: { limit: 50, next_cursor: null, has_more: false },
        }),
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
    await expect(marker).toHaveClass(/is-selected/);
    const anchorBeforeFocus = await marker.boundingBox();
    if (!anchorBeforeFocus) throw new Error("center marker bounds missing");
    const halo = marker.locator(".map-marker__halo");
    await expect(halo).toHaveCSS("width", "68px");
    await expect(halo).toHaveCSS("opacity", "1");
    await marker.focus();
    await expect(marker).toBeFocused();
    const combinedFocusSelection = await marker.evaluate((element) => {
      const markerBox = element.getBoundingClientRect();
      const haloElement =
        element.querySelector<HTMLElement>(".map-marker__halo")!;
      return {
        markerWidth: markerBox.width,
        markerHeight: markerBox.height,
        markerBottom: markerBox.bottom,
        boxShadow: getComputedStyle(haloElement).boxShadow,
      };
    });
    expect(combinedFocusSelection.markerWidth).toBe(44);
    expect(combinedFocusSelection.markerHeight).toBe(44);
    expect(combinedFocusSelection.boxShadow).toContain("0px 0px 0px 3px");
    expect(combinedFocusSelection.boxShadow).toContain("0px 0px 10px");
    expect(
      Math.abs(
        combinedFocusSelection.markerBottom -
          (anchorBeforeFocus.y + anchorBeforeFocus.height),
      ),
    ).toBeLessThanOrEqual(0.1);
    const haloExtendsBeyondCenter = await marker.evaluate((element) => {
      const haloBox = element
        .querySelector<HTMLElement>(".map-marker__halo")!
        .getBoundingClientRect();
      const visualBox = element
        .querySelector<HTMLElement>(".marker-webgemeindezentrum__visual")!
        .getBoundingClientRect();
      return (
        haloBox.width > visualBox.width && haloBox.height > visualBox.height
      );
    });
    expect(haloExtendsBeyondCenter).toBe(true);

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
    await expect(page.getByTestId("center-governance")).toBeVisible();
    await expect(page.getByTestId("center-governance")).toContainText(
      "Governance der Ortsweberei",
    );
    await expect(
      page.getByTestId("webgemeindezentrum-conversation"),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Gespräch im Webgemeindezentrum" }),
    ).toBeVisible();

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

  test("Weber can create a center Sachantrag from the local Webrat", async ({
    page,
  }) => {
    await page.goto(
      "/map?focus=webgemeindezentrum:webgemeindezentrum-hammer-park&view=webgemeindezentrum",
    );
    const governance = page.getByTestId("center-governance").last();
    await governance
      .getByLabel("Sachantrag stellen")
      .fill("Treffzeiten beschließen");
    await governance
      .getByLabel("Begründung")
      .fill("Die Ortsweberei braucht verlässliche Zeiten.");
    const requestPromise = page.waitForRequest(
      (request) =>
        new URL(request.url()).pathname === "/api/proposals" &&
        request.method() === "POST",
    );
    await governance
      .getByRole("button", { name: "Sachantrag stellen" })
      .click();
    const request = await requestPromise;
    expect(request.postDataJSON()).toEqual({
      kind: "sachantrag",
      title: "Treffzeiten beschließen",
      summary: "Die Ortsweberei braucht verlässliche Zeiten.",
      webgemeindezentrum_id: CENTER.id,
    });
  });

  test("opens a clear full view and preserves the map return target", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1200, height: 850 });
    await page.goto(
      "/map?focus=webgemeindezentrum:webgemeindezentrum-hammer-park",
    );

    const fullViewLink = page.getByTestId("webgemeindezentrum-full-view-link");
    await expect(fullViewLink).toBeVisible();
    await expect(fullViewLink).toHaveAttribute(
      "href",
      "/map?focus=webgemeindezentrum:webgemeindezentrum-hammer-park&view=webgemeindezentrum",
    );
    await fullViewLink.click();

    await expect(page).toHaveURL(
      /\/map\?focus=webgemeindezentrum:webgemeindezentrum-hammer-park&view=webgemeindezentrum$/,
    );
    const fullView = page.getByTestId("webgemeindezentrum-full-view");
    await expect(fullView).toBeVisible();
    const fullViewBounds = await fullView.boundingBox();
    expect(fullViewBounds).not.toBeNull();
    expect(fullViewBounds!.x).toBeCloseTo(0, 1);
    expect(fullViewBounds!.y).toBeCloseTo(0, 1);
    expect(fullViewBounds!.width).toBeCloseTo(1200, 0);
    expect(fullViewBounds!.height).toBeCloseTo(850, 0);
    await expect(
      page.getByRole("heading", {
        level: 1,
        name: "Webgemeindezentrum Hammer Park",
      }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", {
        level: 1,
        name: "Webgemeindezentrum Hammer Park",
      }),
    ).toBeFocused();

    const locationState = page.getByTestId(
      "webgemeindezentrum-full-location-state",
    );
    await expect(locationState).toContainText("Gewünschter Treffort");
    await expect(locationState).toContainText("Noch keine Bestätigung");
    await expect(page.getByTestId("center-governance")).toBeVisible();
    await expect(
      page.getByTestId("webgemeindezentrum-full-conversation"),
    ).toBeVisible();

    const activity = page.getByTestId("webgemeindezentrum-activity-summary");
    await expect(activity).toContainText("2");
    await expect(activity).toContainText("Anträge");
    await expect(activity).toContainText("Gesprächsbeiträge");
    await expect(
      page.getByTestId("webgemeindezentrum-map-link"),
    ).toHaveAttribute(
      "href",
      "/map?focus=webgemeindezentrum:webgemeindezentrum-hammer-park",
    );
  });

  test("does not present missing detail data as zero activity", async ({
    page,
  }) => {
    await page.route(
      "**/api/webgemeindezentren/webgemeindezentrum-hammer-park",
      async (route) => {
        await route.fulfill({ status: 503, body: "detail unavailable" });
      },
    );
    await page.route("**/api/proposals", async (route) =>
      route.fulfill({ status: 503, body: "proposals unavailable" }),
    );
    await page.goto(
      "/map?focus=webgemeindezentrum:webgemeindezentrum-hammer-park&view=webgemeindezentrum",
    );

    await expect(
      page.getByTestId("webgemeindezentrum-details-error"),
    ).toBeVisible();
    await expect(
      page.getByTestId("webgemeindezentrum-activity-summary"),
    ).toHaveCount(0);
    const governance = page.getByTestId("center-governance");
    await expect(governance.getByRole("alert")).toContainText(
      "Anträge können gerade nicht geladen werden.",
    );
    await expect(governance.locator(".counts dd")).toHaveText(["—", "—", "—"]);
    await expect(
      page.getByTestId("webgemeindezentrum-full-location-state"),
    ).toContainText("Gewünschter Treffort");
    await expect(
      page.getByTestId("webgemeindezentrum-details-error"),
    ).toContainText("konnten nicht geladen werden");
  });

  test("opens from the map with a real keyboard action", async ({ page }) => {
    await page.goto("/map");
    const marker = page.getByTestId(
      "marker-webgemeindezentrum-webgemeindezentrum-hammer-park",
    );
    await expect(marker).toBeVisible();
    await marker.focus();
    await expect(marker).toBeFocused();
    await expect(marker.locator(".map-marker__halo")).toHaveCSS("opacity", "1");
    await page.keyboard.press("Enter");

    await expect(page.getByTestId("context-panel")).toBeVisible();
    await expect(page.getByTestId("webgemeindezentrum-heading")).toBeFocused();
  });

  test("keeps the full view readable as a single column on mobile", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(
      "/map?focus=webgemeindezentrum:webgemeindezentrum-hammer-park&view=webgemeindezentrum",
    );

    const fullView = page.getByTestId("webgemeindezentrum-full-view");
    await expect(fullView).toBeVisible();
    const workGrid = fullView.locator(".work-grid");
    await expect(workGrid).toBeVisible();
    const columns = await workGrid.evaluate(
      (element) => getComputedStyle(element).gridTemplateColumns,
    );
    expect(columns.trim().split(/\s+/)).toHaveLength(1);
    await expect(
      page.getByTestId("webgemeindezentrum-full-location-state"),
    ).toContainText("Gewünschter Treffort");
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
