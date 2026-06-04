
import { demoEdges } from "../src/lib/demo/demoData";
import { performance } from "perf_hooks";

// Simple O(N) find
function findById(id: string) {
  return demoEdges.find(e => e.id === id);
}

// O(1) Map lookup
const edgeMap = new Map(demoEdges.map(e => [e.id, e]));
function getFromMap(id: string) {
  return edgeMap.get(id);
}

const idToFind = demoEdges[0].id;
const iterations = 1_000_000;

console.log(`Benchmarking ${iterations} iterations...`);

const start1 = performance.now();
for (let i = 0; i < iterations; i++) {
  findById(idToFind);
}
const end1 = performance.now();
console.log(`Array.find: ${(end1 - start1).toFixed(4)}ms`);

const start2 = performance.now();
for (let i = 0; i < iterations; i++) {
  getFromMap(idToFind);
}
const end2 = performance.now();
console.log(`Map.get: ${(end2 - start2).toFixed(4)}ms`);
