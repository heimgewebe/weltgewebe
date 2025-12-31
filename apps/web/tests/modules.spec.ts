import { expect, test } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test.beforeEach(async ({ page }) => {
  await mockApiResponses(page);
  await page.goto("/map");
});

test("schaufenster renders modules from backend data", async ({ page }) => {
  // 1. Arrange: Click marker to open Schaufenster
  const marker = page.locator(".map-marker").first();
  await marker.waitFor({ state: "visible" });
  await marker.click();

  // 2. Act: Wait for Schaufenster
  const card = page.locator(".schaufenster-card");
  await expect(card).toBeVisible();

  // 3. Assert: Verify the presence of specific module buttons
  // "fairschenkbox" should have Steckbrief, Forum, Verantwortungen based on demoData.ts
  await expect(card.locator("button", { hasText: "Steckbrief" })).toBeVisible();
  await expect(card.locator("button", { hasText: "Forum" })).toBeVisible();
  await expect(
    card.locator("button", { hasText: "Verantwortungen" }),
  ).toBeVisible();

  // Verify they are initially locked
  const infosLock = card
    .locator(".module-card", { hasText: "Steckbrief" })
    .locator(".lock-toggle");
  await expect(infosLock).toHaveAttribute("aria-pressed", "true");
});
