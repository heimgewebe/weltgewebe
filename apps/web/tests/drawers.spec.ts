import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  // Maus-Swipes in Tests erlauben
  await page.addInitScript(() => {
    (window as any).__E2E__ = true;
  });
  await page.goto("/map?l=0&r=0&t=0", { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle");
  await page.waitForSelector("#map");
});

test("Esc schließt geöffnete Drawer (top → right → left)", async ({ page }) => {
  const filterDrawer = page.locator("#filter-drawer");
  const accountDrawer = page.locator("#account-drawer");
  const leftStack = page.locator("#left-stack");

  // Rechts öffnen
  await page.keyboard.press("]");
  await expect(filterDrawer).toHaveAttribute("aria-hidden", "false");

  // Esc → schließt rechts
  await page.keyboard.press("Escape");
  await expect(filterDrawer).toHaveAttribute("aria-hidden", "true");

  // Top öffnen
  await page.keyboard.press("Alt+g");
  await expect(accountDrawer).toHaveAttribute("aria-hidden", "false");

  // Esc → schließt top
  await page.keyboard.press("Escape");
  await expect(accountDrawer).toHaveAttribute("aria-hidden", "true");

  // Links öffnen
  await page.keyboard.press("[");
  await expect(leftStack).toHaveAttribute("aria-hidden", "false");

  // Esc → schließt links (Stack)
  await page.keyboard.press("Escape");
  await expect(leftStack).toHaveAttribute("aria-hidden", "true");
});

test("Swipe öffnet & schließt Drawer symmetrisch", async ({ page }) => {
  const map = page.locator("#map");
  const filterDrawer = page.locator("#filter-drawer");
  const accountDrawer = page.locator("#account-drawer");
  const leftStack = page.locator("#left-stack");

  // Linke Kante öffnen (drag→ rechts)
  const box = await map.boundingBox();
  if (!box) throw new Error("map not visible");
  const y = box.y + box.height * 0.5;

  // open left
  await page.mouse.move(box.x + 40, y);
  await page.mouse.down();
  await page.mouse.move(box.x + 120, y, { steps: 6 });
  await page.mouse.up();
  await expect(leftStack).toHaveAttribute("aria-hidden", "false");

  // close left (drag ←)
  await page.mouse.move(box.x + 140, y);
  await page.mouse.down();
  await page.mouse.move(box.x + 30, y, { steps: 6 });
  await page.mouse.up();
  await expect(leftStack).toHaveAttribute("aria-hidden", "true");

  // open right (drag ← an rechter Kante)
  const rx = box.x + box.width - 40;
  await page.mouse.move(rx, y);
  await page.mouse.down();
  await page.mouse.move(rx - 100, y, { steps: 6 });
  await page.mouse.up();
  await expect(filterDrawer).toHaveAttribute("aria-hidden", "false");

  // close right (drag →)
  await page.mouse.move(rx - 120, y);
  await page.mouse.down();
  await page.mouse.move(rx + 20, y, { steps: 6 });
  await page.mouse.up();
  await expect(filterDrawer).toHaveAttribute("aria-hidden", "true");

  // open top (drag ↓ nahe Top)
  const tx = box.x + box.width * 0.5;
  const ty = box.y + 40;
  await page.mouse.move(tx, ty);
  await page.mouse.down();
  await page.mouse.move(tx, ty + 120, { steps: 6 });
  await page.mouse.up();
  await expect(accountDrawer).toHaveAttribute("aria-hidden", "false");

  // close top (drag ↑)
  await page.mouse.move(tx, ty + 140);
  await page.mouse.down();
  await page.mouse.move(tx, ty - 10, { steps: 6 });
  await page.mouse.up();
  await expect(accountDrawer).toHaveAttribute("aria-hidden", "true");
});
