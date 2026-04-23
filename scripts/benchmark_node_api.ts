import { performance } from 'perf_hooks';

const NUM_ACCOUNTS = 500;
const NUM_NODES = 500;
// Mix of account-source and node-source edges to reflect real data shape
const NUM_EDGES = 1000;

const demoAccounts = Array.from({ length: NUM_ACCOUNTS }, (_, i) => ({
  id: `account-${i}`,
  title: `Account ${i}`,
  type: 'garnrolle',
}));

const demoNodes = Array.from({ length: NUM_NODES }, (_, i) => ({
  id: `node-${i}`,
  title: `Node ${i}`,
  kind: 'Knoten',
}));

const TARGET_NODE_ID = 'node-0';

// Half account-source, half node-source edges targeting node-0
const demoEdges = Array.from({ length: NUM_EDGES }, (_, i) => ({
  id: `edge-${i}`,
  source_id: i % 2 === 0 ? `account-${i % NUM_ACCOUNTS}` : `node-${(i + 1) % NUM_NODES}`,
  source_type: i % 2 === 0 ? 'account' : 'node',
  target_id: TARGET_NODE_ID,
  target_type: 'node',
  edge_kind: 'reference',
  note: 'note',
}));

const accountMap = new Map(demoAccounts.map((a) => [a.id, a]));

function baseline() {
  // Original inline route logic: filters by target, then checks source_type on lookup
  const relatedEdges = demoEdges.filter(
    (e) => e.target_id === TARGET_NODE_ID && e.target_type === 'node',
  );
  return relatedEdges
    .map((edge) => {
      const account = edge.source_type === 'account'
        ? demoAccounts.find((a) => a.id === edge.source_id)
        : undefined;
      return {
        edge_id: edge.id,
        edge_kind: edge.edge_kind,
        note: edge.note,
        account_id: account?.id,
        account_title: account?.title,
        account_type: account?.type,
      };
    })
    .filter((p) => p.account_id);
}

function optimized() {
  // resolveNodeParticipants: source_type check in filter + Map lookup
  const relatedEdges = demoEdges.filter(
    (e) =>
      e.target_id === TARGET_NODE_ID &&
      e.target_type === 'node' &&
      e.source_type === 'account',
  );
  return relatedEdges
    .map((edge) => {
      const account = accountMap.get(edge.source_id);
      return {
        edge_id: edge.id,
        edge_kind: edge.edge_kind,
        note: edge.note,
        account_id: account?.id,
        account_title: account?.title,
        account_type: account?.type,
      };
    })
    .filter((p) => p.account_id).length;
}

function runBenchmark(fn: () => any, name: string, iterations = 100, warmUp = 10) {
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

console.log(
  `Running benchmark with ${NUM_ACCOUNTS} accounts, ${NUM_NODES} nodes, ${NUM_EDGES} edges (50% account-source)...\n`,
);

runBenchmark(baseline, 'Baseline (Array.find + runtime source_type check)');
runBenchmark(optimized, 'Optimized (filter source_type + cached Map.get)');
