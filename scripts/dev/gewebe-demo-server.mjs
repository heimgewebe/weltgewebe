// scripts/dev/gewebe-demo-server.mjs
// Minimaler, dependency-freier HTTP-Server (Node >= 18/20) für die Demo-APIs.
// Endpunkte:
// GET /api/nodes[?bbox=west,south,east,north]
// GET /api/edges
// GET /api/accounts
// Liest JSONL aus ./.gewebe/in/*.jsonl

import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { mkdir, writeFile, stat } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = resolve(fileURLToPath(import.meta.url), "..", "..", ".."); // repo root (expected)
const PORT = Number(process.env.PORT || 8080);

console.log("Starting server...");
console.log(`Port: ${PORT}`);

const NODES_FILE = resolve(__dirname, ".gewebe/in/demo.nodes.jsonl");
const EDGES_FILE = resolve(__dirname, ".gewebe/in/demo.edges.jsonl");
const ACCOUNTS_FILE = resolve(__dirname, ".gewebe/in/demo.accounts.jsonl");

function fmtBool(v) {
  return v ? "yes" : "no";
}

async function tryStat(p) {
  try {
    const s = await stat(p);
    return { ok: true, size: s.size };
  } catch (e) {
    return { ok: false, err: String(e?.message || e) };
  }
}

async function printStartupDiagnostics() {
  // These prints are intentionally noisy: they prevent "it works on my machine"
  // and make container/path issues obvious in 3 seconds.
  console.log("---- demo-server diagnostics ----");
  console.log(`node.version: ${process.version}`);
  console.log(`node.execPath: ${process.execPath}`);
  console.log(`cwd: ${process.cwd()}`);
  console.log(`argv: ${process.argv.join(" ")}`);
  console.log(`import.meta.url: ${import.meta.url}`);
  console.log(`repoRoot(__dirname): ${__dirname}`);
  console.log(`PORT(env): ${process.env.PORT ?? "(unset)"} -> ${PORT}`);

  const nodes = await tryStat(NODES_FILE);
  const edges = await tryStat(EDGES_FILE);
  const accounts = await tryStat(ACCOUNTS_FILE);
  console.log(`nodes.path: ${NODES_FILE}`);
  console.log(`nodes.exists: ${fmtBool(nodes.ok)}${nodes.ok ? ` (size=${nodes.size})` : ` (err=${nodes.err})`}`);
  console.log(`edges.path: ${EDGES_FILE}`);
  console.log(`edges.exists: ${fmtBool(edges.ok)}${edges.ok ? ` (size=${edges.size})` : ` (err=${edges.err})`}`);
  console.log(`accounts.path: ${ACCOUNTS_FILE}`);
  console.log(`accounts.exists: ${fmtBool(accounts.ok)}${accounts.ok ? ` (size=${accounts.size})` : ` (err=${accounts.err})`}`);
  console.log("---------------------------------");
}

const DEMO_NODES_JSONL = [
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

const DEMO_EDGES_JSONL = [
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

const DEMO_ACCOUNTS_JSONL = [
  {
    id: "00000000-0000-0000-0000-00000000A001",
    type: "garnrolle",
    title: "gewebespinnerAYE",
    summary: "Persönlicher Account (Garnrolle), am Wohnsitz verortet. Ursprung von Fäden ins Gewebe.",
    location: { lat: 53.5604148, lon: 10.0629844 },
    public_pos: { lat: 53.5604148, lon: 10.0629844 },
    visibility: "public",
    tags: ["account", "garnrolle", "wohnort"]
  }
];

function toJsonl(rows) {
  return rows.map((r) => JSON.stringify(r)).join("\n") + "\n";
}

async function fileIsNonEmpty(p) {
  try {
    const s = await stat(p);
    return s.size > 0;
  } catch {
    return false;
  }
}

async function ensureDemoData() {
  // Create dir even if it already exists (recursive).
  await mkdir(resolve(__dirname, ".gewebe/in"), { recursive: true });

  const nodesOk = await fileIsNonEmpty(NODES_FILE);
  const edgesOk = await fileIsNonEmpty(EDGES_FILE);
  const accountsOk = await fileIsNonEmpty(ACCOUNTS_FILE);

  if (nodesOk && edgesOk && accountsOk) return;

  console.log("Demo data missing → writing deterministic seeds (JS, bash-free) ...");
  if (!nodesOk) await writeFile(NODES_FILE, toJsonl(DEMO_NODES_JSONL), "utf8");
  if (!edgesOk) await writeFile(EDGES_FILE, toJsonl(DEMO_EDGES_JSONL), "utf8");
  if (!accountsOk) await writeFile(ACCOUNTS_FILE, toJsonl(DEMO_ACCOUNTS_JSONL), "utf8");
}

async function readJsonl(path) {
  const raw = await readFile(path, "utf8").catch(() => "");
  return raw
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean)
    .map((l) => JSON.parse(l));
}

function parseBBox(q) {
  // bbox=west,south,east,north
  if (!q || !("bbox" in q)) return null;
  const parts = String(q.bbox).split(",").map(Number);
  if (parts.length !== 4 || parts.some((n) => Number.isNaN(n))) return null;
  const [west, south, east, north] = parts;
  return { west, south, east, north };
}

function withinBBox(node, bbox) {
  if (!node?.location) return false;
  const { lon: lng, lat } = node.location;
  return (
    typeof lng === "number" &&
    typeof lat === "number" &&
    lng >= bbox.west &&
    lng <= bbox.east &&
    lat >= bbox.south &&
    lat <= bbox.north
  );
}

function sendJson(res, status, body, extraHeaders = {}) {
  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Access-Control-Allow-Origin": "*",
    "Cache-Control": "no-store",
    ...extraHeaders,
  });
  res.end(JSON.stringify(body));
}

function notFound(res) {
  sendJson(res, 404, { error: "Not Found" });
}

function badRequest(res, msg) {
  sendJson(res, 400, { error: "Bad Request", message: msg });
}

function parseQuery(url) {
  const idx = url.indexOf("?");
  const q = {};
  if (idx === -1) return q;
  const usp = new URLSearchParams(url.slice(idx + 1));
  for (const [k, v] of usp.entries()) q[k] = v;
  return q;
}

await printStartupDiagnostics();
await ensureDemoData();

const server = createServer(async (req, res) => {
  try {
    const url = req.url || "/";
    const path = url.split("?")[0];

    // Simple diagnostics route (not in spec but helpful)
    if (path === "/api/health") {
      return sendJson(res, 200, { status: "ok" });
    }

    if (req.method === "GET" && path === "/api/nodes") {
      const q = parseQuery(url);
      const bbox = parseBBox(q);
      const nodes = await readJsonl(NODES_FILE);

      const data = bbox ? nodes.filter((f) => withinBBox(f, bbox)) : nodes;
      return sendJson(res, 200, data);
    }

    if (req.method === "GET" && path === "/api/edges") {
      const edges = await readJsonl(EDGES_FILE);
      return sendJson(res, 200, edges);
    }

    if (req.method === "GET" && path === "/api/accounts") {
      const accounts = await readJsonl(ACCOUNTS_FILE);
      return sendJson(res, 200, accounts);
    }

    if (req.method === "OPTIONS") {
      // CORS preflight
      res.writeHead(204, {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET,OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Max-Age": "600",
      });
      return res.end();
    }

    return notFound(res);
  } catch (err) {
    console.error("[demo-server] error:", err);
    return sendJson(res, 500, { error: "Internal Server Error" });
  }
});

server.listen(PORT, () => {
  console.log(`✅ Demo API server listening on http://localhost:${PORT}`);
  console.log(" GET /api/nodes[?bbox=west,south,east,north]");
  console.log(" GET /api/edges");
  console.log(" GET /api/accounts");
});
