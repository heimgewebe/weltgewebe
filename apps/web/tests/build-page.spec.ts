import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

test.describe("Build diagnostics page", () => {
  let localVersion = "unknown";

  test.beforeAll(() => {
    const versionFilePath = path.resolve(
      process.cwd(),
      "src/lib/generated/buildVersion.json",
    );
    if (fs.existsSync(versionFilePath)) {
      const data = JSON.parse(fs.readFileSync(versionFilePath, "utf8"));
      localVersion = data.version;
    }
  });

  test("shows in-sync state when server version matches local bundle", async ({
    page,
  }) => {
    await page.route("**/_app/version.json", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          version: localVersion,
          build_id: `${localVersion}-test`,
          built_at: "2026-05-08T10:00:00Z",
        }),
      });
    });

    await page.goto("/build");

    await expect(
      page.locator('[data-testid="build-local-version"]'),
    ).toHaveText(localVersion);
    await expect(
      page.locator('[data-testid="build-server-version"]'),
    ).toHaveText(localVersion);
    await expect(
      page.locator('[data-testid="build-sync-state"]'),
    ).toContainText("stimmen überein");
  });

  test("shows mismatch state when server version differs from bundle", async ({
    page,
  }) => {
    await page.route("**/_app/version.json", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          version: "different-server-version",
          build_id: "different-server-version-test",
          built_at: "2026-05-08T11:00:00Z",
        }),
      });
    });

    await page.goto("/build");

    await expect(
      page.locator('[data-testid="build-server-version"]'),
    ).toHaveText("different-server-version");
    await expect(
      page.locator('[data-testid="build-sync-state"]'),
    ).toContainText("unterscheiden sich");
  });

  test("shows unreachable state when version.json fetch fails", async ({
    page,
  }) => {
    await page.route("**/_app/version.json", async (route) => {
      await route.fulfill({ status: 500, body: "Internal Server Error" });
    });

    await page.goto("/build");

    await expect(
      page.locator('[data-testid="build-server-status"]'),
    ).toContainText("nicht erreichbar");
    await expect(
      page.locator('[data-testid="build-sync-state"]'),
    ).toContainText("Abgleich nicht möglich");
  });

  test("shows invalid state when payload has no version field", async ({
    page,
  }) => {
    await page.route("**/_app/version.json", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ release: "1.0.0" }),
      });
    });

    await page.goto("/build");

    await expect(
      page.locator('[data-testid="build-server-status"]'),
    ).toContainText("ohne brauchbare");
    await expect(
      page.locator('[data-testid="build-sync-state"]'),
    ).toContainText("Abgleich nicht möglich");
  });

  test("refresh button re-queries the server", async ({ page }) => {
    let calls = 0;
    await page.route("**/_app/version.json", async (route) => {
      calls += 1;
      const version = calls === 1 ? localVersion : "fresh-server-version";
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ version }),
      });
    });

    await page.goto("/build");
    await expect(
      page.locator('[data-testid="build-server-version"]'),
    ).toHaveText(localVersion);

    await page.locator('[data-testid="build-refresh"]').click();
    await expect(
      page.locator('[data-testid="build-server-version"]'),
    ).toHaveText("fresh-server-version");
  });
});
