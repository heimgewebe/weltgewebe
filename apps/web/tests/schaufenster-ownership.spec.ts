import { expect, test } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test.beforeEach(async ({ page }) => {
  await mockApiResponses(page);
  await page.goto("/map");
});

test("Garnrolle (Account) behaves correctly for public vs owner", async ({ page }) => {
  // 1. PUBLIC VIEW (Not logged in / Not owner)
  // Target a Garnrolle marker
  // Note: We use the data-testid we added in +page.svelte
  const garnrolleMarker = page.locator('[data-testid="marker-garnrolle"]').first();

  // Wait for map to load and markers to appear
  await garnrolleMarker.waitFor({ state: "visible" });

  await garnrolleMarker.click();

  const card = page.locator(".schaufenster-card");
  await expect(card).toBeVisible();
  // Title of the first demo account in demoData.ts is "gewebespinnerAYE"
  await expect(card).toContainText("gewebespinnerAYE");

  // Lock toggles should be HIDDEN for non-owner on an Account
  // "Unlock-UI ... ist nur sichtbar, wenn isOwner === true"
  const lockBtns = card.locator(".lock-toggle");
  await expect(lockBtns).toHaveCount(0);

  // Modules should be locked by default (visual check via class)
  const moduleCard = card.locator(".module-card", { hasText: "Infos" });
  await expect(moduleCard).toHaveClass(/locked/);

  // Close card to reset selection
  await card.locator('button[aria-label="Close"]').click();
  await expect(card).toBeHidden();


  // 2. OWNER VIEW
  // Click the hidden login button added to the debug badge
  await page.getByRole("button", { name: "Login Demo" }).click();

  // Verify state changed to Logout (implies logged in)
  await expect(page.getByRole("button", { name: "Logout" })).toBeVisible();

  // Click the SAME Garnrolle marker (id matches the login ID hardcoded in store.ts)
  await garnrolleMarker.click();
  await expect(card).toBeVisible();

  // Lock toggles should now be VISIBLE for owner
  // There are 3 modules, so should be 3 toggles
  await expect(lockBtns).toHaveCount(3);
  await expect(lockBtns.first()).toBeVisible();

  // Verify we can toggle the lock
  const infosModule = card.locator(".module-card", { hasText: "Infos" });
  const infosLockBtn = infosModule.locator(".lock-toggle");

  // It should be locked by default (reset on open)
  await expect(infosModule).toHaveClass(/locked/);
  await expect(infosLockBtn).toHaveText("🔒"); // Lock icon

  // Unlock
  // Hover first in case of CSS opacity transition (good practice for UI tests)
  await infosModule.hover();
  await infosLockBtn.click();

  await expect(infosModule).not.toHaveClass(/locked/);
  await expect(infosLockBtn).toHaveText("🔓"); // Unlock icon

  // Lock again
  await infosLockBtn.click();
  await expect(infosModule).toHaveClass(/locked/);
});
