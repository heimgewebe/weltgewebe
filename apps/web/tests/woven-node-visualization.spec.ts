import { expect, test } from "@playwright/test";
import { FADEN_LIFETIME_MS } from "../src/lib/map/edgeLifecycle";
import { demoAccounts, demoNodes } from "../src/lib/demo/demoData";
import { mockApiResponses, mockListResponse } from "./fixtures/mockApi";
import { activateToolFanAction } from "./fixtures/toolFan";

const NODE_ID = demoNodes[0].id;
const ACCOUNT_A = demoAccounts[0].id;
const ACCOUNT_B = demoAccounts[1].id;
const CREATED_AT_MS = Date.now() - 60_000;
const CREATED_AT = new Date(CREATED_AT_MS).toISOString();
const EXPIRES_AT = new Date(CREATED_AT_MS + FADEN_LIFETIME_MS).toISOString();

function faden(
  id: string,
  sourceId: string,
  type: "knotting" | "conversation" | "proposal" | "vote",
  subjectId: string,
) {
  return {
    id,
    source_id: sourceId,
    source_type: "account",
    target_id: NODE_ID,
    target_type: "node",
    edge_kind: "reference",
    faden_type: type,
    faden_subject_id: subjectId,
    created_at: CREATED_AT,
    expires_at: EXPIRES_AT,
  };
}

test.describe("Gewachsene Knoten und antragsgebundene Stimmkränze", () => {
  test("renders the diagonal X, zones, proposal-bound votes and topic-coloured threads", async ({
    page,
  }) => {
    await mockApiResponses(page);
    // kind "Knoten" is ignored as a theme, so the two tags alone colour the arms.
    const multiThemeNode = {
      ...demoNodes[0],
      tags: ["Natur", "Bildung"],
      kind: "Knoten",
    };
    await page.route("**/api/nodes*", async (route) => {
      const requestUrl = route.request().url();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockListResponse(requestUrl, [multiThemeNode])),
      });
    });
    const edges = [
      faden("knotting-a", ACCOUNT_A, "knotting", NODE_ID),
      faden(
        "conversation-general",
        ACCOUNT_B,
        "conversation",
        "conversation-node",
      ),
      faden("proposal-a", ACCOUNT_A, "proposal", "proposal-a"),
      faden("proposal-b", ACCOUNT_B, "proposal", "proposal-b"),
      faden("conversation-a", ACCOUNT_B, "conversation", "proposal-a"),
      faden("vote-a", ACCOUNT_A, "vote", "proposal-a"),
      faden("vote-b", ACCOUNT_B, "vote", "proposal-b"),
    ];

    await page.route("**/api/edges*", async (route) => {
      const requestUrl = route.request().url();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockListResponse(requestUrl, edges)),
      });
    });

    await page.goto("/map");

    const marker = page.getByTestId(`marker-node-${NODE_ID}`);
    await expect(marker).toBeVisible({ timeout: 15_000 });
    const woven = marker.locator(".woven-node");
    await expect(woven).toHaveAttribute(
      "data-zone-order",
      "knotting,conversation,proposal,vote",
    );
    await expect(woven).toHaveAttribute("data-x-geometry", "diagonal");
    await expect(woven).toHaveAttribute("data-knotting-threads", "1");
    await expect(woven).toHaveAttribute("data-conversation-threads", "2");
    await expect(woven).toHaveAttribute("data-proposal-count", "2");
    await expect(woven).toHaveAttribute("data-vote-threads", "2");
    await expect(woven.locator(".woven-node__arm")).toHaveCount(4);
    await expect(woven.locator('[data-zone="proposal"]')).toHaveCount(2);
    await expect(woven.locator('[data-zone="vote"]')).toHaveCount(2);
    await expect(woven.locator(".woven-node__cross")).toHaveCount(0);

    const armColors = await woven.evaluate((root) =>
      Array.from(root.querySelectorAll<HTMLElement>(".woven-node__arm")).map(
        (arm) => ({
          arm: arm.dataset.arm,
          color: arm.style.getPropertyValue("--arm-color").trim(),
        }),
      ),
    );
    expect(new Set(armColors.map((entry) => entry.color)).size).toBe(2);
    const nw = armColors.find((entry) => entry.arm === "northwest")?.color;
    const se = armColors.find((entry) => entry.arm === "southeast")?.color;
    const ne = armColors.find((entry) => entry.arm === "northeast")?.color;
    const sw = armColors.find((entry) => entry.arm === "southwest")?.color;
    expect(nw).toBe(se);
    expect(ne).toBe(sw);
    expect(nw).not.toBe(ne);

    const rendered = await page.evaluate((nodeId) => {
      const map = (window as any).__TEST_MAP__;
      const source = map?.getSource("edges-source");
      const serialized = source?.serialize?.();
      const root = document.querySelector(
        `[data-testid="marker-node-${nodeId}"] .woven-node`,
      ) as HTMLElement | null;
      return {
        markerTheme: root?.style.getPropertyValue("--weave-primary"),
        armColors: Array.from(
          root?.querySelectorAll<HTMLElement>(".woven-node__arm") ?? [],
        ).map((arm) => arm.style.getPropertyValue("--arm-color").trim()),
        typedFeatures:
          serialized?.data?.features
            ?.filter(
              (feature: any) => feature.properties.fadenType !== "legacy",
            )
            .map((feature: any) => ({
              type: feature.properties.fadenType,
              themeColor: feature.properties.themeColor,
              themeColors: feature.properties.themeColors,
              id: feature.properties.id,
            })) ?? [],
      };
    }, NODE_ID);

    expect(rendered.markerTheme).toMatch(/^#[0-9a-f]{6}$/i);
    expect(rendered.typedFeatures.length).toBeGreaterThanOrEqual(edges.length);
    const edgeIds = new Set(
      rendered.typedFeatures.map((feature: any) => feature.id),
    );
    expect(edgeIds.size).toBe(edges.length);
    for (const feature of rendered.typedFeatures) {
      expect(feature.themeColors?.length).toBeGreaterThan(1);
      expect(feature.themeColors).toEqual(
        expect.arrayContaining(rendered.armColors),
      );
      expect(feature.themeColors).toContain(feature.themeColor);
    }
    expect(
      new Set(rendered.typedFeatures.map((feature: any) => feature.type)),
    ).toEqual(new Set(["knotting", "conversation", "proposal", "vote"]));

    await expect(marker).toHaveAttribute(
      "aria-label",
      /Knüpfkern 1.*Gesprächsring 2.*Anträge 2.*Stimmen 2/,
    );

    // Zoom may only toggle compact/detail classes — never replace the marker body.
    await woven.evaluate((element) =>
      element.setAttribute("data-zoom-sentinel", "kept"),
    );
    await page.evaluate(() => (window as any).__TEST_MAP__.setZoom(13));
    await expect(woven).toHaveAttribute("data-weave-detail", "compact");
    await expect(woven.locator('[data-zone="vote"]').first()).toBeHidden();
    await expect(woven).toHaveAttribute("data-zoom-sentinel", "kept");

    await page.evaluate(() => (window as any).__TEST_MAP__.setZoom(14));
    await expect(woven).toHaveAttribute("data-weave-detail", "detail");
    await expect(woven.locator('[data-zone="vote"]').first()).toBeVisible();
    await expect(woven).toHaveAttribute("data-zoom-sentinel", "kept");

    const layerOrder = await woven.evaluate((root) => {
      const z = (selector: string) =>
        Number.parseInt(
          getComputedStyle(root.querySelector(selector) as Element).zIndex,
          10,
        );
      return {
        crossing: z(".woven-node__crossing"),
        conversation: z(".woven-node__conversation"),
        x: z(".woven-node__x"),
        proposal: z('[data-zone="proposal"]'),
        vote: z('[data-zone="vote"]'),
      };
    });
    expect(layerOrder.crossing).toBeLessThan(layerOrder.conversation);
    expect(layerOrder.conversation).toBeLessThan(layerOrder.x);
    expect(layerOrder.x).toBeLessThan(layerOrder.proposal);
    expect(layerOrder.proposal).toBeLessThan(layerOrder.vote);

    const voteContracts = await woven.evaluate((root) => {
      const proposals = Array.from(
        root.querySelectorAll<HTMLElement>('[data-zone="proposal"]'),
      );
      const votes = Array.from(
        root.querySelectorAll<HTMLElement>('[data-zone="vote"]'),
      );
      const rootStyle = getComputedStyle(root);
      return votes.map((vote) => {
        const slot = vote.dataset.proposalSlot;
        const proposal = proposals.find(
          (candidate) => candidate.dataset.proposalSlot === slot,
        );
        if (!proposal) throw new Error(`proposal slot ${slot} missing`);
        const voteStyle = getComputedStyle(vote) as CSSStyleDeclaration & {
          webkitMaskImage?: string;
        };
        const voteRect = vote.getBoundingClientRect();
        const proposalRect = proposal.getBoundingClientRect();
        return {
          slot,
          sameParent:
            vote.parentElement === root && proposal.parentElement === root,
          nestedInProposal: proposal.contains(vote),
          rootOverflow: rootStyle.overflow,
          voteWidth: voteRect.width,
          proposalWidth: proposalRect.width,
          opacity: Number(voteStyle.opacity),
          display: voteStyle.display,
          backgroundImage: voteStyle.backgroundImage,
          maskImage: voteStyle.maskImage || voteStyle.webkitMaskImage || "",
          voteTotal: vote.dataset.voteTotal,
        };
      });
    });

    expect(voteContracts).toHaveLength(2);
    for (const contract of voteContracts) {
      expect(contract.sameParent).toBe(true);
      expect(contract.nestedInProposal).toBe(false);
      expect(contract.rootOverflow).toBe("visible");
      expect(contract.voteWidth).toBeGreaterThan(contract.proposalWidth);
      expect(contract.opacity).toBeGreaterThan(0);
      expect(contract.display).not.toBe("none");
      expect(contract.backgroundImage).toContain("conic-gradient");
      expect(contract.maskImage).toContain("radial-gradient");
      expect(Number(contract.voteTotal)).toBeGreaterThan(0);
    }

    await page.evaluate(
      (nodeKind) => (window as any).__TEST_SET_ACTIVE_FILTERS__([nodeKind]),
      multiThemeNode.kind || "Knoten",
    );
    await expect(
      page.locator('[data-testid^="marker-garnrolle-"]'),
    ).toHaveCount(0);
    await expect(marker).toBeVisible();
    await expect(woven).toHaveAttribute("data-knotting-threads", "1");
    await expect(woven).toHaveAttribute("data-conversation-threads", "2");
    await expect(woven).toHaveAttribute("data-proposal-count", "2");
    await expect(woven).toHaveAttribute("data-vote-threads", "2");
  });

  test("expires a target-only weave edge exactly without ever drawing a line", async ({
    page,
  }) => {
    const now = new Date("2026-08-05T08:00:00.000Z");
    await page.clock.install({ time: now });
    await mockApiResponses(page);

    const targetOnlyEdge = {
      id: "target-only-expiring-knotting",
      source_id: "outside-visible-markers",
      source_type: "account",
      target_id: NODE_ID,
      target_type: "node",
      edge_kind: "reference",
      faden_type: "knotting",
      faden_subject_id: NODE_ID,
      created_at: new Date(
        now.getTime() - FADEN_LIFETIME_MS + 1_000,
      ).toISOString(),
      expires_at: new Date(now.getTime() + 1_000).toISOString(),
    };

    await page.route("**/api/edges*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          mockListResponse(route.request().url(), [targetOnlyEdge]),
        ),
      });
    });

    await page.goto("/map");
    const marker = page.getByTestId(`marker-node-${NODE_ID}`);
    const woven = marker.locator(".woven-node");
    await expect(marker).toBeVisible({ timeout: 15_000 });
    await expect(woven).toHaveAttribute("data-knotting-threads", "1");
    await expect(
      page.getByTestId("marker-garnrolle-outside-visible-markers"),
    ).toHaveCount(0);

    await expect
      .poll(async () =>
        page.evaluate(() => {
          const source = (window as any).__TEST_MAP__?.getSource(
            "edges-source",
          );
          return source?.serialize?.()?.data?.features?.length ?? 0;
        }),
      )
      .toBe(0);

    await page.clock.fastForward(1_001);
    await expect(woven).toHaveAttribute("data-knotting-threads", "0");
    await expect(woven).toHaveAttribute("data-proposal-count", "0");
  });

  test("does not bring an expired thread back when the target is filtered away and shown again", async ({
    page,
  }) => {
    const now = new Date("2026-08-05T08:00:00.000Z");
    await page.clock.install({ time: now });
    await mockApiResponses(page);

    // The source is not among the visible markers, so this thread may shape the
    // target body but must never become a map line.
    const targetOnlyEdge = {
      id: "target-only-filtered-knotting",
      source_id: "outside-visible-markers",
      source_type: "account",
      target_id: NODE_ID,
      target_type: "node",
      edge_kind: "reference",
      faden_type: "knotting",
      faden_subject_id: NODE_ID,
      created_at: new Date(
        now.getTime() - FADEN_LIFETIME_MS + 60_000,
      ).toISOString(),
      expires_at: new Date(now.getTime() + 60_000).toISOString(),
    };

    await page.route("**/api/edges*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          mockListResponse(route.request().url(), [targetOnlyEdge]),
        ),
      });
    });

    const mapLineCount = () =>
      page.evaluate(() => {
        const source = (window as any).__TEST_MAP__?.getSource("edges-source");
        return source?.serialize?.()?.data?.features?.length ?? 0;
      });

    await page.goto("/map");
    const marker = page.getByTestId(`marker-node-${NODE_ID}`);
    const woven = marker.locator(".woven-node");
    await expect(marker).toBeVisible({ timeout: 15_000 });
    await expect(woven).toHaveAttribute("data-knotting-threads", "1");
    await expect(
      page.getByTestId("marker-garnrolle-outside-visible-markers"),
    ).toHaveCount(0);
    await expect.poll(mapLineCount).toBe(0);

    // Hide the target: nothing on screen observes the exact expiry any more.
    await page.evaluate(() =>
      (window as any).__TEST_SET_ACTIVE_FILTERS__(["Garnrolle"]),
    );
    await expect(marker).toHaveCount(0);
    expect(await mapLineCount()).toBe(0);

    // Advance wall time without firing the unrelated map-init watchdog, then
    // run the same projection refresh used by the production interval.
    await page.clock.setSystemTime(new Date(now.getTime() + 120_000));
    await page.evaluate(() =>
      (window as any).__TEST_REFRESH_EDGE_PROJECTION__(),
    );
    expect(await mapLineCount()).toBe(0);

    // Showing it again must read the current time, not the one from before.
    await page.evaluate(() => (window as any).__TEST_SET_ACTIVE_FILTERS__([]));
    await expect(marker).toBeVisible();
    await expect(woven).toHaveAttribute("data-knotting-threads", "0");
    await expect(woven).toHaveAttribute("data-proposal-count", "0");
    await expect.poll(mapLineCount).toBe(0);
  });

  test("dims an ageing proposal thread without replacing its DOM element", async ({
    page,
  }) => {
    const now = new Date("2026-08-05T08:00:00.000Z");
    await page.clock.install({ time: now });
    await mockApiResponses(page);

    const ageing = {
      id: "ageing-proposal",
      source_id: ACCOUNT_A,
      source_type: "account",
      target_id: NODE_ID,
      target_type: "node",
      edge_kind: "reference",
      faden_type: "proposal",
      faden_subject_id: "proposal-a",
      created_at: new Date(now.getTime() - 60_000).toISOString(),
      expires_at: new Date(
        now.getTime() - 60_000 + FADEN_LIFETIME_MS,
      ).toISOString(),
    };

    await page.route("**/api/edges*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockListResponse(route.request().url(), [ageing])),
      });
    });

    await page.goto("/map");
    const marker = page.getByTestId(`marker-node-${NODE_ID}`);
    await expect(marker).toBeVisible({ timeout: 15_000 });
    const proposal = marker.locator(
      '.woven-node [data-zone="proposal"][data-proposal-slot="1"]',
    );
    await expect(proposal).toHaveCount(1);

    // A sentinel that only survives if this very element is kept alive.
    await proposal.evaluate((element) =>
      element.setAttribute("data-sentinel", "kept"),
    );
    const opacityBefore = await proposal.evaluate((element) =>
      Number((element as HTMLElement).style.opacity),
    );
    expect(opacityBefore).toBeGreaterThan(0);

    // Move the projection instant without firing the unrelated map-init
    // watchdog, then invoke the same production refresh used by the interval.
    await page.clock.setSystemTime(new Date(now.getTime() + 3_600_000));
    await page.evaluate(() =>
      (window as any).__TEST_REFRESH_EDGE_PROJECTION__(),
    );

    await expect
      .poll(() =>
        proposal.evaluate((element) =>
          Number((element as HTMLElement).style.opacity),
        ),
      )
      .toBeLessThan(opacityBefore);
    // The DOM was never rebuilt, only its opacity was written.
    await expect(proposal).toHaveAttribute("data-sentinel", "kept");
  });

  test("keeps geometry contracts across density, zoom and viewports with visual evidence", async ({
    page,
  }, testInfo) => {
    await mockApiResponses(page);
    const denseNode = {
      ...demoNodes[0],
      tags: ["Natur", "Bildung", "Kunst", "Handwerk"],
      kind: "Knoten",
    };
    await page.route("**/api/nodes*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          mockListResponse(route.request().url(), [denseNode]),
        ),
      });
    });

    const edges = [
      faden("knotting-dense", ACCOUNT_A, "knotting", NODE_ID),
      ...Array.from({ length: 12 }, (_, index) =>
        faden(
          `conversation-dense-${index}`,
          index % 2 === 0 ? ACCOUNT_A : ACCOUNT_B,
          "conversation",
          "conversation-node",
        ),
      ),
      ...Array.from({ length: 10 }, (_, index) =>
        faden(
          `proposal-dense-${index}`,
          index % 2 === 0 ? ACCOUNT_A : ACCOUNT_B,
          "proposal",
          `proposal-dense-${index}`,
        ),
      ),
      ...Array.from({ length: 20 }, (_, index) =>
        faden(
          `vote-dense-${index}`,
          index % 2 === 0 ? ACCOUNT_A : ACCOUNT_B,
          "vote",
          `proposal-dense-${index % 10}`,
        ),
      ),
    ];
    await page.route("**/api/edges*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockListResponse(route.request().url(), edges)),
      });
    });

    const evidenceDir = testInfo.outputPath("pr-1685-visual-evidence");
    const capture = async (name: string) => {
      await page.screenshot({
        path: `${evidenceDir}/${name}.png`,
        fullPage: false,
      });
    };

    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/map");
    const marker = page.getByTestId(`marker-node-${NODE_ID}`);
    const woven = marker.locator(".woven-node");
    await expect(marker).toBeVisible({ timeout: 15_000 });

    // Full counts stay in model/aria even when the visual proposal slots cap at 8.
    await expect(woven).toHaveAttribute("data-proposal-count", "10");
    await expect(woven).toHaveAttribute("data-conversation-threads", "12");
    await expect(woven).toHaveAttribute("data-vote-threads", "20");
    await expect(woven.locator('[data-zone="proposal"]')).toHaveCount(8);
    await expect(woven.locator(".woven-node__overflow")).toHaveText("+3");
    await expect(woven.locator(".woven-node__arm")).toHaveCount(4);
    await expect(woven).toHaveAttribute("data-x-geometry", "diagonal");

    const geometry = await woven.evaluate((root) => {
      const style = getComputedStyle(root);
      const host = (root.closest(".map-marker") ??
        root.parentElement?.parentElement) as HTMLElement | null;
      const hostBox = host?.getBoundingClientRect();
      const arms = Array.from(
        root.querySelectorAll<HTMLElement>(".woven-node__arm"),
      ).map((arm) => {
        const armStyle = getComputedStyle(arm);
        return {
          arm: arm.dataset.arm,
          color: arm.style.getPropertyValue("--arm-color").trim(),
          transform: armStyle.transform,
        };
      });
      const box = root.getBoundingClientRect();
      return {
        overflow: style.overflow,
        background: style.backgroundColor,
        borderRadius: style.borderRadius,
        width: box.width,
        height: box.height,
        arms,
        hostWidth: hostBox?.width ?? 0,
        hostHeight: hostBox?.height ?? 0,
        distinctArmColors: new Set(
          arms.map((entry) => entry.color).filter(Boolean),
        ).size,
      };
    });
    expect(geometry.overflow).toBe("visible");
    expect(
      geometry.background === "rgba(0, 0, 0, 0)" ||
        geometry.background === "transparent",
    ).toBe(true);
    expect(geometry.distinctArmColors).toBeGreaterThan(1);
    expect(geometry.distinctArmColors).toBeLessThanOrEqual(4);
    expect(geometry.hostWidth).toBeGreaterThanOrEqual(44);
    expect(geometry.hostHeight).toBeGreaterThanOrEqual(44);
    // Diagonal X: both strands are rotated; no axis-aligned plus arms.
    expect(
      geometry.arms.every(
        (arm) => arm.transform.includes("matrix") || arm.transform !== "none",
      ),
    ).toBe(true);

    await page.evaluate(() => (window as any).__TEST_MAP__.setZoom(13.4));
    await expect(woven).toHaveAttribute("data-weave-detail", "compact");
    await expect(woven.locator('[data-zone="vote"]').first()).toBeHidden();
    await capture("desktop-zoom-13.4-compact");

    await page.evaluate(() => (window as any).__TEST_MAP__.setZoom(13.6));
    await expect(woven).toHaveAttribute("data-weave-detail", "detail");
    await expect(woven.locator('[data-zone="vote"]').first()).toBeVisible();
    await capture("desktop-zoom-13.6-detail");

    await marker.focus();
    await expect(marker).toBeFocused();
    await capture("desktop-focus");

    await marker.click();
    await expect(marker).toHaveClass(/is-selected/);
    await expect(marker).toHaveAttribute("data-selected", "true");
    await capture("desktop-selected");

    // Drive the real T006 search path with a fixture that returns this node.
    await page.route("**/api/search*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [
            {
              id: denseNode.id,
              kind: denseNode.kind,
              title: denseNode.title,
              created_at: denseNode.created_at,
              updated_at: denseNode.created_at,
              tags: denseNode.tags,
              location: { lat: denseNode.lat, lon: denseNode.lon },
            },
          ],
          mode: "mock",
          generation_id: "pr-1685-dense-search",
          offset: 0,
        }),
      });
    });
    await activateToolFanAction(page, "find");
    const searchInput = page.locator(".search-box input");
    await expect(searchInput).toBeVisible();
    await searchInput.fill(denseNode.title);
    await expect(marker).toHaveAttribute("data-search-match", "true", {
      timeout: 10_000,
    });
    await expect(marker.locator(".map-marker__halo")).toHaveCSS("opacity", "1");
    await capture("desktop-search-halo");

    await page.emulateMedia({ colorScheme: "dark" });
    await capture("desktop-dark");
    await page.emulateMedia({ colorScheme: "light" });
    await capture("desktop-light");

    await page.setViewportSize({ width: 820, height: 1024 });
    await expect(woven).toBeVisible();
    await capture("tablet-detail");

    await page.setViewportSize({ width: 390, height: 844 });
    await expect(woven).toBeVisible();
    await expect(marker).toBeVisible();
    const mobileTouch = await marker.evaluate((element) => {
      const box = element.getBoundingClientRect();
      return { width: box.width, height: box.height };
    });
    expect(mobileTouch.width).toBeGreaterThanOrEqual(44);
    expect(mobileTouch.height).toBeGreaterThanOrEqual(44);
    await capture("mobile-narrow");

    // Geographic anchor remains bottom-centered after density/viewport changes.
    const anchor = await marker.evaluate((element) => {
      const style = getComputedStyle(element);
      return {
        transform: style.transform,
        transformOrigin: style.transformOrigin,
      };
    });
    expect(
      anchor.transformOrigin === "50% 100%" ||
        anchor.transform.includes("matrix"),
    ).toBe(true);
  });
});
