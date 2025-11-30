// scripts/dev/gewebe-demo-server.mjs
// Minimaler, dependency-freier HTTP-Server (Node >= 18/20) für die Demo-APIs.
// Endpunkte:
// GET /api/nodes[?bbox=west,south,east,north]
// GET /api/edges
// Liest JSONL aus ./.gewebe/in/*.jsonl

import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = resolve(fileURLToPath(import.meta.url), '..', '..', '..');
const PORT = Number(process.env.PORT || 8080);

console.log('Starting server...');
console.log(`Port: ${PORT}`);

const NODES_FILE = resolve(__dirname, '.gewebe/in/demo.nodes.jsonl');
const EDGES_FILE = resolve(__dirname, '.gewebe/in/demo.edges.jsonl');

console.log(`Nodes file: ${NODES_FILE}`);
console.log(`Edges file: ${EDGES_FILE}`);

async function readJsonl(path) {
  const raw = await readFile(path, 'utf8').catch(() => '');
  return raw
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean)
    .map((l) => JSON.parse(l));
}

function parseBBox(q) {
// bbox=west,south,east,north
if (!q || !('bbox' in q)) return null;
const parts = String(q.bbox).split(',').map(Number);
if (parts.length !== 4 || parts.some((n) => Number.isNaN(n))) return null;
const [west, south, east, north] = parts;
return { west, south, east, north };
}

function withinBBox(feature, bbox) {
if (!feature?.geometry || feature.geometry.type !== 'Point') return false;
const [lng, lat] = feature.geometry.coordinates || [];
return (
typeof lng === 'number' &&
typeof lat === 'number' &&
lng >= bbox.west &&
lng <= bbox.east &&
lat >= bbox.south &&
lat <= bbox.north
);
}

function sendJson(res, status, body, extraHeaders = {}) {
res.writeHead(status, {
'Content-Type': 'application/json; charset=utf-8',
'Access-Control-Allow-Origin': '*',
'Cache-Control': 'no-store',
...extraHeaders,
});
res.end(JSON.stringify(body));
}

function notFound(res) {
sendJson(res, 404, { error: 'Not Found' });
}

function badRequest(res, msg) {
sendJson(res, 400, { error: 'Bad Request', message: msg });
}

function parseQuery(url) {
const idx = url.indexOf('?');
const q = {};
if (idx === -1) return q;
const usp = new URLSearchParams(url.slice(idx + 1));
for (const [k, v] of usp.entries()) q[k] = v;
return q;
}

const server = createServer(async (req, res) => {
try {
const url = req.url || '/';
const path = url.split('?')[0];

if (req.method === 'GET' && path === '/api/nodes') {
const q = parseQuery(url);
const bbox = parseBBox(q);
const nodes = await readJsonl(NODES_FILE);

const data = bbox ? nodes.filter((f) => withinBBox(f, bbox)) : nodes;
return sendJson(res, 200, data);
}

if (req.method === 'GET' && path === '/api/edges') {
const edges = await readJsonl(EDGES_FILE);
return sendJson(res, 200, edges);
}

if (req.method === 'OPTIONS') {
// CORS preflight
res.writeHead(204, {
'Access-Control-Allow-Origin': '*',
'Access-Control-Allow-Methods': 'GET,OPTIONS',
'Access-Control-Allow-Headers': 'Content-Type',
'Access-Control-Max-Age': '600',
});
return res.end();
}

return notFound(res);
} catch (err) {
console.error('[demo-server] error:', err);
return sendJson(res, 500, { error: 'Internal Server Error' });
}
});

server.listen(PORT, () => {
console.log(`▶ Demo-API läuft: http://127.0.0.1:${PORT}`);
console.log(' GET /api/nodes[?bbox=west,south,east,north]');
console.log(' GET /api/edges');
});
