import { test, expect } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

function directConversation(id: string, unreadCount: number, at: string) {
  return {
    id,
    counterpart_account_id: `counterpart-${id}`,
    counterpart_title: `Person ${id}`,
    created_at: at,
    updated_at: at,
    unread_count: unreadCount,
    last_message_preview: `Nachricht ${id}`,
    last_message_at: at,
    blocked_by_me: false,
    can_send: true,
  };
}

function proposal(id: string, createdAt: string) {
  return {
    id,
    kind: "sachantrag",
    webgemeindezentrum_id: "wgz-test",
    title: `Antrag ${id}`,
    applicant_account_id: `author-${id}`,
    applicant_title: `Autor ${id}`,
    status: "consent",
    created_at: createdAt,
    consent_until: "2026-08-24T08:00:00Z",
    veto_count: 0,
    yes_votes: 0,
    no_votes: 0,
    abstain_votes: 0,
  };
}

test.describe("top-left attention bubbles", () => {
  test("shares one initial attention read across both topbar consumers", async ({
    page,
  }) => {
    await mockApiResponses(page, {
      auth: {
        authenticated: true,
        account_id: "weber-attention",
        role: "weber",
      },
    });
    let directReads = 0;
    let proposalReads = 0;
    await page.route("**/api/direct-conversations", async (route) => {
      directReads += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [directConversation("shared", 1, "2026-08-17T08:00:00Z")],
        }),
      });
    });
    await page.route("**/api/proposals", async (route) => {
      proposalReads += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });

    await page.goto("/map");
    await expect(
      page.locator('[data-attention-id="direct:shared"]'),
    ).toBeVisible();
    await expect.poll(() => directReads).toBe(1);
    await expect.poll(() => proposalReads).toBe(1);
  });

  test("mobile keeps newest items left and exposes the rest through +N", async ({
    page,
  }) => {
    await mockApiResponses(page, {
      auth: {
        authenticated: true,
        account_id: "weber-attention",
        role: "weber",
      },
    });
    await page.route("**/api/direct-conversations", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [
            directConversation("newest", 1, "2026-08-17T08:00:00Z"),
            directConversation("second", 2, "2026-08-17T07:00:00Z"),
            directConversation("third", 1, "2026-08-17T06:00:00Z"),
          ],
        }),
      });
    });
    await page.route("**/api/proposals", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          proposal("fourth", "2026-08-17T05:00:00Z"),
          proposal("fifth", "2026-08-17T04:00:00Z"),
        ]),
      });
    });
    await page.setViewportSize({ width: 320, height: 568 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/map");

    const attention = page.getByTestId("attention-bubbles");
    await expect(attention).toBeVisible();
    await expect(page.getByTestId("governance-fan-trigger")).toHaveCount(0);

    const bubbles = attention.locator(".attention-bubble");
    await expect(bubbles).toHaveCount(2);
    await expect(bubbles.nth(0)).toHaveAttribute(
      "data-attention-id",
      "direct:newest",
    );
    await expect(bubbles.nth(1)).toHaveAttribute(
      "data-attention-id",
      "direct:second",
    );

    for (let index = 0; index < 2; index += 1) {
      const box = await bubbles.nth(index).boundingBox();
      expect(box).not.toBeNull();
      expect(box!.width).toBeGreaterThanOrEqual(44);
      expect(box!.height).toBeGreaterThanOrEqual(44);
    }

    const overflow = attention.locator(".attention-overflow-trigger");
    await expect(overflow).toHaveText("+3");
    await expect(overflow).toHaveAccessibleName(
      "3 weitere Aufmerksamkeitseinheiten",
    );
    await overflow.click();
    const menu = page.getByTestId("attention-overflow-menu");
    await expect(menu).toBeVisible();
    await expect(menu.locator(".attention-overflow-item")).toHaveCount(3);
    await expect(
      menu.locator('[data-attention-id="direct:third"]'),
    ).toHaveAttribute("href", "/nachrichten?id=third");
    await expect(
      menu.locator('[data-attention-id="proposal:fourth"]'),
    ).toHaveAttribute("href", "/antraege?id=fourth");

    const [attentionBox, authBox] = await Promise.all([
      attention.boundingBox(),
      page.locator(".auth-slot").boundingBox(),
    ]);
    expect(attentionBox).not.toBeNull();
    expect(authBox).not.toBeNull();
    expect(attentionBox!.x).toBeGreaterThanOrEqual(0);
    expect(attentionBox!.x + attentionBox!.width).toBeLessThanOrEqual(
      authBox!.x,
    );
  });

  test("the bubble row stays inside its topbar track at 390 pixels", async ({
    page,
  }) => {
    await mockApiResponses(page, {
      auth: {
        authenticated: true,
        account_id: "weber-attention",
        role: "weber",
      },
    });
    await page.route("**/api/direct-conversations", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [
            directConversation("newest", 1, "2026-08-17T08:00:00Z"),
            directConversation("second", 1, "2026-08-17T07:00:00Z"),
            directConversation("third", 1, "2026-08-17T06:00:00Z"),
          ],
        }),
      });
    });
    await page.route("**/api/proposals", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          proposal("fourth", "2026-08-17T05:00:00Z"),
          proposal("fifth", "2026-08-17T04:00:00Z"),
        ]),
      });
    });
    await page.setViewportSize({ width: 390, height: 720 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/map");

    const attention = page.getByTestId("attention-bubbles");
    const bubbles = attention.locator(".attention-bubble");
    await expect(bubbles).toHaveCount(2);
    await expect(attention.locator(".attention-overflow-trigger")).toHaveText(
      "+3",
    );

    const [attentionBox, authBox] = await Promise.all([
      attention.boundingBox(),
      page.locator(".auth-slot").boundingBox(),
    ]);
    expect(attentionBox).not.toBeNull();
    expect(authBox).not.toBeNull();
    expect(attentionBox!.x).toBeGreaterThanOrEqual(0);
    expect(attentionBox!.x + attentionBox!.width).toBeLessThanOrEqual(
      authBox!.x,
    );
  });

  test("a newly observed item enters at the far left and shifts the older item right", async ({
    page,
  }) => {
    await mockApiResponses(page, {
      auth: {
        authenticated: true,
        account_id: "weber-attention",
        role: "weber",
      },
    });
    let conversations = [
      directConversation("older", 1, "2026-08-17T06:00:00Z"),
    ];
    await page.route("**/api/direct-conversations", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: conversations }),
      });
    });
    await page.route("**/api/proposals", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });
    await page.goto("/map");

    const bubbles = page
      .getByTestId("attention-bubbles")
      .locator(".attention-bubble");
    await expect(bubbles).toHaveCount(1);
    await expect(bubbles.first()).toHaveAttribute(
      "data-attention-id",
      "direct:older",
    );

    conversations = [
      directConversation("new", 1, "2026-08-17T08:00:00Z"),
      ...conversations,
    ];
    await page.evaluate(() => window.dispatchEvent(new Event("focus")));

    await expect(bubbles).toHaveCount(2);
    await expect(bubbles.nth(0)).toHaveAttribute(
      "data-attention-id",
      "direct:new",
    );
    await expect(bubbles.nth(1)).toHaveAttribute(
      "data-attention-id",
      "direct:older",
    );
  });
});
