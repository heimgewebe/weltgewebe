import { test, expect, type Page } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";
import { activateToolFanAction } from "./fixtures/toolFan";

const SOURCE_NODE = {
  id: "source-node",
  title: "Offene Fahrradwerkstatt",
  summary: "Gemeinsam Fahrräder reparieren",
  info: "Werkzeuge teilen und voneinander lernen",
  tags: ["Fahrrad", "Reparatur"],
  kind: "Werkstatt",
  location: { lat: 54.9, lon: 8.3 },
  modules: [],
  created_at: "2026-07-23T00:00:00Z",
};

const SIMILAR_NODE = {
  id: "similar-node",
  title: "Gemeinschaftliche Radstation",
  summary: "Hilfe bei Fahrradreparaturen",
  kind: "Werkstatt",
  location: { lat: 54.91, lon: 8.31 },
  modules: [],
  created_at: "2026-07-23T00:00:00Z",
};

async function openSearch(page: Page) {
  await page.goto("/map");
  await page.waitForSelector(".map-marker");
  await activateToolFanAction(page, "find");
  return page.getByRole("searchbox", { name: "Suchbegriff" });
}

test.describe("T007 authorized server search contract", () => {
  test.beforeEach(async ({ page }) => {
    await mockApiResponses(page);
    await page.route("**/api/nodes", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([SOURCE_NODE]),
      });
    });
    await page.route("**/api/node/source-node", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(SOURCE_NODE),
      });
    });
  });

  test("does not fall back to the locally loaded node scene when server search fails", async ({
    page,
  }) => {
    await page.route("**/api/search**", async (route) => {
      await route.fulfill({ status: 503, body: "search_unavailable" });
    });

    const input = await openSearch(page);
    await input.fill("Offene Fahrradwerkstatt");

    await expect(
      page.getByText(
        "Die sichere Knotensuche ist gerade nicht verfügbar. Es wird nicht auf eine lokale Knotensuche zurückgefallen.",
      ),
    ).toBeVisible();
    await expect(page.getByRole("option")).toHaveCount(0);
  });

  test("renders lexical fallback explicitly while keeping server results usable", async ({
    page,
  }) => {
    await page.route("**/api/search**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [SOURCE_NODE],
          mode: "lexical_fallback",
          fallback_reason: "provider_unavailable",
          generation_id: "fallback-generation",
          offset: 0,
        }),
      });
    });

    const input = await openSearch(page);
    await input.fill("Fahrradwerkstatt");

    await expect(
      page.getByText(
        "Die semantische Ergänzung ist vorübergehend nicht verfügbar. Die serverseitige lexikalische Suche bleibt aktiv.",
      ),
    ).toBeVisible();
    await expect(page.getByRole("option").first()).toContainText(
      "Offene Fahrradwerkstatt",
    );
  });

  test("ignores a stale slower response after the query changes", async ({
    page,
  }) => {
    await page.route("**/api/search**", async (route) => {
      const query = new URL(route.request().url()).searchParams.get("q") ?? "";
      if (query === "alt") {
        await new Promise((resolve) => setTimeout(resolve, 550));
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            items: [
              { ...SOURCE_NODE, id: "old-node", title: "Altes Ergebnis" },
            ],
            mode: "hybrid",
            generation_id: "old-generation",
            offset: 0,
          }),
        });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [{ ...SOURCE_NODE, id: "new-node", title: "Neues Ergebnis" }],
          mode: "hybrid",
          generation_id: "new-generation",
          offset: 0,
        }),
      });
    });

    const input = await openSearch(page);
    await input.fill("alt");
    await page.waitForRequest((request) => {
      const url = new URL(request.url());
      return (
        url.pathname === "/api/search" && url.searchParams.get("q") === "alt"
      );
    });
    await input.fill("neu");

    await expect(page.getByRole("option").first()).toContainText(
      "Neues Ergebnis",
    );
    await expect(page.getByText("Altes Ergebnis")).toHaveCount(0);
    await page.waitForTimeout(600);
    await expect(page.getByRole("option").first()).toContainText(
      "Neues Ergebnis",
    );
    await expect(page.getByText("Altes Ergebnis")).toHaveCount(0);
  });

  test("shows similar nodes as machine-computed suggestions, not relations, and navigates without mutation", async ({
    page,
  }) => {
    let mutationRequests = 0;
    await page.route("**/api/search**", async (route) => {
      const query = new URL(route.request().url()).searchParams.get("q") ?? "";
      const items = query.includes("Werkzeuge teilen")
        ? [SOURCE_NODE, SIMILAR_NODE]
        : [SOURCE_NODE];
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items,
          mode: "hybrid",
          generation_id: "similar-generation",
          offset: 0,
        }),
      });
    });
    await page.route("**/api/**", async (route) => {
      if (!["GET", "HEAD"].includes(route.request().method()))
        mutationRequests += 1;
      await route.fallback();
    });

    const input = await openSearch(page);
    await input.fill("Fahrradwerkstatt");
    await page.getByRole("option").first().click();

    const section = page.locator("section.similar-nodes");
    await expect(
      section.getByRole("heading", { name: "Ähnliche Knoten" }),
    ).toBeVisible();
    await expect(section).toContainText(
      "Maschinell aus Inhalt und Schlagwörtern dieses Knotens berechnet.",
    );
    await expect(section).toContainText("keine Fäden");
    await expect(section).toContainText("keine kuratierten Beziehungen");
    await expect(
      section.getByRole("button", { name: /Gemeinschaftliche Radstation/ }),
    ).toBeVisible();
    expect(mutationRequests).toBe(0);

    await section
      .getByRole("button", { name: /Gemeinschaftliche Radstation/ })
      .click();
    await expect(page.getByTestId("context-panel")).toBeVisible();
    expect(mutationRequests).toBe(0);
  });

  test("keeps lexical fallback visible in the similar-nodes empty state", async ({
    page,
  }) => {
    await page.route("**/api/search**", async (route) => {
      const query = new URL(route.request().url()).searchParams.get("q") ?? "";
      const items = [SOURCE_NODE];
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items,
          mode: query.includes("Werkzeuge teilen")
            ? "lexical_fallback"
            : "hybrid",
          fallback_reason: query.includes("Werkzeuge teilen")
            ? "provider_unavailable"
            : undefined,
          generation_id: "similar-fallback-generation",
          offset: 0,
        }),
      });
    });

    const input = await openSearch(page);
    await input.fill("Fahrradwerkstatt");
    await page.getByRole("option").first().click();

    const section = page.locator("section.similar-nodes");
    await expect(section).toContainText(
      "Die semantische Ergänzung ist gerade nicht verfügbar; die Vorschläge stammen aus dem lexikalischen Serverpfad.",
    );
    await expect(section).toContainText("Keine ähnlichen Knoten gefunden.");
  });
});
