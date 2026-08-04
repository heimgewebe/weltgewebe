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
  test("renders the canonical zones, separate proposals and topic-coloured threads", async ({
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
    await expect(
      woven.locator('[data-zone="proposal"] [data-zone="vote"]'),
    ).toHaveCount(2);

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
  });
});
