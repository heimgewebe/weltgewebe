import { expect, test } from "@playwright/test";

test.describe("public web truth", () => {
  test("declares German language and global metadata", async ({ page }) => {
    await page.goto("/map");
    await expect(page.locator("html")).toHaveAttribute("lang", "de");
    await expect(page).toHaveTitle(/Weltgewebe/);
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
    await expect(page).toHaveTitle("Impressum – Weltgewebe");
  });

  test("serves a real privacy page", async ({ page }) => {
    await page.goto("/datenschutz");
    await expect(
      page.getByRole("heading", { name: "Datenschutzerklärung", level: 1 }),
    ).toBeVisible();
    await expect(page.getByText(/kein.*Werbung/i)).toBeVisible();
    await expect(page).toHaveTitle("Datenschutz – Weltgewebe");
  });

  test("serves machine-readable discovery files", async ({ request }) => {
    const robots = await request.get("/robots.txt");
    expect(robots.ok()).toBeTruthy();
    expect(await robots.text()).toContain(
      "Sitemap: https://weltgewebe.net/sitemap.xml",
    );

    const sitemap = await request.get("/sitemap.xml");
    expect(sitemap.ok()).toBeTruthy();
    expect(sitemap.headers()["content-type"]).toContain("xml");
    expect(await sitemap.text()).toContain("https://weltgewebe.net/impressum");

    const manifest = await request.get("/manifest.webmanifest");
    expect(manifest.ok()).toBeTruthy();
    const data = await manifest.json();
    expect(data).toMatchObject({
      name: "Weltgewebe",
      lang: "de",
      start_url: "/map",
    });
  });
});
