import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    (window as any).__E2E__ = true;
    (window as any).__FORCE_INERT_POLYFILL__ = true;
    (window as any).__POLYFILL_CLICKED__ = false;
  });
  await page.goto("/");
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
  await expect(child).toHaveAttribute("aria-hidden", "true");

  await child.click({ force: true });
  await expect
    .poll(async () =>
      page.evaluate(() => Boolean((window as any).__POLYFILL_CLICKED__)),
    )
    .toBe(false);

  await page.evaluate(() => {
    (window as any).__POLYFILL_CLICKED__ = false;
    document.getElementById("polyfill-host")?.removeAttribute("inert");
  });

  await child.waitFor({ state: "visible" });
  await expect(child).not.toHaveAttribute("aria-hidden", "true");

  await child.click({ force: true });
  await expect
    .poll(async () =>
      page.evaluate(() => Boolean((window as any).__POLYFILL_CLICKED__)),
    )
    .toBe(true);
});
