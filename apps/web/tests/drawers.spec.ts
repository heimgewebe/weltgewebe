import { test, expect } from "@playwright/test";

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
  await page.mouse.move(leftEdgeX + 140, y, { steps: 6 });
  await page.mouse.up();
  await expect(leftStack).toHaveAttribute("aria-hidden", "false", {
    timeout: 2000,
  });

  // close left (drag ←)
  const leftStackBox = await leftStack.boundingBox();
  if (!leftStackBox) throw new Error("left stack not visible");
  await page.mouse.move(leftStackBox.x + leftStackBox.width - 10, y);
  await page.mouse.down();
  await page.mouse.move(leftStackBox.x + 10, y, { steps: 6 });
  await page.mouse.up();
  await expect(leftStack).toHaveAttribute("aria-hidden", "true", {
    timeout: 2000,
  });

  // open right (drag ← an rechter Kante)
  const rightEdgeBox = await rightEdge.boundingBox();
  if (!rightEdgeBox) throw new Error("right edge not visible");
  const rx = rightEdgeBox.x + rightEdgeBox.width * 0.5;
  await page.mouse.move(rx, y);
  await page.mouse.down();
  await page.mouse.move(rx - 120, y, { steps: 6 });
  await page.mouse.up();
  await expect(filterDrawer).toHaveAttribute("aria-hidden", "false", {
    timeout: 2000,
  });

  // close right (drag →)
  const filterDrawerBox = await filterDrawer.boundingBox();
  if (!filterDrawerBox) throw new Error("filter drawer not visible");
  await page.mouse.move(filterDrawerBox.x + 10, y);
  await page.mouse.down();
  await page.mouse.move(filterDrawerBox.x + filterDrawerBox.width - 10, y, {
    steps: 6,
  });
  await page.mouse.up();
  await expect(filterDrawer).toHaveAttribute("aria-hidden", "true", {
    timeout: 2000,
  });

  // open top (drag ↓ nahe Top)
  const topEdgeBox = await topEdge.boundingBox();
  if (!topEdgeBox) throw new Error("top edge bounding box unavailable");
  const tx = topEdgeBox.x + topEdgeBox.width * 0.5;
  const ty = topEdgeBox.y + topEdgeBox.height * 0.5;
  await page.mouse.move(tx, ty);
  await page.mouse.down();
  await page.mouse.move(tx, ty + 140, { steps: 6 });
  await page.mouse.up();
  await expect(accountDrawer).toHaveAttribute("aria-hidden", "false", {
    timeout: 2000,
  });

  // close top (drag ↑)
  const accountDrawerBox = await accountDrawer.boundingBox();
  if (!accountDrawerBox) throw new Error("account drawer not visible");
  await page.mouse.move(tx, accountDrawerBox.y + accountDrawerBox.height - 10);
  await page.mouse.down();
  await page.mouse.move(tx, accountDrawerBox.y + 10, { steps: 6 });
  await page.mouse.up();
  await expect(accountDrawer).toHaveAttribute("aria-hidden", "true", {
    timeout: 2000,
  });
});
