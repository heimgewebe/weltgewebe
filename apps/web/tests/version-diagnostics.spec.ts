import { test, expect } from "@playwright/test";

test.describe("Version Diagnostics", () => {
  test("displays canonical version and optional build_id when version.json is successfully fetched", async ({
    page,
  }) => {
    await page.route("**/_app/version.json", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          version: "abc1234",
          build_id: "abc1234-1742155012000",
          release: "1.2.0",
          built_at: "2026-03-15T12:00:00Z",
        }),
      });
    });

    await page.goto("/settings");
    await expect(page.locator('[data-testid="version-text"]')).toHaveText(
      "Release 1.2.0 · Version abc1234",
    );
    await expect(page.locator('[data-testid="version-meta"]')).toContainText(
      "(Build abc1234-1742155012000) · gebaut am 15.03.2026",
    );
  });

  test("displays fallback when version.json fetch fails", async ({ page }) => {
    await page.route("**/_app/version.json", async (route) => {
      await route.fulfill({
        status: 500,
        body: "Internal Server Error",
      });
    });

    await page.goto("/settings");
    await expect(page.locator('[data-testid="version-text"]')).toHaveText(
      "Version unbekannt",
    );
  });

  test("displays only version when release and build_id are missing", async ({
    page,
  }) => {
    await page.route("**/_app/version.json", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          version: "test-build-67890",
        }),
      });
    });

    await page.goto("/settings");
    await expect(page.locator('[data-testid="version-text"]')).toHaveText(
      "Version test-build-67890",
    );
    // The meta element should not be rendered if built_at and build_id are missing
    await expect(page.locator('[data-testid="version-meta"]')).toHaveCount(0);
  });

  test("remains stable and hides timestamp if built_at is invalid", async ({
    page,
  }) => {
    await page.route("**/_app/version.json", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          version: "test-build-invalid-date",
          built_at: "not-a-valid-date",
        }),
      });
    });

    await page.goto("/settings");
    await expect(page.locator('[data-testid="version-text"]')).toHaveText(
      "Version test-build-invalid-date",
    );
    await expect(page.locator('[data-testid="version-meta"]')).toHaveCount(0);
  });
});
