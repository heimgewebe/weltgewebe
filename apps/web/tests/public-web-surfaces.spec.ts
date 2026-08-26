import { expect, test } from "@playwright/test";

function pngDimensions(bytes: Buffer): { width: number; height: number } {
  const signature = bytes.subarray(0, 8).toString("hex");
  expect(signature).toBe("89504e470d0a1a0a");
  return {
    width: bytes.readUInt32BE(16),
    height: bytes.readUInt32BE(20),
  };
}

test.describe("public web truth", () => {
  test("declares German language and global metadata", async ({ page }) => {
    await page.goto("/map");
    await expect(page.locator("html")).toHaveAttribute("lang", "de");
    await expect(page).toHaveTitle(/commonThing/);
    await expect(page.locator('meta[name="description"]')).toHaveAttribute(
      "content",
      /Commons/,
    );
    await expect(page.locator('link[rel="manifest"]')).toHaveAttribute(
      "href",
      "/manifest.webmanifest",
    );
  });

  test("serves a real imprint page", async ({ page }) => {
    await page.goto("/impressum");
    await expect(
      page.getByRole("heading", { name: "Impressum", level: 1 }),
    ).toBeVisible();
    await expect(page.getByText("Alexander Mohr")).toBeVisible();
    await expect(page.getByRole("link", { name: "kontakt@weltgewebe.net" })).toBeVisible();
    await expect(page).toHaveTitle("Impressum – commonThing");
  });

  test("serves a real privacy page", async ({ page }) => {
    await page.goto("/datenschutz");
    await expect(
      page.getByRole("heading", { name: "Datenschutzerklärung", level: 1 }),
    ).toBeVisible();
    await expect(page.getByText(/kein.*Werbung/i)).toBeVisible();
    await expect(page.getByRole("link", { name: "kontakt@weltgewebe.net" }).first()).toBeVisible();
    await expect(page).toHaveTitle("Datenschutz – commonThing");
  });

  test("serves origin-consistent crawler discovery files", async ({
    request,
  }) => {
    const robots = await request.get("/robots.txt");
    expect(robots.ok()).toBeTruthy();
    expect(robots.headers()["content-type"]).toContain("text/plain");

    const robotsText = await robots.text();
    expect(robotsText).toMatch(/^Disallow: \/api\/$/m);
    expect(robotsText).toMatch(/^Disallow: \/\*\?noinert=$/m);

    const sitemapDeclaration = robotsText.match(
      /^Sitemap: (https?:\/\/\S+\/sitemap\.xml)$/m,
    );
    expect(sitemapDeclaration).not.toBeNull();
    const publicOrigin = new URL(sitemapDeclaration![1]).origin;

    const sitemap = await request.get("/sitemap.xml");
    expect(sitemap.ok()).toBeTruthy();
    expect(sitemap.headers()["content-type"]).toContain("xml");
    const sitemapText = await sitemap.text();
    expect(sitemapText).toContain(`${publicOrigin}/map`);
    expect(sitemapText).toContain(`${publicOrigin}/impressum`);
    expect(sitemapText).toContain(`${publicOrigin}/datenschutz`);
  });

  test("serves a manifest with exact PNG fallbacks", async ({ request }) => {
    const manifest = await request.get("/manifest.webmanifest");
    expect(manifest.ok()).toBeTruthy();
    const data = await manifest.json();
    expect(data).toMatchObject({
      name: "commonThing",
      short_name: "commonThing",
      lang: "de",
      start_url: "/map",
      icons: expect.arrayContaining([
        expect.objectContaining({
          src: "/icon-192.png",
          sizes: "192x192",
          type: "image/png",
        }),
        expect.objectContaining({
          src: "/icon-512.png",
          sizes: "512x512",
          type: "image/png",
        }),
      ]),
    });

    for (const size of [192, 512]) {
      const icon = await request.get(`/icon-${size}.png`);
      expect(icon.ok()).toBeTruthy();
      expect(icon.headers()["content-type"]).toContain("image/png");
      expect(pngDimensions(await icon.body())).toEqual({
        width: size,
        height: size,
      });
    }
  });
});
