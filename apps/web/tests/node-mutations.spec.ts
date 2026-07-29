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
      expect(dialog.message()).toContain("Aus dem Gewebe entfernen");
      await dialog.accept();
    });
    const deleteRequestPromise = page.waitForRequest(
      (request) =>
        request.method() === "DELETE" &&
        /\/api\/nodes\/[^/]+$/.test(new URL(request.url()).pathname),
    );
    await panel
      .getByRole("button", { name: "Aus dem Gewebe entfernen" })
      .click();
    const deleteRequest = await deleteRequestPromise;
    expect(deleteRequest.headers()["if-match"]).toMatch(/^".+"$/);

    await expect(panel).toHaveCount(0);
    await expect(page.locator(".map-marker")).toHaveCount(
      markerCountBeforeDelete - 1,
    );
  });

  test("archivierte Gesprächsbeiträge bleiben nach der Entfernung erreichbar", async ({
    page,
  }) => {
    await mockApiResponses(page, {
      auth: {
        authenticated: true,
        account_id: "e2e-weber",
        role: "weber",
      },
      nodeDeleteConversation: {
        effect: "archived",
        archive_id: "70000000-0000-4000-8000-000000000001",
        archive_url: "/api/conversations/70000000-0000-4000-8000-000000000001",
      },
    });
    await page.route("**/api/conversations/**", async (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path === "/api/conversations/70000000-0000-4000-8000-000000000001") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: "70000000-0000-4000-8000-000000000001",
            conversation_type: "node",
            lifecycle_state: "archived",
            node_id: null,
            node_id_snapshot: "fake-id",
            node_title_snapshot: "Entfernter Knoten",
            visibility: "public",
            created_at: "2026-07-27T08:00:00Z",
            updated_at: "2026-07-27T09:05:00Z",
            archived_at: "2026-07-27T09:05:00Z",
            deleted_at: null,
          }),
        });
      }
      if (
        path ===
        "/api/conversations/70000000-0000-4000-8000-000000000001/messages"
      ) {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            items: [
              {
                id: "80000000-0000-4000-8000-000000000001",
                conversation_id: "70000000-0000-4000-8000-000000000001",
                author_account_id: "e2e-weber",
                author_title: "Eigene Garnrolle",
                content: "Erhaltener Gesprächsbeitrag",
                created_at: "2026-07-27T08:30:00Z",
                updated_at: "2026-07-27T08:30:00Z",
                deleted_at: null,
              },
            ],
            page: { limit: 50, next_cursor: null, has_more: false },
          }),
        });
      }
      return route.fallback();
    });
    await page.goto("/map");

    const panel = await openFirstNode(page);
    const markerCountBeforeDelete = await page.locator(".map-marker").count();
    await panel.getByRole("tab", { name: "Bearbeiten" }).click();
    page.once("dialog", async (dialog) => {
      expect(dialog.message()).toContain("Aus dem Gewebe entfernen");
      await dialog.accept();
    });
    await panel
      .getByRole("button", { name: "Aus dem Gewebe entfernen" })
      .click();

    const receipt = panel.getByRole("link", { name: "Archiv öffnen" });
    await expect(receipt).toBeVisible();
    await expect(receipt).toHaveAttribute(
      "href",
      "/archive?id=70000000-0000-4000-8000-000000000001",
    );
    await expect(page.locator(".map-marker")).toHaveCount(
      markerCountBeforeDelete - 1,
    );
    await receipt.click();
    await expect(page).toHaveURL(
      /\/archive\?id=70000000-0000-4000-8000-000000000001$/,
    );
    await expect(
      page.getByRole("heading", { level: 1, name: "Entfernter Knoten" }),
    ).toBeVisible();
    await expect(page.getByText("Erhaltener Gesprächsbeitrag")).toBeVisible();
    await expect(page.locator("main button, main form")).toHaveCount(0);
  });

  test("Gast kann einen selbst geknüpften Knoten bearbeiten", async ({
    page,
  }) => {
    const guestId = "e2e-gast";
    await mockApiResponses(page, {
      auth: {
        authenticated: true,
        account_id: guestId,
        role: "gast",
      },
    });
    await page.goto("/map");
    const created = await page.evaluate(async (accountId) => {
      const response = await fetch("/api/nodes", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          title: "Eigener Gastknoten",
          kind: "Ort",
          address: "Gastweg 1",
          location: { lat: 53.5, lon: 10.0 },
          tags: [],
          operation_id: "40000000-0000-4000-8000-000000000001",
        }),
      });
      const node = await response.json();
      if (node.created_by_account_id !== accountId) {
        throw new Error("mock creator binding missing");
      }
      return node;
    }, guestId);
    await page.goto(`/map?focus=node:${created.id}`);
    const panel = page.locator('[data-testid="context-panel"]');
    await expect(panel).toBeVisible();
    await expect(panel.locator("h3")).toHaveText("Eigener Gastknoten");
    await panel.getByRole("tab", { name: "Bearbeiten" }).click();
    await panel
      .getByRole("button", { name: "Bearbeiten", exact: true })
      .click();
    await panel.getByLabel("Titel").fill("Vom Gast gepflegt");
    await panel.getByRole("button", { name: "Änderungen speichern" }).click();
    await expect(panel.locator("h3")).toHaveText("Vom Gast gepflegt");
  });

  test("Gast sieht an einem fremden Knoten keine Bearbeitungs- oder Löschaktion", async ({
    page,
  }) => {
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
      panel.getByRole("button", { name: "Aus dem Gewebe entfernen" }),
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
      const requestedNodeId = decodeURIComponent(
        new URL(request.url()).pathname.split("/").pop() ?? "",
      );
      expect(requestedNodeId).not.toBe("");
      putAttempt += 1;
      if (putAttempt === 1) {
        await route.fulfill({
          status: 412,
          contentType: "application/json",
          body: JSON.stringify({
            id: requestedNodeId,
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
          id: requestedNodeId,
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
