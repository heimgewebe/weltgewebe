import { test, expect } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test.describe("Topbar — guest role visibility", () => {
  test("an authenticated guest sees a Gast badge that links to the Weber application", async ({
    page,
  }) => {
    await mockApiResponses(page, {
      auth: { authenticated: true, account_id: "guest-topbar", role: "gast" },
    });
    await page.goto("/map");

    const badge = page.getByTestId("topbar-guest-badge");
    await expect(badge).toBeVisible();
    await expect(badge).toHaveAttribute("href", "/antraege#antrag-stellen");
    await expect(badge).toContainText("Gast");

    const box = await badge.boundingBox();
    expect(box, "guest badge has no visible box").not.toBeNull();
    expect(box!.height).toBeGreaterThanOrEqual(44);

    await expect(
      page.getByRole("link", { name: "Private Nachrichten" }),
    ).toBeVisible();

    await badge.click();
    await expect(page).toHaveURL(/\/antraege#antrag-stellen$/);
    await expect(
      page.getByRole("heading", { name: "Weberstatus beantragen" }),
    ).toBeVisible();
  });

  test("the guest badge stays reachable and preserves the messages entry on a 320 pixel viewport", async ({
    page,
  }) => {
    await mockApiResponses(page, {
      auth: { authenticated: true, account_id: "guest-topbar", role: "gast" },
    });
    await page.setViewportSize({ width: 320, height: 568 });
    await page.goto("/map");

    const badge = page.getByTestId("topbar-guest-badge");
    await expect(badge).toBeVisible();
    const box = await badge.boundingBox();
    expect(box, "guest badge has no visible box").not.toBeNull();
    expect(box!.height).toBeGreaterThanOrEqual(44);
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(320);

    await expect(
      page.getByRole("link", { name: "Private Nachrichten" }),
    ).toBeVisible();
  });

  test("a weber does not see the guest badge", async ({ page }) => {
    await mockApiResponses(page, {
      auth: {
        authenticated: true,
        account_id: "weber-topbar",
        role: "weber",
      },
    });
    await page.goto("/map");

    await expect(
      page.getByRole("link", { name: "Private Nachrichten" }),
    ).toBeVisible();
    await expect(page.getByTestId("topbar-guest-badge")).toHaveCount(0);
  });

  test("an anonymous visitor does not see the guest badge", async ({
    page,
  }) => {
    await mockApiResponses(page, { auth: { authenticated: false } });
    await page.goto("/map");

    await expect(page.getByRole("link", { name: "Anmelden" })).toBeVisible();
    await expect(page.getByTestId("topbar-guest-badge")).toHaveCount(0);
  });
});
