### 📄 weltgewebe/apps/web/tests/drawers.spec.ts

**Größe:** 3 KB | **md5:** `ab97256041c7f0f44e14769a9bd338be`

```typescript
import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  // Maus-Swipes in Tests erlauben
  await page.addInitScript(() => { (window as any).__E2E__ = true; });
  await page.goto('/map');
});

test('Esc schließt geöffnete Drawer (top → right → left)', async ({ page }) => {
  // Rechts öffnen
  await page.keyboard.press(']');
  await expect(page.getByRole('heading', { name: 'Suche & Filter' })).toBeVisible();

  // Esc → schließt rechts
  await page.keyboard.press('Escape');
  await expect(page.getByRole('heading', { name: 'Suche & Filter' })).toBeHidden();

  // Top öffnen
  await page.keyboard.press('Alt+g');
  await expect(page.getByRole('heading', { name: 'Gewebekonto' })).toBeVisible();

  // Esc → schließt top
  await page.keyboard.press('Escape');
  await expect(page.getByRole('heading', { name: 'Gewebekonto' })).toBeHidden();

  // Links öffnen
  await page.keyboard.press('[');
  await expect(page.getByRole('heading', { name: 'Webrat' })).toBeVisible();

  // Esc → schließt links (Stack)
  await page.keyboard.press('Escape');
  await expect(page.getByRole('heading', { name: 'Webrat' })).toBeHidden();
});

test('Swipe öffnet & schließt Drawer symmetrisch', async ({ page }) => {
  const map = page.locator('#map');

  // Linke Kante öffnen (drag→ rechts)
  const box = await map.boundingBox();
  if (!box) throw new Error('map not visible');
  const y = box.y + box.height * 0.5;

  // open left
  await page.mouse.move(box.x + 40, y);
  await page.mouse.down();
  await page.mouse.move(box.x + 120, y, { steps: 6 });
  await page.mouse.up();
  await expect(page.getByRole('heading', { name: 'Webrat' })).toBeVisible();

  // close left (drag ←)
  await page.mouse.move(box.x + 140, y);
  await page.mouse.down();
  await page.mouse.move(box.x + 30, y, { steps: 6 });
  await page.mouse.up();
  await expect(page.getByRole('heading', { name: 'Webrat' })).toBeHidden();

  // open right (drag ← an rechter Kante)
  const rx = box.x + box.width - 40;
  await page.mouse.move(rx, y);
  await page.mouse.down();
  await page.mouse.move(rx - 100, y, { steps: 6 });
  await page.mouse.up();
  await expect(page.getByRole('heading', { name: 'Suche & Filter' })).toBeVisible();

  // close right (drag →)
  await page.mouse.move(rx - 120, y);
  await page.mouse.down();
  await page.mouse.move(rx + 20, y, { steps: 6 });
  await page.mouse.up();
  await expect(page.getByRole('heading', { name: 'Suche & Filter' })).toBeHidden();

  // open top (drag ↓ nahe Top)
  const tx = box.x + box.width * 0.5;
  const ty = box.y + 40;
  await page.mouse.move(tx, ty);
  await page.mouse.down();
  await page.mouse.move(tx, ty + 120, { steps: 6 });
  await page.mouse.up();
  await expect(page.getByRole('heading', { name: 'Gewebekonto' })).toBeVisible();

  // close top (drag ↑)
  await page.mouse.move(tx, ty + 140);
  await page.mouse.down();
  await page.mouse.move(tx, ty - 10, { steps: 6 });
  await page.mouse.up();
  await expect(page.getByRole('heading', { name: 'Gewebekonto' })).toBeHidden();
});
```

### 📄 weltgewebe/apps/web/tests/map-smoke.spec.ts

**Größe:** 570 B | **md5:** `79a75ef59118015fac2b3427e2fc9b88`

```typescript
import { expect, test } from "@playwright/test";

test.describe("map route", () => {
  test("shows structure layer controls", async ({ page }) => {
    await page.goto("/map");

    const strukturknotenButton = page.getByRole("button", { name: "Strukturknoten" });
    await expect(strukturknotenButton).toBeVisible();
    await expect(strukturknotenButton).toBeDisabled();

    await expect(page.getByRole("button", { name: "Fäden" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Archiv ansehen" })).toHaveAttribute("href", "/archive/");
  });
});
```

