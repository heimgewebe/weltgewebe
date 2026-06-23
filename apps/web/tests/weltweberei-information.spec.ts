import { expect, test, type Request } from "@playwright/test";

/**
 * Browser proof for the static Weltweberei information surface
 * (apps/web/static/weltweberei/ -> apps/web/build/weltweberei/).
 *
 * The surface is a raw static HTML artifact served verbatim by the preview
 * server. It must not load JavaScript, forms, frames, trackers or any foreign
 * origin, and must expose stable machine markers. These assertions operate on
 * the DOM, the network log and the layout — not on screenshots.
 */

const SURFACE_PATH = "/weltweberei/";
const WELTGEWEBE_LINK = "https://weltgewebe.net/";

// Known legacy contact strings that must never reach the public artifact.
const FORBIDDEN_CONTACT = [
  "kontakt@weltweberei.org",
  "@weltweberei.org",
  "mailto:",
  "tel:",
];

test.describe("weltweberei information surface", () => {
  test("is served, self-contained and accessible", async ({
    page,
  }, testInfo) => {
    const requests: Request[] = [];
    page.on("request", (req) => requests.push(req));

    const response = await page.goto(SURFACE_PATH, { waitUntil: "load" });

    // 1./2. The built page is reachable and the response is successful.
    expect(response, "navigation produced a response").not.toBeNull();
    expect(response!.ok(), "response status is 2xx").toBeTruthy();

    const pageOrigin = new URL(page.url()).origin;

    // 3. Document title is correct.
    await expect(page).toHaveTitle("Weltweberei – Konzept und Weltgewebe");

    // 4. Exactly one visible main heading containing "Weltweberei".
    const headings = page.locator("h1");
    await expect(headings).toHaveCount(1);
    await expect(headings.first()).toBeVisible();
    await expect(headings.first()).toContainText("Weltweberei");

    // 5. Machine marker meta tag present.
    await expect(
      page.locator('meta[name="weltgewebe-surface"]'),
    ).toHaveAttribute("content", "weltweberei-info-v1");

    // 6. DOM surface marker present.
    await expect(page.locator("main")).toHaveAttribute(
      "data-surface",
      "weltweberei-info-v1",
    );

    // 7. Visible link to weltgewebe.net.
    const link = page.locator(`a[href="${WELTGEWEBE_LINK}"]`);
    await expect(link).toHaveCount(1);
    await expect(link).toBeVisible();

    // 8. No active or embedded elements, no mailto/tel links.
    await expect(page.locator("script")).toHaveCount(0);
    await expect(page.locator("form")).toHaveCount(0);
    await expect(page.locator("iframe")).toHaveCount(0);
    await expect(page.locator('a[href^="mailto:"]')).toHaveCount(0);
    await expect(page.locator('a[href^="tel:"]')).toHaveCount(0);

    // 9./10. Every request stays on the local preview origin (no foreign origin,
    // no CDN). data: URLs are inert and therefore tolerated.
    for (const req of requests) {
      const url = req.url();
      if (url.startsWith("data:")) continue;
      expect(new URL(url).origin, `request to unexpected origin: ${url}`).toBe(
        pageOrigin,
      );
    }

    // The stylesheet specifically must come from the local origin.
    const cssRequests = requests.filter((r) => r.url().endsWith(".css"));
    expect(cssRequests.length, "stylesheet was requested").toBeGreaterThan(0);
    for (const r of cssRequests) {
      expect(new URL(r.url()).origin).toBe(pageOrigin);
    }

    // 14. No known legacy private/contact data leaked into the artifact.
    const html = await page.content();
    for (const needle of FORBIDDEN_CONTACT) {
      expect(html, `artifact must not contain "${needle}"`).not.toContain(
        needle,
      );
    }

    // 11. No horizontal overflow on a narrow viewport.
    await page.setViewportSize({ width: 320, height: 640 });
    const overflow = await page.evaluate(
      () =>
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
    );
    expect(overflow, "no horizontal overflow at 320px").toBeLessThanOrEqual(0);

    // 12. The main link is reachable via keyboard.
    await page.keyboard.press("Tab");
    const focusedHref = await page.evaluate(
      () => (document.activeElement as HTMLAnchorElement | null)?.href ?? null,
    );
    expect(focusedHref, "first Tab focuses the main link").toBe(
      WELTGEWEBE_LINK,
    );

    // 13. The keyboard-focused link has a visible focus indicator.
    const outline = await link.evaluate((el) => {
      const style = getComputedStyle(el);
      return {
        width: parseFloat(style.outlineWidth || "0"),
        styleName: style.outlineStyle,
      };
    });
    expect(
      outline.width > 0 && outline.styleName !== "none",
      "focus indicator is visible",
    ).toBeTruthy();

    testInfo.annotations.push({
      type: "surface",
      description: "weltweberei-info-v1",
    });
  });
});
