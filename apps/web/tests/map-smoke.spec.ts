import { expect, test } from "@playwright/test";

test.describe("map route", () => {
  test.beforeEach(() => {
    // Map-data fetches can sometimes take slightly longer in CI containers.
    test.setTimeout(15_000);
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
    await expect(strukturknotenButton).toBeVisible();
    await expect(strukturknotenButton).toBeDisabled();

    await expect(page.getByRole("button", { name: "Fäden" })).toBeVisible();
    await expect(
      page.getByRole("link", { name: /Archiv ansehen/i }),
    ).toHaveAttribute("href", "/archive/");
    await expect(page.getByRole("main")).toBeVisible();

    expect(consoleErrors, consoleErrors.join("\n")).toHaveLength(0);
    expect(pageErrors, pageErrors.join("\n")).toHaveLength(0);
  });
});
