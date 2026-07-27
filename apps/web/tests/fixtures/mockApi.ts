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
  await page.route("**/local-basemap/style.json*", (route) => {
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

  // Node creates and their server-derived Fäden persist for the lifetime of
  // the mock. There is deliberately no direct edge-create request surface.
  const createdNodes: Record<string, unknown>[] = [];
  const createdEdges: Record<string, unknown>[] = [];
  const mutableDemoNodes: Record<string, unknown>[] = demoNodes.map((node) => ({
    ...node,
    address: "Musterstraße 1",
    info: "Öffentliche Information zum Knoten",
    tags: ["commons"],
    location: { ...node.location },
  }));
  const deletedNodeIds = new Set<string>();
  const mockAccounts = demoAccounts.map((account) => ({ ...account }));
  const privateProfiles = new Map(
    mockAccounts.map((account) => [
      account.id,
      {
        address: "",
        location: account.location ? { ...account.location } : null,
      },
    ]),
  );
  let nextNodeId = 1;
  let nextEdgeId = 1;

  await page.route("**/api/**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();

    if (new URL(url).pathname === "/api/search" && method === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [],
          mode: "hybrid",
          generation_id: "mock-search-generation",
          offset: 0,
        }),
      });
    }

    if (url.endsWith("/api/nodes") && method === "POST") {
      if (!isAuthenticated || !currentAccountId) {
        return route.fulfill({ status: 401 });
      }
      const payload = route.request().postDataJSON() as Record<
        string,
        unknown
      > | null;
      const operationId =
        typeof payload?.operation_id === "string" ? payload.operation_id : "";
      const validOperationId =
        /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
          operationId,
        );
      const title =
        typeof payload?.title === "string" ? payload.title.trim() : "";
      const kind = typeof payload?.kind === "string" ? payload.kind.trim() : "";
      const address =
        typeof payload?.address === "string" ? payload.address.trim() : "";
      const location = payload?.location as
        | { lat?: unknown; lon?: unknown }
        | undefined;
      if (
        !validOperationId ||
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
        created_by_account_id: currentAccountId,
      };
      createdNodes.push(node);
      if (currentAccountId) {
        createdEdges.push({
          id: `mock-edge-${nextEdgeId++}`,
          source_id: currentAccountId,
          source_type: "account",
          target_id: node.id,
          target_type: "node",
          edge_kind: "reference",
          created_at: now,
        });
      }
      return route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(node),
      });
    }

    const nodeDetailMatch = new URL(url).pathname.match(
      /^\/api\/nodes\/([^/]+)$/,
    );
    if (nodeDetailMatch) {
      const nodeId = decodeURIComponent(nodeDetailMatch[1]);
      const allNodes = [...mutableDemoNodes, ...createdNodes];
      const node = allNodes.find((item) => item.id === nodeId);

      if (method === "GET") {
        return route.fulfill({
          status: node ? 200 : 404,
          contentType: "application/json",
          body: JSON.stringify(node ?? { error: "node not found" }),
        });
      }

      if (!isAuthenticated || !currentAccountId) {
        return route.fulfill({ status: 401 });
      }
      if (!node) {
        return route.fulfill({ status: 404 });
      }
      if (
        currentRole === "gast" &&
        node.created_by_account_id !== currentAccountId
      ) {
        return route.fulfill({ status: 403 });
      }

      if (method === "PUT") {
        const payload = route.request().postDataJSON() as Record<
          string,
          unknown
        > | null;
        const title =
          typeof payload?.title === "string" ? payload.title.trim() : "";
        const kind =
          typeof payload?.kind === "string" ? payload.kind.trim() : "";
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
          return route.fulfill({ status: 400 });
        }
        const updated = {
          ...node,
          title,
          kind,
          address,
          location: { lat: location.lat, lon: location.lon },
          summary:
            typeof payload?.summary === "string" ? payload.summary : undefined,
          info: typeof payload?.info === "string" ? payload.info : undefined,
          tags: Array.isArray(payload?.tags) ? payload.tags : [],
          id: node.id,
          created_at: node.created_at,
          updated_at: new Date().toISOString(),
        };
        const demoIndex = mutableDemoNodes.findIndex(
          (item) => item.id === nodeId,
        );
        if (demoIndex >= 0) {
          mutableDemoNodes[demoIndex] = updated;
        } else {
          const createdIndex = createdNodes.findIndex(
            (item) => item.id === nodeId,
          );
          createdNodes[createdIndex] = updated;
        }
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(updated),
        });
      }

      if (method === "DELETE") {
        const demoIndex = mutableDemoNodes.findIndex(
          (item) => item.id === nodeId,
        );
        if (demoIndex >= 0) mutableDemoNodes.splice(demoIndex, 1);
        const createdIndex = createdNodes.findIndex(
          (item) => item.id === nodeId,
        );
        if (createdIndex >= 0) createdNodes.splice(createdIndex, 1);
        deletedNodeIds.add(nodeId);
        for (let index = createdEdges.length - 1; index >= 0; index -= 1) {
          const edge = createdEdges[index];
          if (edge.source_id === nodeId || edge.target_id === nodeId) {
            createdEdges.splice(index, 1);
          }
        }
        return route.fulfill({ status: 204, body: "" });
      }

      return route.fulfill({ status: 405 });
    }

    if (url.endsWith("/api/nodes")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([...mutableDemoNodes, ...createdNodes]),
      });
    }

    if (url.endsWith("/api/accounts/me/profile")) {
      if (!isAuthenticated || !currentAccountId) {
        return route.fulfill({ status: 401 });
      }
      const account = mockAccounts.find((item) => item.id === currentAccountId);
      if (!account) {
        return route.fulfill({ status: 404 });
      }
      const privateProfile = privateProfiles.get(currentAccountId) ?? {
        address: "",
        location: null,
      };
      if (method === "PATCH") {
        const payload = route.request().postDataJSON() as Record<
          string,
          unknown
        >;
        const mapState = payload.map_state;
        const location = payload.location as
          | { lat?: unknown; lon?: unknown }
          | undefined;
        const clearAddress = payload.clear_address === true;
        const clearLocation = payload.clear_location === true;
        const suppliedLocation =
          typeof location?.lat === "number" && typeof location?.lon === "number"
            ? { lat: location.lat, lon: location.lon }
            : null;
        const effectiveLocation = clearLocation
          ? null
          : (suppliedLocation ?? privateProfile.location);
        if (
          typeof payload.title !== "string" ||
          !payload.title.trim() ||
          (mapState !== "not_on_map" &&
            mapState !== "exact" &&
            mapState !== "radius") ||
          (clearAddress && payload.address !== undefined) ||
          (clearLocation && location !== undefined) ||
          (clearLocation && mapState !== "not_on_map") ||
          (mapState !== "not_on_map" && effectiveLocation === null)
        ) {
          return route.fulfill({ status: 400 });
        }
        account.title = payload.title.trim();
        account.summary =
          typeof payload.summary === "string" ? payload.summary : "";
        account.tags = Array.isArray(payload.tags)
          ? payload.tags.filter((tag): tag is string => typeof tag === "string")
          : [];
        account.map_state = mapState;
        account.radius_m =
          mapState === "radius" && typeof payload.radius_m === "number"
            ? payload.radius_m
            : 0;
        if (clearLocation) {
          privateProfile.location = null;
        } else if (suppliedLocation) {
          privateProfile.location = suppliedLocation;
        }
        if (clearAddress) {
          privateProfile.address = "";
        } else if (typeof payload.address === "string") {
          privateProfile.address = payload.address;
        }
        if (mapState === "not_on_map") {
          delete account.public_pos;
        } else if (privateProfile.location) {
          account.public_pos = { ...privateProfile.location };
        }
        privateProfiles.set(currentAccountId, privateProfile);
      } else if (method !== "GET") {
        return route.fulfill({ status: 405 });
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: account.id,
          title: account.title,
          summary: account.summary,
          tags: account.tags,
          address: privateProfile.address || undefined,
          location: privateProfile.location || undefined,
          map_state: account.map_state ?? "not_on_map",
          radius_m: account.radius_m ?? 0,
        }),
      });
    }

    const accountDetailMatch = new URL(url).pathname.match(
      /^\/api\/accounts\/([^/]+)$/,
    );
    if (accountDetailMatch && method === "GET") {
      const account = mockAccounts.find(
        (item) => item.id === decodeURIComponent(accountDetailMatch[1]),
      );
      return route.fulfill({
        status: account ? 200 : 404,
        contentType: "application/json",
        body: JSON.stringify(account ?? { error: "account not found" }),
      });
    }

    if (url.endsWith("/api/accounts")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockAccounts),
      });
    }

    if (url.endsWith("/api/edges") && method !== "GET") {
      return route.fulfill({ status: 405 });
    }

    if (url.endsWith("/api/edges")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          [...demoEdges, ...createdEdges].filter(
            (edge) =>
              (typeof edge.source_id !== "string" ||
                !deletedNodeIds.has(edge.source_id)) &&
              (typeof edge.target_id !== "string" ||
                !deletedNodeIds.has(edge.target_id)),
          ),
        ),
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
          status: 401,
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
