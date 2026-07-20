import { expect, test } from "@playwright/test";

test.describe("Federation diagnostics", () => {
  test("shows the public cell identity and resolves a global object", async ({
    page,
  }) => {
    await page.route("**/federation/v1/cell", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          protocol_version: "wg-federation/1",
          cell_id: "cell-a.example",
          public_base_url: "https://cell-a.example/federation/v1",
          active_key: {
            key_id: "key-2026-07",
            algorithm: "Ed25519",
            public_key: "A".repeat(43),
          },
          capabilities: [
            "signed-events",
            "origin-owned-objects",
            "neighbourhood-scope",
            "shared-rooms",
            "quarantine",
          ],
        }),
      });
    });
    await page.route("**/federation/v1/objects?**", async (route) => {
      const requestUrl = new URL(route.request().url());
      expect(requestUrl.searchParams.get("address")).toBe(
        "wg://cell-a.example/shared-room/harvest-2026",
      );
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          object_address: "wg://cell-a.example/shared-room/harvest-2026",
          origin_cell_id: "cell-a.example",
          object_kind: "shared-room",
          object_version: 2,
          scope: "global",
          payload: {
            title: "Harvest 2026",
            members: ["cell-a.example", "cell-b.example"],
          },
          deleted: false,
          updated_at: "2026-07-20T08:00:00Z",
        }),
      });
    });

    await page.goto("/federation");

    await expect(page.getByTestId("federation-cell-id")).toHaveText(
      "cell-a.example",
    );
    await expect(
      page.getByText("signed-events", { exact: true }),
    ).toBeVisible();
    await expect(page.getByText("shared-rooms", { exact: true })).toBeVisible();

    await page
      .getByTestId("federation-address")
      .fill("wg://cell-a.example/shared-room/harvest-2026");
    await page.getByRole("button", { name: "Prüfen", exact: true }).click();

    await expect(page.getByTestId("federation-object-address")).toHaveText(
      "wg://cell-a.example/shared-room/harvest-2026",
    );
    await expect(page.getByTestId("federation-object-version")).toHaveText("2");
    await expect(page.getByTestId("federation-object-payload")).toContainText(
      "Harvest 2026",
    );
  });

  test("reports a disabled federation boundary without inventing state", async ({
    page,
  }) => {
    await page.route("**/federation/v1/cell", async (route) => {
      await route.fulfill({ status: 404, body: "Not Found" });
    });

    await page.goto("/federation");

    await expect(page.getByTestId("federation-cell-status")).toContainText(
      "nicht öffentlich erreichbar",
    );
  });

  test("does not display neighbourhood-only or missing objects", async ({
    page,
  }) => {
    await page.route("**/federation/v1/cell", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          protocol_version: "wg-federation/1",
          cell_id: "cell-b.example",
          public_base_url: "https://cell-b.example/federation/v1",
          active_key: {
            key_id: "key-1",
            algorithm: "Ed25519",
            public_key: "B".repeat(43),
          },
          capabilities: ["signed-events"],
        }),
      });
    });
    await page.route("**/federation/v1/objects?**", async (route) => {
      await route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ error: "federated object not found" }),
      });
    });

    await page.goto("/federation");
    await page
      .getByTestId("federation-address")
      .fill("wg://cell-a.example/node/neighbour-only");
    await page.getByRole("button", { name: "Prüfen", exact: true }).click();

    await expect(page.getByTestId("federation-object-result")).toContainText(
      "Kein öffentliches globales Objekt",
    );
    await expect(page.getByText("neighbour-only", { exact: true })).toHaveCount(
      0,
    );
  });
});
