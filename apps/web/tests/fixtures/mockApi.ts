import type { Page } from "@playwright/test";

/**
 * Mock API responses for E2E tests.
 * This ensures tests work without a running backend API server.
 */

const demoNodes = [
  {
    id: "00000000-0000-0000-0000-000000000001",
    kind: "Ort",
    title: "Marktplatz Hamburg",
    created_at: "2025-01-01T12:00:00Z",
    updated_at: "2025-11-01T09:00:00Z",
    location: { lon: 9.9937, lat: 53.5511 },
  },
  {
    id: "00000000-0000-0000-0000-000000000002",
    kind: "Initiative",
    title: "Nachbarschaftshaus",
    created_at: "2025-01-01T12:00:00Z",
    updated_at: "2025-11-02T12:15:00Z",
    location: { lon: 10.0002, lat: 53.5523 },
  },
  {
    id: "00000000-0000-0000-0000-000000000003",
    kind: "Projekt",
    title: "Tauschbox Altona",
    created_at: "2025-01-01T12:00:00Z",
    updated_at: "2025-10-30T18:45:00Z",
    location: { lon: 9.9813, lat: 53.5456 },
  },
  {
    id: "00000000-0000-0000-0000-000000000004",
    kind: "Ort",
    title: "Gemeinschaftsgarten",
    created_at: "2025-01-01T12:00:00Z",
    updated_at: "2025-11-05T10:00:00Z",
    location: { lon: 10.0184, lat: 53.5631 },
  },
  {
    id: "00000000-0000-0000-0000-000000000005",
    kind: "Initiative",
    title: "Reparaturcafé",
    created_at: "2025-01-01T12:00:00Z",
    updated_at: "2025-11-03T16:20:00Z",
    location: { lon: 9.9708, lat: 53.5615 },
  },
];

const demoEdges = [
  {
    id: "00000000-0000-0000-0000-000000000101",
    source_type: "node",
    source_id: "00000000-0000-0000-0000-000000000001",
    target_type: "node",
    target_id: "00000000-0000-0000-0000-000000000002",
    edge_kind: "reference",
    note: "Kooperation Marktplatz ↔ Nachbarschaftshaus",
    created_at: "2025-01-01T12:00:00Z",
  },
  {
    id: "00000000-0000-0000-0000-000000000102",
    source_type: "node",
    source_id: "00000000-0000-0000-0000-000000000002",
    target_type: "node",
    target_id: "00000000-0000-0000-0000-000000000004",
    edge_kind: "reference",
    note: "Gemeinschaftsaktion Gartenpflege",
    created_at: "2025-01-01T12:00:00Z",
  },
  {
    id: "00000000-0000-0000-0000-000000000103",
    source_type: "node",
    source_id: "00000000-0000-0000-0000-000000000001",
    target_type: "node",
    target_id: "00000000-0000-0000-0000-000000000003",
    edge_kind: "reference",
    note: "Tauschbox liefert Material",
    created_at: "2025-01-01T12:00:00Z",
  },
  {
    id: "00000000-0000-0000-0000-000000000104",
    source_type: "node",
    source_id: "00000000-0000-0000-0000-000000000005",
    target_type: "node",
    target_id: "00000000-0000-0000-0000-000000000001",
    edge_kind: "reference",
    note: "Reparaturcafé hilft Marktplatz",
    created_at: "2025-01-01T12:00:00Z",
  },
];

/**
 * Setup API mocking for a Playwright page.
 * Intercepts /api/** requests and returns demo data or empty responses.
 * This prevents ECONNREFUSED errors from the Vite proxy when backend is missing.
 */
export async function mockApiResponses(page: Page): Promise<void> {
  await page.route("**/api/nodes", async (route) => {
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(demoNodes),
    });
  });

  await page.route("**/api/edges", async (route) => {
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(demoEdges),
    });
  });

  await page.route("**/api/health", async (route) => {
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "Ready" }),
    });
  });

  // Catch-all for any other /api/** requests
  await page.route("**/api/**", async (route) => {
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({}),
    });
  });
}
