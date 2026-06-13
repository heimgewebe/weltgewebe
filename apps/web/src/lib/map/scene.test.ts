import { describe, it, expect } from "vitest";
import { buildMapScene, resolveApiMode } from "./scene";
import type { Node, Account, Edge } from "./types";

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
    mode: "verortet",
    title: "Test Account",
    created_at: "2025-01-01T00:00:00Z",
    tags: [],
    radius_m: 0,
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
      loadState: "ok",
      resourceStatus: [{ resource: "nodes", status: "ok" }],
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
      accounts: [makeAccount()],
      edges: [],
      loadState: "ok",
      resourceStatus: [{ resource: "accounts", status: "ok" }],
      apiBase: undefined,
      basemapMode: "local-sovereign",
    });

    expect(scene.entities).toHaveLength(1);
    expect(scene.entities[0].type).toBe("garnrolle");
    expect(scene.entities[0].lat).toBe(53.56);
    expect(scene.entities[0].lon).toBe(10.06);
  });

  it("excludes accounts without public_pos (e.g. RoN)", () => {
    const ronAccount = makeAccount({
      id: "ron-1",
      type: "ron",
      mode: "ron",
    } as any);
    // Remove public_pos to simulate RoN account
    delete (ronAccount as any).public_pos;

    const scene = buildMapScene({
      nodes: [],
      accounts: [ronAccount],
      edges: [],
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
      loadState: "ok",
      resourceStatus: [],
      apiBase: undefined,
      basemapMode: "local-sovereign",
    });

    expect(scene.entities).toHaveLength(2);
    expect(scene.edges).toHaveLength(1);
  });

  it("passes through loadState and resourceStatus", () => {
    const scene = buildMapScene({
      nodes: [],
      accounts: [],
      edges: [],
      loadState: "partial",
      resourceStatus: [
        { resource: "nodes", status: "ok" },
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
