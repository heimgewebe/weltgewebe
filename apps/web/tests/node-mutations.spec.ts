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

    const panel = await openFirstNode(page);
    await expect(
      panel.getByRole("button", { name: "Bearbeiten", exact: true }),
    ).toHaveCount(0);
    await panel.getByRole("tab", { name: "Bearbeiten" }).click();
    await panel
      .getByRole("button", { name: "Bearbeiten", exact: true })
      .click();
    await expect(panel.getByLabel("Titel")).toBeFocused();
    await panel.getByRole("button", { name: "Abbrechen" }).click();
    await expect(panel.getByRole("tab", { name: "Bearbeiten" })).toBeFocused();
    await panel
      .getByRole("button", { name: "Bearbeiten", exact: true })
      .click();
    await expect(panel.getByLabel("Titel")).toBeFocused();
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
    expect(putRequest.headers()["if-match"]).toMatch(/^".+"$/);
    expect(putRequest.postDataJSON()).toMatchObject({
      title: "Gemeinsam gepflegter Knoten",
      summary: "Aktualisierte öffentliche Kurzbeschreibung",
    });
    await expect(panel).toBeVisible();
    await expect(panel.locator("h3")).toHaveText("Gemeinsam gepflegter Knoten");
    await expect(
      panel.getByText("Aktualisierte öffentliche Kurzbeschreibung"),
    ).toBeVisible();
    const markerCountBeforeDelete = await page.locator(".map-marker").count();

    await expect(panel.getByRole("tab", { name: "Übersicht" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await expect(panel.getByRole("tab", { name: "Übersicht" })).toBeFocused();
    await panel.getByRole("tab", { name: "Bearbeiten" }).click();
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
    const deleteRequest = await deleteRequestPromise;
    expect(deleteRequest.headers()["if-match"]).toMatch(/^".+"$/);

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
    await expect(panel.getByRole("tab", { name: "Bearbeiten" })).toHaveCount(0);
    await expect(
      panel.getByRole("button", { name: "Bearbeiten", exact: true }),
    ).toHaveCount(0);
    await expect(
      panel.getByRole("button", { name: "Knoten löschen" }),
    ).toHaveCount(0);

    const uebersichtTab = panel.getByRole("tab", { name: "Übersicht" });
    const verlaufTab = panel.getByRole("tab", { name: "Verlauf" });
    await uebersichtTab.focus();
    await page.keyboard.press("ArrowLeft");
    await expect(verlaufTab).toBeFocused();
    await expect(verlaufTab).toHaveAttribute("aria-selected", "true");
    await expect(verlaufTab).toHaveAttribute("tabindex", "0");
    await expect(uebersichtTab).toHaveAttribute("tabindex", "-1");
    await page.keyboard.press("ArrowRight");
    await expect(uebersichtTab).toBeFocused();
    await expect(uebersichtTab).toHaveAttribute("aria-selected", "true");
  });

  test("bewahrt den Entwurf bei 412 und speichert nach bewusstem Vergleich erneut", async ({
    page,
  }) => {
    await mockApiResponses(page, {
      auth: { authenticated: true, account_id: "e2e-weber", role: "weber" },
    });

    const observedIfMatch: string[] = [];
    let putAttempt = 0;
    await page.route("**/api/nodes/*", async (route, request) => {
      if (request.method() !== "PUT") {
        await route.fallback();
        return;
      }
      observedIfMatch.push(request.headers()["if-match"] ?? "");
      putAttempt += 1;
      if (putAttempt === 1) {
        await route.fulfill({
          status: 412,
          contentType: "application/json",
          body: JSON.stringify({
            id: "fake-id",
            title: "Neuer Titel vom Server",
            kind: "Ort",
            summary: "Neue Kurzbeschreibung vom Server",
            address: "Adresse",
            location: { lat: 0, lon: 0 },
            tags: ["server"],
            updated_at: "2026-07-18T10:00:00Z",
          }),
        });
        return;
      }

      const payload = request.postDataJSON();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "fake-id",
          ...payload,
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-07-18T10:01:00Z",
        }),
      });
    });

    await page.goto("/map");
    const panel = await openFirstNode(page);
    await panel.getByRole("tab", { name: "Bearbeiten" }).click();
    await panel
      .getByRole("button", { name: "Bearbeiten", exact: true })
      .click();
    await panel.getByLabel("Titel").fill("Mein Konflikt");
    await panel.getByRole("button", { name: "Änderungen speichern" }).click();

    expect(observedIfMatch[0]).toMatch(/^".+"$/);
    await expect(
      panel.getByText(
        "Der Knoten wurde in der Zwischenzeit geändert. Dein Entwurf bleibt erhalten. Vergleiche ihn mit dem aktuellen Stand und speichere anschließend erneut.",
      ),
    ).toBeVisible();
    await expect(panel.getByLabel("Titel")).toHaveValue("Mein Konflikt");
    const current = panel.getByRole("region", {
      name: "Aktueller Serverstand",
    });
    await expect(current).toContainText("Neuer Titel vom Server");
    await expect(current).toContainText("Neue Kurzbeschreibung vom Server");
    await expect(
      panel.getByRole("button", { name: "Änderungen speichern" }),
    ).toBeVisible();

    await panel.getByRole("button", { name: "Änderungen speichern" }).click();
    expect(observedIfMatch[1]).toBe('"2026-07-18T10:00:00Z"');
    await expect(panel.locator("h3")).toHaveText("Mein Konflikt");
    await expect(
      panel.getByRole("button", { name: "Änderungen speichern" }),
    ).toHaveCount(0);
  });
});
