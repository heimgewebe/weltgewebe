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
    await expect(marker).toHaveCSS("transition-duration", "0s");

    const visual = marker.locator(".map-marker__visual");
    await expect(visual).toHaveCount(1);
    await expect(visual).toHaveCSS("transition-property", "transform");

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

  test("stays locked to its projected coordinate during a map jump", async ({
    page,
  }) => {
    const marker = page.getByTestId(`marker-garnrolle-${GARNROLLE_ID}`);
    await expect(marker).toBeVisible();

    await page.waitForFunction(() => {
      const map = (
        window as typeof window & { __TEST_MAP__?: { isMoving(): boolean } }
      ).__TEST_MAP__;
      return Boolean(map && !map.isMoving());
    });

    const errorPx = await page.evaluate(
      async ({ markerId }) => {
        const map = (
          window as typeof window & {
            __TEST_MAP__?: {
              getCenter(): { lng: number; lat: number };
              jumpTo(options: { center: [number, number] }): void;
              project(lngLat: [number, number]): { x: number; y: number };
            };
          }
        ).__TEST_MAP__;
        const markerElement = document.querySelector<HTMLElement>(
          `[data-testid="marker-garnrolle-${markerId}"]`,
        );
        if (!map || !markerElement) {
          throw new Error("test map or marker unavailable");
        }

        const center = map.getCenter();
        map.jumpTo({ center: [center.lng + 0.02, center.lat + 0.01] });

        // Two frames allow MapLibre to render the new camera position. A CSS
        // transition on the outer marker would still be visibly catching up.
        await new Promise<void>((resolve) =>
          requestAnimationFrame(() => resolve()),
        );
        await new Promise<void>((resolve) =>
          requestAnimationFrame(() => resolve()),
        );

        const projected = map.project([10.0629844, 53.5604148]);
        const rect = markerElement.getBoundingClientRect();
        const actualAnchor = {
          x: rect.left + rect.width / 2,
          y: rect.bottom,
        };
        return Math.hypot(
          actualAnchor.x - projected.x,
          actualAnchor.y - projected.y,
        );
      },
      { markerId: GARNROLLE_ID },
    );

    expect(errorPx).toBeLessThanOrEqual(2);
  });
});
