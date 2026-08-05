import { expect, test } from "@playwright/test";
import { FADEN_LIFETIME_MS } from "../src/lib/map/edgeLifecycle";
import { demoAccounts, demoNodes } from "../src/lib/demo/demoData";
import { mockApiResponses, mockListResponse } from "./fixtures/mockApi";

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
  test("renders the canonical zones, visible proposal-bound votes and topic-coloured threads", async ({
    page,
  }) => {
    await mockApiResponses(page);
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
    await expect(woven).toHaveAttribute("data-knotting-threads", "1");
    await expect(woven).toHaveAttribute("data-conversation-threads", "2");
    await expect(woven).toHaveAttribute("data-proposal-count", "2");
    await expect(woven).toHaveAttribute("data-vote-threads", "2");
    await expect(woven.locator('[data-zone="proposal"]')).toHaveCount(2);
    await expect(woven.locator('[data-zone="vote"]')).toHaveCount(2);

    const rendered = await page.evaluate((nodeId) => {
      const map = (window as any).__TEST_MAP__;
      const source = map?.getSource("edges-source");
      const serialized = source?.serialize?.();
      return {
        markerTheme: (
          document.querySelector(
            `[data-testid="marker-node-${nodeId}"] .woven-node`,
          ) as HTMLElement | null
        )?.style.getPropertyValue("--weave-primary"),
        typedFeatures:
          serialized?.data?.features
            ?.filter(
              (feature: any) => feature.properties.fadenType !== "legacy",
            )
            .map((feature: any) => ({
              type: feature.properties.fadenType,
              themeColor: feature.properties.themeColor,
            })) ?? [],
      };
    }, NODE_ID);

    expect(rendered.markerTheme).toMatch(/^#[0-9a-f]{6}$/i);
    expect(rendered.typedFeatures).toHaveLength(edges.length);
    expect(
      new Set(rendered.typedFeatures.map((feature: any) => feature.themeColor)),
    ).toEqual(new Set([rendered.markerTheme]));
    expect(
      new Set(rendered.typedFeatures.map((feature: any) => feature.type)),
    ).toEqual(new Set(["knotting", "conversation", "proposal", "vote"]));

    await expect(marker).toHaveAttribute(
      "aria-label",
      /Knüpfkern 1.*Gesprächsring 2.*Anträge 2.*Stimmen 2/,
    );

    await page.evaluate(() => (window as any).__TEST_MAP__.setZoom(13));
    await expect(woven).toHaveAttribute("data-weave-detail", "compact");
    await expect(woven.locator('[data-zone="vote"]').first()).toBeHidden();

    await page.evaluate(() => (window as any).__TEST_MAP__.setZoom(14));
    await expect(woven).toHaveAttribute("data-weave-detail", "detail");
    await expect(woven.locator('[data-zone="vote"]').first()).toBeVisible();

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
    }

    await page.evaluate(
      (nodeKind) => (window as any).__TEST_SET_ACTIVE_FILTERS__([nodeKind]),
      demoNodes[0].kind || "Knoten",
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
});
