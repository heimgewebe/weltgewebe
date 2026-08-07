import { devices, expect, test } from "@playwright/test";
import { getGarnrolleMarkerScale } from "../src/lib/map/markerScale";
import { mockApiResponses } from "./fixtures/mockApi";

const GARNROLLE_ID = "7d97a42e-3704-4a33-a61f-0e0a6b4d65d8";
const KNOTEN_ID = "b52be17c-4ab7-4434-98ce-520f86290cf0";
const IPAD_PRO_11_LANDSCAPE = {
  userAgent: devices["iPad Pro 11 landscape"].userAgent,
  viewport: devices["iPad Pro 11 landscape"].viewport,
  deviceScaleFactor: devices["iPad Pro 11 landscape"].deviceScaleFactor,
  isMobile: devices["iPad Pro 11 landscape"].isMobile,
  hasTouch: devices["iPad Pro 11 landscape"].hasTouch,
};

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

  test("renders Knoten as woven bodies instead of generic dots", async ({
    page,
  }) => {
    const marker = page.getByTestId(`marker-node-${KNOTEN_ID}`);
    const visual = marker.locator(".marker-node__visual");
    const body = visual.locator(".woven-node");
    await expect(marker).toHaveCSS("outline-style", "none");
    await expect(marker).toHaveCSS("width", "44px");
    await expect(marker).toHaveCSS("height", "44px");
    await expect(visual).toHaveCSS("width", "46px");
    await expect(visual).toHaveCSS("height", "46px");
    await expect(visual).toHaveCSS("border-top-style", "none");
    await expect(body).toHaveCount(1);
    await expect(body).toHaveAttribute(
      "data-zone-order",
      "knotting,conversation,proposal,vote",
    );
    // X body is not a bullseye disc; no circular marker box.
    await expect(body).toHaveCSS("border-radius", "0px");
    await expect(body).toHaveCSS("background-color", "rgba(0, 0, 0, 0)");
    await expect(body.locator('[data-zone="knotting"]')).toHaveCount(1);
    await expect(body.locator('[data-zone="conversation"]')).toHaveCount(1);

    await expect(body).toHaveAttribute("data-x-geometry", "diagonal");
    const xGeometry = await body
      .locator(".woven-node__x")
      .evaluate((element) => {
        const arms = Array.from(
          element.querySelectorAll<HTMLElement>(".woven-node__arm"),
        ).map((arm) => {
          const style = getComputedStyle(arm);
          return {
            arm: arm.dataset.arm,
            transform: style.transform,
            width: Number.parseFloat(style.width),
            height: Number.parseFloat(style.height),
          };
        });
        const strands = Array.from(
          element.querySelectorAll<HTMLElement>(".woven-node__strand"),
        ).map((strand) => ({
          strand: strand.dataset.strand,
          zIndex: Number.parseInt(getComputedStyle(strand).zIndex, 10),
        }));
        return { arms, strands };
      });
    expect(xGeometry.arms.map((arm) => arm.arm).sort()).toEqual([
      "northeast",
      "northwest",
      "southeast",
      "southwest",
    ]);
    // Diagonal X: each arm is an elongated rotated band — never an axis-aligned plus.
    for (const arm of xGeometry.arms) {
      expect(arm.height).toBeGreaterThan(arm.width);
      expect(arm.transform).not.toBe("none");
      expect(arm.transform).toMatch(/matrix/);
    }
    const under = xGeometry.strands.find((strand) => strand.strand === "a");
    const over = xGeometry.strands.find((strand) => strand.strand === "b");
    expect(under && over).toBeTruthy();
    expect((over?.zIndex ?? 0) > (under?.zIndex ?? 0)).toBe(true);

    // No separate crossing blob: the four-arm X is the whole knot.
    await expect(body.locator(".woven-node__crossing")).toHaveCount(0);
    await expect(body.locator(".woven-node__cross")).toHaveCount(0);

    const halo = marker.locator(".map-marker__halo");
    await expect(halo).toHaveCSS("width", "68px");
    await marker.focus();
    await expect(halo).toHaveCSS("opacity", "1");
    const haloExtendsBeyondBody = await marker.evaluate((element) => {
      const haloBox = element
        .querySelector<HTMLElement>(".map-marker__halo")!
        .getBoundingClientRect();
      const bodyBox = element
        .querySelector<HTMLElement>(".marker-node__visual")!
        .getBoundingClientRect();
      return haloBox.width > bodyBox.width && haloBox.height > bodyBox.height;
    });
    expect(haloExtendsBeyondBody).toBe(true);
  });

  test("uses round textile haloes instead of rectangular marker and title boxes", async ({
    page,
  }) => {
    const marker = page.getByTestId(`marker-garnrolle-${GARNROLLE_ID}`);
    await expect(marker).toHaveClass(/is-selected/);
    await expect(marker).toHaveCSS("outline-style", "none");
    await expect(marker).toHaveCSS("box-shadow", "none");

    const halo = marker.locator(".map-marker__halo");
    await expect(halo).toHaveCount(1);
    await expect(halo).toHaveCSS("width", "42px");
    await expect(halo).toHaveCSS("height", "42px");
    await expect(halo).toHaveCSS("border-radius", "50%");
    await expect(halo).toHaveCSS("opacity", "1");

    const heading = page.getByTestId("account-heading");
    await expect(heading).toBeFocused();
    await expect(heading).toHaveCSS("outline-style", "none");
  });

  test("keeps the selected halo static when reduced motion is requested", async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.reload();

    const marker = page.getByTestId(`marker-garnrolle-${GARNROLLE_ID}`);
    const halo = marker.locator(".map-marker__halo");
    const icon = marker.locator(".marker-account__icon");
    await expect(halo).toHaveCSS("transition-duration", "0s");
    await expect(icon).toHaveCSS("transition-duration", "0s");
    await expect(halo).toHaveCSS("opacity", "1");
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
        // Center anchor: map coordinate is the geometric midpoint of the spool.
        const actualAnchor = {
          x: rect.left + rect.width / 2,
          y: rect.top + rect.height / 2,
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

  test("allows regional zoom-out while keeping the touch target stable", async ({
    page,
  }) => {
    const marker = page.getByTestId(`marker-garnrolle-${GARNROLLE_ID}`);
    await expect(marker).toBeVisible();

    const metrics = await page.evaluate(
      async ({ markerId }) => {
        type TestMap = {
          getMinZoom(): number;
          getZoom(): number;
          jumpTo(options: { zoom: number }): void;
        };
        const map = (window as typeof window & { __TEST_MAP__?: TestMap })
          .__TEST_MAP__;
        const markerElement = document.querySelector<HTMLElement>(
          `[data-testid="marker-garnrolle-${markerId}"]`,
        );
        const icon = markerElement?.querySelector<HTMLElement>(
          ".marker-account__icon",
        );
        if (!map || !markerElement || !icon) {
          throw new Error("test map or Garnrolle marker unavailable");
        }

        const settle = async () => {
          await new Promise((resolve) => setTimeout(resolve, 220));
          await new Promise<void>((resolve) =>
            requestAnimationFrame(() => resolve()),
          );
        };
        const measure = () => {
          const outer = markerElement.getBoundingClientRect();
          const visibleIcon = icon.getBoundingClientRect();
          const transform = new DOMMatrixReadOnly(
            getComputedStyle(icon).transform,
          );
          const outerCx = outer.left + outer.width / 2;
          const outerCy = outer.top + outer.height / 2;
          const iconCx = visibleIcon.left + visibleIcon.width / 2;
          const iconCy = visibleIcon.top + visibleIcon.height / 2;
          return {
            zoom: map.getZoom(),
            outerWidth: outer.width,
            outerHeight: outer.height,
            visualWidth: visibleIcon.width,
            visualHeight: visibleIcon.height,
            transformScaleX: transform.a,
            transformScaleY: transform.d,
            // Center-origin scale: icon midpoint stays on the geographic pin.
            centerDelta: Math.hypot(outerCx - iconCx, outerCy - iconCy),
          };
        };

        map.jumpTo({ zoom: 13 });
        await settle();
        const local = measure();

        map.jumpTo({ zoom: 7 });
        await settle();
        const regional = measure();

        return { minZoom: map.getMinZoom(), local, regional };
      },
      { markerId: GARNROLLE_ID },
    );

    expect(metrics.minZoom).toBe(7);
    expect(metrics.local.zoom).toBeCloseTo(13, 5);
    expect(metrics.regional.zoom).toBeCloseTo(7, 5);
    for (const stage of [metrics.local, metrics.regional]) {
      expect(stage.outerWidth).toBeGreaterThanOrEqual(43.9);
      expect(stage.outerWidth).toBeLessThanOrEqual(44.1);
      expect(stage.outerHeight).toBeGreaterThanOrEqual(43.9);
      expect(stage.outerHeight).toBeLessThanOrEqual(44.1);
    }
    expect(metrics.local.transformScaleX).toBeGreaterThanOrEqual(0.995);
    expect(metrics.local.transformScaleX).toBeLessThanOrEqual(1.005);
    expect(metrics.local.transformScaleY).toBeGreaterThanOrEqual(0.995);
    expect(metrics.local.transformScaleY).toBeLessThanOrEqual(1.005);
    // Fachlicher Zoom-Vertrag: regional scale tracks getGarnrolleMarkerScale.
    // Subpixel matrix readout may drift slightly across engines/devices.
    const expectedRegional = getGarnrolleMarkerScale(metrics.regional.zoom);
    expect(metrics.regional.transformScaleX).toBeCloseTo(expectedRegional, 2);
    expect(metrics.regional.transformScaleY).toBeCloseTo(expectedRegional, 2);
    const widthRatio = metrics.regional.visualWidth / metrics.local.visualWidth;
    expect(widthRatio).toBeGreaterThanOrEqual(0.62);
    expect(widthRatio).toBeLessThanOrEqual(0.68);
    expect(
      Math.abs(metrics.regional.visualWidth - metrics.regional.visualHeight),
    ).toBeLessThanOrEqual(0.25);
    expect(metrics.local.centerDelta).toBeLessThanOrEqual(0.5);
    expect(metrics.regional.centerDelta).toBeLessThanOrEqual(0.5);
  });
});

test.describe("iPad Pro 11 landscape Garnrolle interaction", () => {
  test.use(IPAD_PRO_11_LANDSCAPE);

  test("keeps the touch target invisible and the selected state circular", async ({
    page,
  }) => {
    await mockApiResponses(page);
    await page.goto("/map");

    const marker = page.getByTestId(`marker-garnrolle-${GARNROLLE_ID}`);
    await expect(marker).toBeVisible();
    await expect(marker).toHaveCSS("width", "44px");
    await expect(marker).toHaveCSS("height", "44px");
    await expect(marker).toHaveCSS("outline-style", "none");
    await expect(marker).toHaveCSS("box-shadow", "none");

    await marker.tap();
    await expect(page.getByTestId("account-heading")).toBeVisible();
    await expect(marker).toHaveClass(/is-selected/);

    const halo = marker.locator(".map-marker__halo");
    await expect(halo).toHaveCSS("border-radius", "50%");
    await expect(halo).toHaveCSS("opacity", "1");

    const hasHorizontalOverflow = await page.evaluate(
      () =>
        document.documentElement.scrollWidth >
        document.documentElement.clientWidth,
    );
    expect(hasHorizontalOverflow).toBe(false);
  });
});
