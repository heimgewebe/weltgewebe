import { expect, test } from "@playwright/test";

// Wait time for CSS transitions to complete (180ms transition + buffer)
const DRAWER_ANIMATION_WAIT = 500;

test.beforeEach(async ({ page }) => {
  // Maus-Swipes in Tests erlauben
  await page.addInitScript(() => {
    (window as any).__E2E__ = true;
  });
  await page.goto("/map?l=0&r=0&t=0", { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle");
  await page.waitForSelector("#map");
  // Wait for drawers to be rendered and initial state settled
  await expect(page.locator("#left-stack")).toBeAttached({ timeout: 5000 });
  await expect(page.locator("#filter-drawer")).toBeAttached({ timeout: 5000 });
  await expect(page.locator("#account-drawer")).toBeAttached({ timeout: 5000 });
});

test("Esc schließt geöffnete Drawer (top → right → left)", async ({ page }) => {
  const filterDrawer = page.locator("#filter-drawer");
  const accountDrawer = page.locator("#account-drawer");
  const leftStack = page.locator("#left-stack");

  await expect(filterDrawer).toHaveAttribute("aria-hidden", "true", {
    timeout: 2000,
  });
  await expect(accountDrawer).toHaveAttribute("aria-hidden", "true", {
    timeout: 2000,
  });
  await expect(leftStack).toHaveAttribute("aria-hidden", "true", {
    timeout: 2000,
  });

  // Rechts öffnen
  await page.keyboard.press("]");
  await expect(filterDrawer).toHaveAttribute("aria-hidden", "false", {
    timeout: 2000,
  });

  // Esc → schließt rechts
  await page.keyboard.press("Escape");
  await expect(filterDrawer).toHaveAttribute("aria-hidden", "true", {
    timeout: 2000,
  });

  // Top öffnen
  await page.keyboard.press("Alt+g");
  await expect(accountDrawer).toHaveAttribute("aria-hidden", "false", {
    timeout: 2000,
  });

  // Esc → schließt top
  await page.keyboard.press("Escape");
  await expect(accountDrawer).toHaveAttribute("aria-hidden", "true", {
    timeout: 2000,
  });

  // Links öffnen
  await page.keyboard.press("[");
  await expect(leftStack).toHaveAttribute("aria-hidden", "false", {
    timeout: 2000,
  });

  // Esc → schließt links (Stack)
  await page.keyboard.press("Escape");
  await expect(leftStack).toHaveAttribute("aria-hidden", "true", {
    timeout: 2000,
  });
});

test("Swipe öffnet & schließt Drawer symmetrisch", async ({ page }) => {
  const leftEdge = page.locator(".edge.left");
  const rightEdge = page.locator(".edge.right");
  const topEdge = page.locator(".edge.top");
  const filterDrawer = page.locator("#filter-drawer");
  const accountDrawer = page.locator("#account-drawer");
  const leftStack = page.locator("#left-stack");

  // Linke Kante öffnen (drag→ rechts)
  const leftEdgeBox = await leftEdge.boundingBox();
  if (!leftEdgeBox) throw new Error("left edge bounding box unavailable");
  const y = leftEdgeBox.y + leftEdgeBox.height * 0.5;

  // open left
  const leftEdgeX = leftEdgeBox.x + leftEdgeBox.width * 0.5;
  await page.mouse.move(leftEdgeX, y);
  await page.mouse.down();
  await page.mouse.move(leftEdgeX + 200, y, { steps: 20 });
  await page.mouse.up();
  await expect(leftStack).toHaveAttribute("aria-hidden", "false", {
    timeout: 2000,
  });
  // Ensure animation completes and state stabilizes
  await expect(leftStack).toHaveClass(/open/, { timeout: 2000 });
  // Wait for CSS transition to complete (180ms transition + buffer)
  await page.waitForTimeout(DRAWER_ANIMATION_WAIT);

  // Wait for transition to complete so bounding box is correct (x >= 0)
  await expect
    .poll(
      async () => {
        const box = await leftStack.boundingBox();
        return box && box.x >= 0;
      },
      { timeout: 2000 },
    )
    .toBe(true);

  // close left (drag ←)
  const leftStackBox = await leftStack.boundingBox();
  if (!leftStackBox) throw new Error("left stack not visible");

  const startX = leftStackBox.x + 200;
  const endX = leftStackBox.x + 50;

  await page.mouse.move(startX, y);
  await page.mouse.down();
  await page.mouse.move(endX, y, { steps: 20 });
  await page.mouse.up();
  // Wait for animation and DOM update to complete
  await page.waitForTimeout(DRAWER_ANIMATION_WAIT);
  await expect(leftStack).toHaveAttribute("aria-hidden", "true", {
    timeout: 4000,
  });

  // open right (drag ← an rechter Kante)
  const rightEdgeBox = await rightEdge.boundingBox();
  if (!rightEdgeBox) throw new Error("right edge not visible");
  const rx = rightEdgeBox.x + rightEdgeBox.width * 0.5;
  await page.mouse.move(rx, y);
  await page.mouse.down();
  await page.mouse.move(rx - 200, y, { steps: 20 });
  await page.mouse.up();
  await expect(filterDrawer).toHaveAttribute("aria-hidden", "false", {
    timeout: 2000,
  });
  // Wait for CSS transition to complete
  await page.waitForTimeout(DRAWER_ANIMATION_WAIT);

  // Ensure drawer is truly interactive before attempting to close
  await expect(filterDrawer).toHaveClass(/open/);

  // Wait for transition (Right drawer visible on screen)
  await expect
    .poll(
      async () => {
        const box = await filterDrawer.boundingBox();
        // Assuming viewport width ~1280. If closed, x is large. If open, x < 1280.
        return box && box.x < 1280;
      },
      { timeout: 2000 },
    )
    .toBe(true);

  // close right (drag →)
  const filterDrawerBox = await filterDrawer.boundingBox();
  if (!filterDrawerBox) throw new Error("filter drawer not visible");
  const startRX = filterDrawerBox.x + 100;
  const endRX = filterDrawerBox.x + 250;

  await page.mouse.move(startRX, y);
  await page.mouse.down();
  await page.mouse.move(endRX, y, { steps: 20 });
  await page.mouse.up();
  // Wait for animation and DOM update to complete
  await page.waitForTimeout(DRAWER_ANIMATION_WAIT);
  await expect(filterDrawer).toHaveAttribute("aria-hidden", "true", {
    timeout: 4000,
  });

  // open top (drag ↓ nahe Top)
  const topEdgeBox = await topEdge.boundingBox();
  if (!topEdgeBox) throw new Error("top edge bounding box unavailable");
  const tx = topEdgeBox.x + topEdgeBox.width * 0.5;
  const ty = topEdgeBox.y + topEdgeBox.height * 0.5;
  await page.mouse.move(tx, ty);
  await page.mouse.down();
  await page.mouse.move(tx, ty + 200, { steps: 20 });
  await page.mouse.up();
  await expect(accountDrawer).toHaveAttribute("aria-hidden", "false", {
    timeout: 2000,
  });
  // Wait for CSS transition to complete
  await page.waitForTimeout(DRAWER_ANIMATION_WAIT);

  // Wait for transition (Top drawer visible on screen)
  await expect
    .poll(
      async () => {
        const box = await accountDrawer.boundingBox();
        return box && box.y >= 0;
      },
      { timeout: 2000 },
    )
    .toBe(true);

  // close top (drag ↑)
  const accountDrawerBox = await accountDrawer.boundingBox();
  if (!accountDrawerBox) throw new Error("account drawer not visible");
  // Ensure we drag from within the drawer
  const startTY =
    accountDrawerBox.y + Math.min(accountDrawerBox.height - 20, 200);
  const endTY = startTY - 100;

  await page.mouse.move(tx, startTY);
  await page.mouse.down();
  await page.mouse.move(tx, endTY, { steps: 20 });
  await page.mouse.up();
  // Wait for animation and DOM update to complete
  await page.waitForTimeout(DRAWER_ANIMATION_WAIT);
  await expect(accountDrawer).toHaveAttribute("aria-hidden", "true", {
    timeout: 4000,
  });
});
