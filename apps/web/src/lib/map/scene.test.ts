import { describe, it, expect } from "vitest";
import { buildMapScene, resolveApiMode } from "./scene";
import type { Node, Account, Edge, Webgemeindezentrum } from "./types";

const makeNode = (overrides: Partial<Node> = {}): Node => ({
  id: "node-1",
  kind: "Knoten",
  title: "Test Node",
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-01T00:00:00Z",
  tags: [],
  location: { lat: 53.5, lon: 10.0 },
  ...overrides,
});

const makeAccount = (overrides: Partial<Account> = {}): Account =>
  ({
    id: "acc-1",
    type: "garnrolle",
    title: "Test Account",
    created_at: "2025-01-01T00:00:00Z",
    tags: [],
    radius_m: 0,
    map_state: "exact",
    public_pos: { lat: 53.56, lon: 10.06 },
    ...overrides,
  }) as Account;

const makeEdge = (overrides: Partial<Edge> = {}): Edge => ({
  id: "edge-1",
  source_id: "acc-1",
  target_id: "node-1",
  edge_kind: "reference",
  ...overrides,
});

const makeCenter = (
  overrides: Partial<Webgemeindezentrum> = {},
): Webgemeindezentrum => ({
  type: "webgemeindezentrum",
  id: "webgemeindezentrum-hammer-park",
  title: "Webgemeindezentrum Hammer Park",
  ortsweberei: {
    id: "ortsweberei-hamm",
    slug: "hamm",
    name: "Ortsweberei Hamm",
    gewebezelle_id: "hamm.weltgewebe.net",
  },
  location_state: "desired",
  location_state_label: "Gewünschter Treffort",
  faden_endpoint_id: "22222222-2222-5222-8222-222222222222",
  conversation_id: "33333333-3333-5333-8333-333333333333",
  location: { lat: 53.5585, lon: 10.058 },
  location_label: "Hammer Park – gewünschter Treffpunkt auf der Grünfläche",
  meeting_note: "Hier kann die Ortsweberei tatsächlich zusammenkommen.",
  access_note: "Nutzung und Barrierefreiheit sind noch nicht bestätigt.",
  created_at: "2026-08-02T10:08:00.000Z",
  updated_at: "2026-08-02T10:08:00.000Z",
  ...overrides,
});

describe("resolveApiMode", () => {
  it("returns 'remote' when apiBase is set", () => {
    expect(resolveApiMode("https://api.example.com")).toBe("remote");
  });

  it("returns 'local' when apiBase is empty string", () => {
    expect(resolveApiMode("")).toBe("local");
  });

  it("returns 'local' when apiBase is undefined", () => {
    expect(resolveApiMode(undefined)).toBe("local");
  });
});

describe("buildMapScene", () => {
  it("transforms nodes into entities with type 'node'", () => {
    const scene = buildMapScene({
      nodes: [makeNode()],
      accounts: [],
      edges: [],
      webgemeindezentren: [],
      loadState: "ok",
      resourceStatus: [
        { resource: "nodes", status: "complete", loaded: 1, pages: 1 },
      ],
      apiBase: undefined,
      basemapMode: "local-sovereign",
    });

    expect(scene.entities).toHaveLength(1);
    expect(scene.entities[0].type).toBe("node");
    expect(scene.entities[0].id).toBe("node-1");
    expect(scene.entities[0].lat).toBe(53.5);
    expect(scene.entities[0].lon).toBe(10.0);
  });

  it("transforms accounts with public_pos into entities", () => {
    const scene = buildMapScene({
      nodes: [],
      accounts: [makeAccount({ tags: ["skill:Kochen", "interest:Commons"] })],
      edges: [],
      webgemeindezentren: [],
      loadState: "ok",
      resourceStatus: [
        { resource: "accounts", status: "complete", loaded: 1, pages: 1 },
      ],
      apiBase: undefined,
      basemapMode: "local-sovereign",
    });

    expect(scene.entities).toHaveLength(1);
    expect(scene.entities[0].type).toBe("garnrolle");
    expect(scene.entities[0].lat).toBe(53.56);
    expect(scene.entities[0].lon).toBe(10.06);
    expect(scene.entities[0].tags).toEqual([
      "skill:Kochen",
      "interest:Commons",
    ]);
  });

  it("excludes Garnrollen without a public position", () => {
    const account = makeAccount({
      id: "account-without-position",
      map_state: "not_on_map",
    });
    delete account.public_pos;

    const scene = buildMapScene({
      nodes: [],
      accounts: [account],
      edges: [],
      webgemeindezentren: [],
      loadState: "ok",
      resourceStatus: [],
      apiBase: undefined,
      basemapMode: "local-sovereign",
    });

    expect(scene.entities).toHaveLength(0);
  });

  it("merges nodes and accounts into entities", () => {
    const scene = buildMapScene({
      nodes: [makeNode()],
      accounts: [makeAccount()],
      edges: [makeEdge()],
      webgemeindezentren: [],
      loadState: "ok",
      resourceStatus: [],
      apiBase: undefined,
      basemapMode: "local-sovereign",
    });

    expect(scene.entities).toHaveLength(2);
    expect(scene.edges).toHaveLength(1);
  });

  it("maps a desired Webgemeindezentrum as an independent permanent structure", () => {
    const scene = buildMapScene({
      nodes: [],
      accounts: [],
      edges: [],
      webgemeindezentren: [makeCenter()],
      loadState: "ok",
      resourceStatus: [
        {
          resource: "webgemeindezentren",
          status: "complete",
          loaded: 1,
          pages: 1,
        },
      ],
      apiBase: undefined,
      basemapMode: "local-sovereign",
    });

    expect(scene.entities).toHaveLength(1);
    expect(scene.entities[0]).toMatchObject({
      type: "webgemeindezentrum",
      id: "webgemeindezentrum-hammer-park",
      title: "Webgemeindezentrum Hammer Park",
      lat: 53.5585,
      lon: 10.058,
      location_state: "desired",
      location_state_label: "Gewünschter Treffort",
    });
    expect(scene.entities[0].tags).toContain("Ortsweberei Hamm");
  });

  it("passes through loadState and resourceStatus", () => {
    const scene = buildMapScene({
      nodes: [],
      accounts: [],
      edges: [],
      webgemeindezentren: [],
      loadState: "partial",
      resourceStatus: [
        { resource: "nodes", status: "complete", loaded: 1, pages: 1 },
        { resource: "accounts", status: "failed", error: "HTTP 500" },
      ],
      apiBase: undefined,
      basemapMode: "local-sovereign",
    });

    expect(scene.loadState).toBe("partial");
    expect(scene.resourceStatus).toHaveLength(2);
    expect(scene.resourceStatus[1].status).toBe("failed");
  });

  it("sets diagnostics correctly for local mode", () => {
    const scene = buildMapScene({
      nodes: [],
      accounts: [],
      edges: [],
      webgemeindezentren: [],
      loadState: "ok",
      resourceStatus: [],
      apiBase: undefined,
      basemapMode: "local-sovereign",
    });

    expect(scene.diagnostics.apiMode).toBe("local");
    expect(scene.diagnostics.basemapMode).toBe("local-sovereign");
    expect(scene.diagnostics.degraded).toBe(false);
  });

  it("sets diagnostics correctly for remote mode with degraded state", () => {
    const scene = buildMapScene({
      nodes: [],
      accounts: [],
      edges: [],
      webgemeindezentren: [],
      loadState: "failed",
      resourceStatus: [],
      apiBase: "https://api.example.com",
      basemapMode: "remote-style",
    });

    expect(scene.diagnostics.apiMode).toBe("remote");
    expect(scene.diagnostics.basemapMode).toBe("remote-style");
    expect(scene.diagnostics.degraded).toBe(true);
  });
});
