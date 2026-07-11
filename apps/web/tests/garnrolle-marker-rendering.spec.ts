import { expect, test } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

const GARNROLLE_ID = "7d97a42e-3704-4a33-a61f-0e0a6b4d65d8";

test.describe("Garnrolle marker rendering", () => {
  test.beforeEach(async ({ page }) => {
    await mockApiResponses(page);
    await page.goto(`/map?focus=garnrolle:${GARNROLLE_ID}`);
  });

  test("uses a reset button and a loaded intrinsic image", async ({ page }) => {
    const marker = page.getByTestId(`marker-garnrolle-${GARNROLLE_ID}`);
    await expect(marker).toBeVisible();
    await expect(marker).toHaveCSS("appearance", "none");
    await expect(marker).toHaveCSS("padding", "0px");
    await expect(marker).toHaveCSS("width", "44px");
    await expect(marker).toHaveCSS("height", "44px");
    await expect(marker).toHaveCSS("background-image", "none");

    const icon = marker.locator("img.marker-account__icon");
    await expect(icon).toHaveCount(1);
    await expect(icon).toHaveAttribute("alt", "");
    await expect(icon).toHaveAttribute("aria-hidden", "true");
    await expect(icon).toHaveJSProperty("complete", true);
    await expect(icon).toHaveJSProperty("naturalWidth", 256);
    await expect(icon).toHaveJSProperty("naturalHeight", 255);
    await expect(icon).toHaveCSS("width", "44px");
    await expect(icon).toHaveCSS("height", "44px");
    await expect(icon).toHaveCSS("object-fit", "contain");
  });
});
