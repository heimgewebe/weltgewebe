import { expect, test, type Page } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

async function openFirstNode(page: Page) {
  await page.waitForSelector(".map-marker", { timeout: 10000 });
  await page.evaluate(() => {
    const markers = Array.from(
      document.querySelectorAll(".map-marker"),
    ) as HTMLElement[];
    const nodeMarker =
      markers.find(
        (marker) => !marker.classList.contains("garnrolle-marker"),
      ) ?? markers[0];
    nodeMarker?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });
  const panel = page.locator('[data-testid="context-panel"]');
  await expect(panel).toBeVisible();
  await expect(panel.getByRole("tab", { name: "Übersicht" })).toBeVisible();
  return panel;
}

test.describe("Knoten bearbeiten und löschen", () => {
  test("Weber kann einen gemeinsamen Knoten bearbeiten und samt Fadenprojektionen löschen", async ({
    page,
  }) => {
    await mockApiResponses(page, {
      auth: {
        authenticated: true,
        account_id: "e2e-weber",
        role: "weber",
      },
    });
    await page.goto("/map");

    let panel = await openFirstNode(page);
    await panel.getByRole("button", { name: "Bearbeiten" }).click();
    await panel.getByLabel("Titel").fill("Gemeinsam gepflegter Knoten");
    await panel
      .getByLabel("Kurzbeschreibung")
      .fill("Aktualisierte öffentliche Kurzbeschreibung");

    const putRequestPromise = page.waitForRequest(
      (request) =>
        request.method() === "PUT" &&
        /\/api\/nodes\/[^/]+$/.test(new URL(request.url()).pathname),
    );
    await panel.getByRole("button", { name: "Änderungen speichern" }).click();
    const putRequest = await putRequestPromise;
    expect(putRequest.postDataJSON()).toMatchObject({
      title: "Gemeinsam gepflegter Knoten",
      summary: "Aktualisierte öffentliche Kurzbeschreibung",
    });
    await expect(panel).toHaveCount(0);

    panel = await openFirstNode(page);
    await expect(panel.locator("h3")).toHaveText("Gemeinsam gepflegter Knoten");
    const markerCountBeforeDelete = await page.locator(".map-marker").count();

    page.once("dialog", async (dialog) => {
      expect(dialog.type()).toBe("confirm");
      expect(dialog.message()).toContain("Knoten wirklich löschen");
      await dialog.accept();
    });
    const deleteRequestPromise = page.waitForRequest(
      (request) =>
        request.method() === "DELETE" &&
        /\/api\/nodes\/[^/]+$/.test(new URL(request.url()).pathname),
    );
    await panel.getByRole("button", { name: "Knoten löschen" }).click();
    await deleteRequestPromise;

    await expect(panel).toHaveCount(0);
    await expect(page.locator(".map-marker")).toHaveCount(
      markerCountBeforeDelete - 1,
    );
  });

  test("Gast sieht keine Bearbeitungs- oder Löschaktion", async ({ page }) => {
    await mockApiResponses(page, {
      auth: {
        authenticated: true,
        account_id: "e2e-gast",
        role: "gast",
      },
    });
    await page.goto("/map");

    const panel = await openFirstNode(page);
    await expect(panel.getByRole("button", { name: "Bearbeiten" })).toHaveCount(
      0,
    );
    await expect(
      panel.getByRole("button", { name: "Knoten löschen" }),
    ).toHaveCount(0);
  });
});
