import { performance } from 'perf_hooks';

const NUM_NODES = 10000;
const NUM_EDGES = 1000;

const demoNodes = Array.from({ length: NUM_NODES }, (_, i) => ({
  id: `node-${i}`,
  title: `Node ${i}`,
  kind: 'Knoten'
}));

// Use a deterministic target distribution (modulo) instead of Math.random()
const demoEdges = Array.from({ length: NUM_EDGES }, (_, i) => ({
  id: `edge-${i}`,
  source_id: 'account-1',
  target_id: `node-${i % NUM_NODES}`,
  edge_kind: 'reference',
  note: 'note',
  source_type: 'account',
  target_type: 'node'
}));

const relatedEdges = demoEdges;

function baseline() {
  const nodes = relatedEdges
    .map((edge) => {
      const node = demoNodes.find((n) => n.id === edge.target_id);
      return {
        edge_id: edge.id,
        edge_kind: edge.edge_kind,
        note: edge.note,
        node_id: node?.id,
        node_title: node?.title,
        node_kind: node?.kind,
      };
    })
    .filter((n) => n.node_id);
  return nodes.length;
}

function optimized() {
  // We measure both index creation and lookup to simulate per-request cost
  const nodeMap = new Map(demoNodes.map((n) => [n.id, n]));
  const nodes = relatedEdges
    .map((edge) => {
      const node = nodeMap.get(edge.target_id);
      return {
        edge_id: edge.id,
        edge_kind: edge.edge_kind,
        note: edge.note,
        node_id: node?.id,
        node_title: node?.title,
        node_kind: node?.kind,
      };
    })
    .filter((n) => n.node_id);
  return nodes.length;
}

function optimizedCached() {
  // simulate module-level cache
  const nodeMap = new Map(demoNodes.map((n) => [n.id, n]));
  return () => {
    const nodes = relatedEdges
      .map((edge) => {
        const node = nodeMap.get(edge.target_id);
        return {
          edge_id: edge.id,
          edge_kind: edge.edge_kind,
          note: edge.note,
          node_id: node?.id,
          node_title: node?.title,
          node_kind: node?.kind,
        };
      })
      .filter((n) => n.node_id);
    return nodes.length;
  };
}

const cachedFn = optimizedCached();

function runBenchmark(fn: () => any, name: string, iterations = 100, warmUp = 10) {
  // Warm-up
  for (let i = 0; i < warmUp; i++) fn();

  const results: number[] = [];
  for (let i = 0; i < iterations; i++) {
    const start = performance.now();
    fn();
    const end = performance.now();
    results.push(end - start);
  }

  const avg = results.reduce((a, b) => a + b, 0) / iterations;
  const min = Math.min(...results);
  const max = Math.max(...results);
  const median = [...results].sort((a, b) => a - b)[Math.floor(iterations / 2)];

  console.log(`${name}:`);
  console.log(`  Avg:    ${avg.toFixed(4)}ms`);
  console.log(`  Median: ${median.toFixed(4)}ms`);
  console.log(`  Min:    ${min.toFixed(4)}ms`);
  console.log(`  Max:    ${max.toFixed(4)}ms`);
}

console.log(`Running benchmark with ${NUM_NODES} nodes and ${NUM_EDGES} edges...\n`);

runBenchmark(baseline, "Baseline (Array.find)");
runBenchmark(optimized, "Optimized (Map build + get)");
runBenchmark(cachedFn, "Optimized (Cached Map + get)");
