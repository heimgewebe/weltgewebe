import { test, expect } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test.describe("Garnrolle relations", () => {
  test("shows connected Knoten and activity from persisted Fäden", async ({
    page,
  }) => {
    await mockApiResponses(page);

    await page.route("**/api/nodes", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "node-1",
            kind: "resource",
            title: "fairschenkbox",
            created_at: "2026-07-11T11:11:50.289607+00:00",
            updated_at: "2026-07-11T11:11:50.289607+00:00",
            summary: "sharing is caring",
            address: "Caspar-Voght-Straße 35",
            location: { lat: 53.55899732464337, lon: 10.060655662114556 },
          },
        ]),
      });
    });

    await page.route("**/api/accounts", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "account-1",
            type: "garnrolle",
            title: "Alexander Mohr",
            summary: "schaunmermal",
            public_pos: { lat: 53.560395907330474, lon: 10.063080663681632 },
            map_state: "exact",
            radius_m: 0,
            tags: ["interest:Commons", "account", "garnrolle"],
          },
        ]),
      });
    });

    await page.route("**/api/edges", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "edge-1",
            source_id: "account-1",
            source_type: "account",
            target_id: "node-1",
            target_type: "node",
            edge_kind: "reference",
            created_at: "2026-07-11T11:11:50.322307+00:00",
          },
        ]),
      });
    });

    await page.route("**/api/accounts/account-1", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "account-1",
          type: "garnrolle",
          title: "Alexander Mohr",
          summary: "schaunmermal",
          public_pos: { lat: 53.560395907330474, lon: 10.063080663681632 },
          map_state: "exact",
          radius_m: 0,
          tags: ["interest:Commons", "account", "garnrolle"],
          nodes: [
            {
              node_id: "node-1",
              node_title: "fairschenkbox",
              node_kind: "resource",
              edge_kind: "reference",
            },
          ],
          activity: [
            {
              date: "2026-07-11T11:11:50.322307+00:00",
              event: 'Hat den Knoten "fairschenkbox" geknüpft.',
            },
          ],
        }),
      });
    });

    await page.goto("/map?focus=garnrolle:account-1");

    const panel = page.getByTestId("context-panel");
    await expect(panel).toBeVisible();
    await expect(panel.locator("h3")).toHaveText("Alexander Mohr");

    await panel.getByRole("tab", { name: "Aktivität" }).click();
    await expect(panel.locator("#panel-aktivitaet")).toContainText(
      'Hat den Knoten "fairschenkbox" geknüpft.',
    );

    await panel.getByRole("tab", { name: "Knoten" }).click();
    await expect(panel.locator("#panel-knoten")).toContainText("fairschenkbox");
    await expect(panel.locator("#panel-knoten")).not.toContainText("Faden");
    await expect(panel.locator("#panel-knoten")).not.toContainText("reference");
  });
});
