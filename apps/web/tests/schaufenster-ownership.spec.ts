import { expect, test } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test.beforeEach(async ({ page }) => {
  await mockApiResponses(page);
  await page.goto("/map");
  // Robust wait for map
  await page.locator("#map").waitFor();
  // Ensure loading overlay is gone before interacting
  await expect(page.locator(".loading-overlay")).toBeHidden();
});

test("Garnrolle (Account) behaves correctly for public vs owner", async ({
  page,
}) => {
  // 1. PUBLIC VIEW (Not logged in / Not owner)
  // Target a Garnrolle marker using prefix match
  // Note: data-testid is now `marker-garnrolle-<id>`
  const garnrolleMarker = page
    .locator('[data-testid^="marker-garnrolle-"]')
    .first();

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
  const moduleCard = card.locator('[data-module-id="profile"]');
  await expect(moduleCard).toHaveClass(/locked/);

  // Close card to reset selection
  await card.locator('button[aria-label="Close"]').click();
  await expect(card).toBeHidden();

  // 2. OWNER VIEW
  // Click the hidden login button added to the debug badge
  await page.getByRole("button", { name: "Login Demo" }).click();

  // Verify state changed to Logout (implies logged in)
  // Prefer debug badge logout (same surface as Login Demo), fallback to global AuthStatus.
  const debugLogout = page.getByTestId("debug-logout");
  const authStatusLogout = page.getByTestId("auth-status-logout");

  if (await debugLogout.isVisible().catch(() => false)) {
    await expect(debugLogout).toHaveText("Logout");
  } else {
    await expect(authStatusLogout).toBeVisible();
    // Optional but helpful if AuthStatus has a stable label/text:
    // await expect(authStatusLogout).toHaveText(/logout/i);
  }

  // Click the SAME Garnrolle marker (id matches the login ID hardcoded in store.ts)
  await garnrolleMarker.click();
  await expect(card).toBeVisible();

  // Lock toggles should now be VISIBLE for owner
  // There are 3 modules, so should be 3 toggles
  await expect(lockBtns).toHaveCount(3);
  await expect(lockBtns.first()).toBeVisible();

  // Verify we can toggle the lock
  const profileModule = card.locator('[data-module-id="profile"]');
  const profileLockBtn = profileModule.locator(".lock-toggle");

  // It should be locked by default (reset on open)
  await expect(profileModule).toHaveClass(/locked/);
  await expect(profileLockBtn).toHaveText("🔒"); // Lock icon

  // Unlock
  // Hover first in case of CSS opacity transition (good practice for UI tests)
  await profileModule.hover();
  await profileLockBtn.click();

  await expect(profileModule).not.toHaveClass(/locked/);
  await expect(profileLockBtn).toHaveText("🔓"); // Unlock icon

  // Lock again
  await profileLockBtn.click();
  await expect(profileModule).toHaveClass(/locked/);
});
