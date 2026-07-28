import { expect, test, type Page, type Route } from "@playwright/test";

const CONVERSATION_ID = "70000000-0000-4000-8000-000000000001";

function metadata() {
  return {
    id: CONVERSATION_ID,
    conversation_type: "node",
    lifecycle_state: "archived",
    node_id: null,
    node_id_snapshot: "historischer-knoten",
    node_title_snapshot: "Historischer Treffpunkt",
    visibility: "public",
    created_at: "2026-07-27T08:00:00Z",
    updated_at: "2026-07-27T09:05:00Z",
    archived_at: "2026-07-27T09:05:00Z",
    deleted_at: null,
  };
}

async function mockArchive(
  page: Page,
  options: {
    metadataStatus?: number;
    metadataBody?: unknown;
    messagesBody?: unknown;
  } = {},
) {
  await page.route("**/api/conversations/**", async (route: Route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === `/api/conversations/${CONVERSATION_ID}`) {
      return route.fulfill({
        status: options.metadataStatus ?? 200,
        contentType: "application/json",
        body: JSON.stringify(options.metadataBody ?? metadata()),
      });
    }
    if (path === `/api/conversations/${CONVERSATION_ID}/messages`) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          options.messagesBody ?? {
            items: [],
            page: { limit: 50, next_cursor: null, has_more: false },
          },
        ),
      });
    }
    return route.fallback();
  });
}

test("Archivmetadaten und sichere schreibgeschützte Beiträge werden dargestellt", async ({
  page,
}) => {
  await mockArchive(page, {
    messagesBody: {
      items: [
        {
          id: "80000000-0000-4000-8000-000000000001",
          conversation_id: CONVERSATION_ID,
          author_account_id: "account-a",
          author_title: "Garnrolle A",
          content: "<button>Archiv löschen</button>\nErhaltener Beitrag",
          created_at: "2026-07-27T08:30:00Z",
          updated_at: "2026-07-27T08:30:00Z",
          deleted_at: null,
        },
        {
          id: "80000000-0000-4000-8000-000000000002",
          conversation_id: CONVERSATION_ID,
          author_account_id: null,
          author_title: "Ehemalige Garnrolle",
          content: null,
          created_at: "2026-07-27T08:45:00Z",
          updated_at: "2026-07-27T08:50:00Z",
          deleted_at: "2026-07-27T08:50:00Z",
        },
      ],
      page: { limit: 50, next_cursor: null, has_more: false },
    },
  });

  await page.goto(`/archive?id=${CONVERSATION_ID}`);

  const archive = page.locator("main.archive");
  await expect(
    archive.getByRole("heading", { level: 1, name: "Historischer Treffpunkt" }),
  ).toBeVisible();
  await expect(archive.getByText("historischer-knoten")).toBeVisible();
  await expect(
    archive.getByRole("list", { name: "Archivierte Gesprächsbeiträge" }),
  ).toBeVisible();
  await expect(
    archive.getByText("<button>Archiv löschen</button>\nErhaltener Beitrag"),
  ).toBeVisible();
  await expect(archive.getByText("Beitrag entfernt.")).toBeVisible();
  await expect(archive.locator("button, form, textarea, input")).toHaveCount(0);
});

test("ein leeres Archiv bleibt ein sicherer, unterscheidbarer Zustand", async ({
  page,
}) => {
  await mockArchive(page);
  await page.goto(`/archive?id=${CONVERSATION_ID}`);

  await expect(
    page.getByText("Dieses Gesprächsarchiv enthält keine Beiträge."),
  ).toBeVisible();
  await expect(page.locator("main button, main form")).toHaveCount(0);
});

for (const [label, status, heading] of [
  ["nicht gefunden", 404, "Archiv nicht gefunden"],
  ["nicht autorisiert", 403, "Kein Zugriff"],
  ["API-Fehler", 500, "Gesprächsarchiv nicht verfügbar"],
] as const) {
  test(`${label} wird ohne leere Scheindaten dargestellt`, async ({ page }) => {
    await mockArchive(page, {
      metadataStatus: status,
      metadataBody: { code: "request_failed", message: label },
    });
    await page.goto(`/archive?id=${CONVERSATION_ID}`);

    await expect(
      page.getByRole("heading", { level: 1, name: heading }),
    ).toBeVisible();
    await expect(page.locator("main ol, main button, main form")).toHaveCount(
      0,
    );
  });
}

test("eine missgebildete Antwort wird nicht teilweise gerendert", async ({
  page,
}) => {
  await mockArchive(page, {
    messagesBody: {
      items: [{ content: "<img src=x onerror=alert(1)>" }],
      page: { limit: 50, next_cursor: null, has_more: false },
    },
  });
  await page.goto(`/archive?id=${CONVERSATION_ID}`);

  await expect(
    page.getByRole("heading", { level: 1, name: "Archivdaten unvollständig" }),
  ).toBeVisible();
  await expect(
    page.locator("main ol, main img, main button, main form"),
  ).toHaveCount(0);
});
