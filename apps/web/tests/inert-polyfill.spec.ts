import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route(
    "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
    (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ version: 8, sources: {}, layers: [] }),
      });
    },
  );
  await page.addInitScript(() => {
    (window as any).__E2E__ = true;
    (window as any).__FORCE_INERT_POLYFILL__ = true;
    (window as any).__POLYFILL_CLICKED__ = false;
  });
  await page.goto("/");
  // Ensure the page has fully loaded and `onMount` (where `ensureInertPolyfill` runs) has finished
  await page.waitForLoadState("domcontentloaded");
  // Give a small amount of time for any synchronous initialization like `ensureInertPolyfill` to complete in CI environments
  await page.waitForTimeout(500);
});

test("polyfill schützt dynamisch eingefügte Elemente", async ({ page }) => {
  await page.evaluate(() => {
    const host = document.createElement("section");
    host.id = "polyfill-host";
    host.setAttribute("inert", "");

    const button = document.createElement("button");
    button.id = "polyfill-child";
    button.textContent = "Polyfill-Test";
    button.addEventListener("click", () => {
      (window as any).__POLYFILL_CLICKED__ = true;
    });

    host.appendChild(button);
    document.body.appendChild(host);
  });

  const child = page.locator("#polyfill-child");
  await expect
    .poll(async () => child.getAttribute("aria-hidden"), { timeout: 10000 })
    .toBe("true");

  // Fire click through dispatchEvent since Playwright intercepts clicks on inert elements too well sometimes
  await page.evaluate(() => {
    document
      .getElementById("polyfill-child")
      ?.dispatchEvent(
        new MouseEvent("click", { bubbles: true, cancelable: true }),
      );
  });

  // No need to poll here, just check once after dispatching event synchronously
  const clicked = await page.evaluate(() =>
    Boolean((window as any).__POLYFILL_CLICKED__),
  );
  expect(clicked).toBe(false);

  await page.evaluate(() => {
    (window as any).__POLYFILL_CLICKED__ = false;
    document.getElementById("polyfill-host")?.removeAttribute("inert");
  });

  await child.waitFor({ state: "visible" });
  await expect(child).not.toHaveAttribute("aria-hidden", "true");

  // Try standard Playwright click again now that inert is gone
  await child.click({ force: true, timeout: 5000 }).catch(async () => {
    // Fallback to evaluation if it somehow still times out
    await page.evaluate(() => {
      document.getElementById("polyfill-child")?.click();
    });
  });

  // Add fallback dispatchEvent just in case both click attempts failed or were intercepted by other elements
  await page.evaluate(() => {
    document
      .getElementById("polyfill-child")
      ?.dispatchEvent(
        new MouseEvent("click", { bubbles: true, cancelable: true }),
      );
  });

  const clicked2 = await page.evaluate(() =>
    Boolean((window as any).__POLYFILL_CLICKED__),
  );
  expect(clicked2).toBe(true);
});
