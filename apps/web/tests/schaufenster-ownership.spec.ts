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
  // Note: AuthStatus now also has a logout button, so we filter by the one in the debug panel (which is what "Login Demo" toggles)
  // actually "Login Demo" is a dev helper that likely swaps the button text in place or shows a sibling.
  // However, since we now have two "Logout" buttons (one in AuthStatus, one in the Dev helper/Garnrolle UI),
  // we just need to assert that *at least one* is visible, or be more specific.
  // The ambiguous error happens because `getByRole` returns strict matches.
  // We can scope it to the debug panel if we knew its selector, or just use .first() if we just care about *a* logout button showing up.
  // But wait, "Login Demo" button suggests this test relies on some dev-only UI?
  // Let's check where "Login Demo" comes from. It's likely `GewebekontoWidget` or similar.
  // Given this is an integration test using mocks, let's just assert that the login flow completed.
  // We can target the logout button that replaces "Login Demo".
  await expect(page.getByRole("button", { name: "Logout" }).first()).toBeVisible();

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
