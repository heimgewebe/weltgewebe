import { expect, test, type Request, type Response } from "@playwright/test";

/**
 * Browser proof for the static Weltweberei information surface
 * (apps/web/static/weltweberei/ -> apps/web/build/weltweberei/).
 *
 * The surface is a raw static HTML artifact served verbatim by the preview
 * server. It must not load JavaScript, forms, frames, trackers or any foreign
 * origin, and must expose stable machine markers. Before the operational and
 * legal activation gate it must also stay non-indexable and must not publish a
 * canonical link to the target domain. These assertions operate on the DOM,
 * the network log and the layout — not on screenshots.
 */

const SURFACE_PATH = "/weltweberei/";
const WELTGEWEBE_LINK = "https://weltgewebe.net/";

// Known legacy contact strings that must never reach the public artifact.
// This is a targeted contact-channel guard, not a general PII scanner.
const FORBIDDEN_CONTACT = [
  "kontakt@weltweberei.org",
  "@weltweberei.org",
  "mailto:",
  "tel:",
];

type Rgb = [number, number, number];

function parseRgb(value: string): Rgb {
  const match = value.match(/^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/);

  if (!match) {
    throw new Error(`unsupported CSS color: ${value}`);
  }

  return [Number(match[1]), Number(match[2]), Number(match[3])];
}

function relativeLuminance([red, green, blue]: Rgb): number {
  const channels = [red, green, blue].map((channel) => {
    const normalized = channel / 255;

    return normalized <= 0.04045
      ? normalized / 12.92
      : ((normalized + 0.055) / 1.055) ** 2.4;
  });

  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}

function contrastRatio(first: Rgb, second: Rgb): number {
  const firstLuminance = relativeLuminance(first);
  const secondLuminance = relativeLuminance(second);

  const lighter = Math.max(firstLuminance, secondLuminance);
  const darker = Math.min(firstLuminance, secondLuminance);

  return (lighter + 0.05) / (darker + 0.05);
}

test.describe("weltweberei information surface", () => {
  test("is served, self-contained and accessible", async ({
    page,
  }, testInfo) => {
    const requests: Request[] = [];
    const stylesheetResponses: Response[] = [];

    page.on("request", (request) => requests.push(request));
    page.on("response", (response) => {
      if (new URL(response.url()).pathname.endsWith("/styles.css")) {
        stylesheetResponses.push(response);
      }
    });

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
    await expect(page.locator("object")).toHaveCount(0);
    await expect(page.locator("embed")).toHaveCount(0);
    await expect(page.locator('a[href^="mailto:"]')).toHaveCount(0);
    await expect(page.locator('a[href^="tel:"]')).toHaveCount(0);
    await expect(page.locator('a[href^="javascript:" i]')).toHaveCount(0);
    await expect(page.locator('meta[http-equiv="refresh" i]')).toHaveCount(0);

    // 8b. No inline event handlers anywhere in the DOM.
    const inlineEventHandlers = await page
      .locator("*")
      .evaluateAll((elements) =>
        elements.flatMap((element) =>
          [...element.attributes]
            .filter((attribute) =>
              attribute.name.toLowerCase().startsWith("on"),
            )
            .map((attribute) => `${element.tagName}:${attribute.name}`),
        ),
      );
    expect(inlineEventHandlers, "no inline event handlers").toEqual([]);

    // 9./10. Every request stays on the local preview origin (no foreign origin,
    // no CDN). data: URLs are inert and therefore tolerated.
    for (const req of requests) {
      const url = req.url();
      if (url.startsWith("data:")) continue;
      expect(new URL(url).origin, `request to unexpected origin: ${url}`).toBe(
        pageOrigin,
      );
    }

    // The stylesheet must be present exactly once, requested locally, and must
    // be answered successfully with a CSS content type — a 404 must fail here.
    const stylesheet = page.locator('link[rel="stylesheet"]');
    await expect(stylesheet).toHaveCount(1);
    await expect(stylesheet).toHaveAttribute("href", "styles.css");
    await expect(page.locator("base")).toHaveCount(0);

    expect(stylesheetResponses, "exactly one stylesheet response").toHaveLength(
      1,
    );

    const stylesheetResponse = stylesheetResponses[0];

    expect(
      new URL(stylesheetResponse.url()).origin,
      "stylesheet stays on preview origin",
    ).toBe(pageOrigin);

    expect(
      stylesheetResponse.ok(),
      "stylesheet response is successful",
    ).toBeTruthy();

    expect(
      stylesheetResponse.headers()["content-type"] ?? "",
      "stylesheet content type",
    ).toContain("text/css");

    // Pre-activation publication contract: not indexable, no canonical link to
    // the target domain until the activation gate is cleared.
    await expect(page.locator('meta[name="robots"]')).toHaveAttribute(
      "content",
      "noindex, nofollow",
    );
    await expect(page.locator('link[rel="canonical"]')).toHaveCount(0);

    // 14. No known legacy private/contact data leaked into the artifact.
    const html = await page.content();
    for (const needle of FORBIDDEN_CONTACT) {
      expect(html, `artifact must not contain "${needle}"`).not.toContain(
        needle,
      );
    }
    expect(html, "artifact contains no email address").not.toMatch(
      /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/i,
    );

    // 11. No horizontal overflow on a narrow viewport.
    await page.setViewportSize({ width: 320, height: 640 });
    const overflow = await page.evaluate(
      () =>
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
    );
    expect(overflow, "no horizontal overflow at 320px").toBeLessThanOrEqual(0);

    // 12. The main link is reachable via real keyboard navigation.
    await page.keyboard.press("Tab");
    await expect(link).toBeFocused();

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

    // 13b. The focus outline keeps sufficient contrast against both the card
    // surface and the page background.
    const focusColors = await link.evaluate((element) => {
      const linkStyle = getComputedStyle(element);
      const surface = element.closest(".surface");

      if (!surface) {
        throw new Error("surface container missing");
      }

      return {
        outline: linkStyle.outlineColor,
        surface: getComputedStyle(surface).backgroundColor,
        body: getComputedStyle(document.body).backgroundColor,
      };
    });

    const outlineColor = parseRgb(focusColors.outline);
    const surfaceColor = parseRgb(focusColors.surface);
    const bodyColor = parseRgb(focusColors.body);

    expect(
      contrastRatio(outlineColor, surfaceColor),
      "focus outline contrast against surface",
    ).toBeGreaterThanOrEqual(3);

    expect(
      contrastRatio(outlineColor, bodyColor),
      "focus outline contrast against page background",
    ).toBeGreaterThanOrEqual(3);

    testInfo.annotations.push({
      type: "surface",
      description: "weltweberei-info-v1",
    });
  });
});
