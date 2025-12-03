import { expect, test } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test.describe("map route", () => {
  test.beforeEach(async ({ page }) => {
    // Map-data fetches can sometimes take slightly longer in CI containers.
    test.setTimeout(15_000);
    // Mock API responses to avoid needing a running backend
    await mockApiResponses(page);
  });

  test("shows structure layer controls", async ({ page }) => {
    const consoleErrors: string[] = [];
    const pageErrors: string[] = [];

    page.on("console", (message) => {
      if (message.type() === "error") {
        consoleErrors.push(message.text());
      }
    });
    page.on("pageerror", (error) => {
      pageErrors.push(error.message ?? String(error));
    });

    await page.goto("/map", { waitUntil: "domcontentloaded" });
    await page.waitForLoadState("networkidle");

    const strukturknotenButton = page.getByRole("button", {
      name: "Strukturknoten",
    });
    await expect.poll(async () => strukturknotenButton.isVisible()).toBe(true);
    await expect(strukturknotenButton).toBeDisabled();

    const faedenButton = page.getByRole("button", { name: "Fäden" });
    await expect.poll(async () => faedenButton.isVisible()).toBe(true);
    await expect(
      page.getByRole("link", { name: /Archiv ansehen/i }),
    ).toHaveAttribute("href", "/archive/");
    await expect(page.getByRole("main")).toBeVisible();

    expect(consoleErrors, consoleErrors.join("\n")).toHaveLength(0);
    expect(pageErrors, pageErrors.join("\n")).toHaveLength(0);
  });

  test("loads markers from API", async ({ page }) => {
    // Intercept the API call to return a specific known marker
    await page.route("**/api/nodes", async (route) => {
      const json = [
        {
          id: "test-marker-1",
          kind: "Ort",
          title: "API Marker Test",
          created_at: "2025-01-01T12:00:00Z",
          updated_at: "2025-11-01T09:00:00Z",
          location: { lon: 10.05, lat: 53.55 },
        },
      ];
      await route.fulfill({ json });
    });

    await page.goto("/map", { waitUntil: "domcontentloaded" });

    // We don't strictly wait for networkidle because we want to see if the element appears
    // But since the map renders asynchronously, we might need to wait a bit.

    // Check if the marker is present
    // The current implementation sets aria-label and title to item.title
    const marker = page.locator('.map-marker[aria-label="API Marker Test"]');

    // This assertion should fail if the app uses dummy data (which doesn't have "API Marker Test")
    await expect(marker).toBeVisible({ timeout: 5000 });
  });
});
