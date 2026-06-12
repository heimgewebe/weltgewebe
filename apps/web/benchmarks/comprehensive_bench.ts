import { demoEdges, demoNodes, demoAccounts } from "../src/lib/demo/demoData";
import { performance } from "perf_hooks";

function benchmark(
  name: string,
  iterations: number,
  findFn: () => void,
  getFn: () => void,
) {
  console.log(`\n--- Benchmarking ${name} (${iterations} iterations) ---`);

  const start1 = performance.now();
  for (let i = 0; i < iterations; i++) {
    findFn();
  }
  const end1 = performance.now();
  const time1 = end1 - start1;
  console.log(`Array.find: ${time1.toFixed(4)}ms`);

  const start2 = performance.now();
  for (let i = 0; i < iterations; i++) {
    getFn();
  }
  const end2 = performance.now();
  const time2 = end2 - start2;
  console.log(`Map.get: ${time2.toFixed(4)}ms`);

  const improvement = (((time1 - time2) / time1) * 100).toFixed(2);
  console.log(`Improvement: ${improvement}%`);
}

// Edge benchmark
const edgeId = demoEdges[0].id;
const edgeMap = new Map(demoEdges.map((e) => [e.id, e]));
benchmark(
  "Edges",
  1_000_000,
  () => demoEdges.find((e) => e.id === edgeId),
  () => edgeMap.get(edgeId),
);

// Node benchmark
const nodeId = demoNodes[0].id;
const nodeMap = new Map(demoNodes.map((n) => [n.id, n]));
benchmark(
  "Nodes",
  1_000_000,
  () => demoNodes.find((n) => n.id === nodeId),
  () => nodeMap.get(nodeId),
);

// Account benchmark
const accountId = demoAccounts[0].id;
const accountMap = new Map(demoAccounts.map((a) => [a.id, a]));
benchmark(
  "Accounts",
  1_000_000,
  () => demoAccounts.find((a) => a.id === accountId),
  () => accountMap.get(accountId),
);

// Scalability test
console.log("\n--- Scalability Test (simulating 1000 items) ---");
const largeArray = Array.from({ length: 1000 }, (_, i) => ({ id: `id-${i}` }));
const largeMap = new Map(largeArray.map((item) => [item.id, item]));
const targetId = "id-999";

benchmark(
  "Scalability (1000 items)",
  100_000,
  () => largeArray.find((item) => item.id === targetId),
  () => largeMap.get(targetId),
);
