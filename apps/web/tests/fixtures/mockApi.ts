import type { Page } from "@playwright/test";
import {
  demoNodes,
  demoAccounts,
  demoEdges,
} from "../../src/lib/demo/demoData";

/**
 * Mock API responses for E2E tests.
 * This ensures tests work without a running backend API server.
 */

/**
 * Setup API mocking for a Playwright page.
 * Intercepts /api/** requests and returns demo data or empty responses.
 * This prevents ECONNREFUSED errors from the Vite proxy when backend is missing.
 */
import fs from "node:fs";
import path from "node:path";

export interface MockApiOptions {
  /**
   * Pre-authenticate the mock without going through the dev-login flow.
   * Defaults to unauthenticated/gast, matching prior `mockApiResponses(page)`
   * behaviour exactly.
   */
  auth?: { authenticated: boolean; account_id?: string; role?: string };
}

export async function mockApiResponses(
  page: Page,
  options: MockApiOptions = {},
): Promise<void> {
  // intercept version check so tests don't randomly show an UpdateBanner overlay
  await page.route("**/_app/version.json", async (route) => {
    let localVersion = "unknown";
    try {
      const versionFilePath = path.resolve(
        process.cwd(),
        "src/lib/generated/buildVersion.json",
      );
      if (fs.existsSync(versionFilePath)) {
        const data = JSON.parse(fs.readFileSync(versionFilePath, "utf8"));
        localVersion = data.version;
      }
    } catch {
      // ignore
    }

    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ version: localVersion }),
    });
  });

  // Intercept local map style fetching to provide a deterministic base payload during tests.
  await page.route("**/local-basemap/style.json", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ version: 8, sources: {}, layers: [] }),
    });
  });

  // Track auth state in the mock
  let isAuthenticated = options.auth?.authenticated ?? false;
  let currentAccountId = options.auth?.account_id ?? null;
  let currentRole = options.auth?.role ?? "gast";

  // Node/edge creates persist into these for the lifetime of the mock, so a
  // reload (GET /api/nodes, /api/edges) after a POST reflects the create —
  // mirroring the real API's persist-then-cache-then-readable contract.
  const createdNodes: Record<string, unknown>[] = [];
  const createdEdges: Record<string, unknown>[] = [];
  let nextNodeId = 1;
  let nextEdgeId = 1;

  await page.route("**/api/**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();

    if (url.endsWith("/api/nodes") && method === "POST") {
      const payload = route.request().postDataJSON() as Record<
        string,
        unknown
      > | null;
      const title =
        typeof payload?.title === "string" ? payload.title.trim() : "";
      const kind = typeof payload?.kind === "string" ? payload.kind.trim() : "";
      const address =
        typeof payload?.address === "string" ? payload.address.trim() : "";
      const location = payload?.location as
        | { lat?: unknown; lon?: unknown }
        | undefined;
      if (
        !title ||
        !kind ||
        !address ||
        typeof location?.lat !== "number" ||
        typeof location?.lon !== "number"
      ) {
        return route.fulfill({
          status: 400,
          contentType: "application/json",
          body: JSON.stringify({ error: "invalid node create request" }),
        });
      }
      const now = new Date().toISOString();
      const node = {
        id: `mock-node-${nextNodeId++}`,
        kind,
        title,
        address,
        summary:
          typeof payload?.summary === "string" ? payload.summary : undefined,
        tags: Array.isArray(payload?.tags) ? payload.tags : [],
        location,
        created_at: now,
        updated_at: now,
      };
      createdNodes.push(node);
      return route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(node),
      });
    }

    if (url.endsWith("/api/nodes")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([...demoNodes, ...createdNodes]),
      });
    }

    if (url.endsWith("/api/accounts")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(demoAccounts),
      });
    }

    if (url.endsWith("/api/edges") && method === "POST") {
      const payload = route.request().postDataJSON() as Record<
        string,
        unknown
      > | null;
      if (
        typeof payload?.source_id !== "string" ||
        typeof payload?.source_type !== "string" ||
        typeof payload?.target_id !== "string" ||
        typeof payload?.target_type !== "string" ||
        typeof payload?.edge_kind !== "string"
      ) {
        return route.fulfill({
          status: 400,
          contentType: "application/json",
          body: JSON.stringify({ error: "invalid edge create request" }),
        });
      }
      const edge = {
        id: `mock-edge-${nextEdgeId++}`,
        source_id: payload.source_id,
        source_type: payload.source_type,
        target_id: payload.target_id,
        target_type: payload.target_type,
        edge_kind: payload.edge_kind,
        created_at: new Date().toISOString(),
      };
      createdEdges.push(edge);
      return route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(edge),
      });
    }

    if (url.endsWith("/api/edges")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([...demoEdges, ...createdEdges]),
      });
    }

    if (url.includes("/api/health")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "Ready" }),
      });
    }

    // Handle auth/dev/login
    if (url.includes("/api/auth/dev/login") && method === "POST") {
      try {
        const postData = route.request().postDataJSON();
        currentAccountId = postData?.account_id || null;
        isAuthenticated = true;
        // Dev-login always lands as gast in the real API; a role is only
        // pre-set via `mockApiResponses(page, { auth: { role: ... } })`.
        currentRole = "gast";
        return route.fulfill({
          status: 200,
          headers: {
            "Set-Cookie":
              "gewebe_session=mock_session; Path=/; HttpOnly; SameSite=Strict; Secure",
          },
        });
      } catch {
        return route.fulfill({ status: 400 });
      }
    }

    // Handle auth/logout
    if (url.includes("/api/auth/logout") && method === "POST") {
      isAuthenticated = false;
      currentAccountId = null;
      return route.fulfill({
        status: 200,
        headers: {
          "Set-Cookie":
            "gewebe_session=; Path=/; HttpOnly; SameSite=Strict; Secure; Max-Age=0",
        },
      });
    }

    // Handle auth/me
    if (url.includes("/api/auth/me")) {
      if (isAuthenticated && currentAccountId) {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            authenticated: true,
            account_id: currentAccountId,
            role: currentRole,
          }),
        });
      } else {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            authenticated: false,
            role: "gast",
          }),
        });
      }
    }

    // Default: empty, no error objects
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({}),
    });
  });
}
