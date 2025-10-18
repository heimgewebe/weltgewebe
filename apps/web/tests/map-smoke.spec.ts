import { expect, test } from "@playwright/test";

test.describe("map route", () => {
  test("shows structure layer controls", async ({ page }) => {
    await page.goto("/map");

    const strukturknotenButton = page.getByRole("button", { name: "Strukturknoten" });
    await expect(strukturknotenButton).toBeVisible();
    await expect(strukturknotenButton).toBeDisabled();

    await expect(page.getByRole("button", { name: "Fäden" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Archiv ansehen" })).toHaveAttribute("href", "/archive/");
  });
});
