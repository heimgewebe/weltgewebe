import { performance } from "perf_hooks";

// Simulate the data structures
interface Account {
  id: string;
  type: string;
  title: string;
}

interface Edge {
  id: string;
  source_id: string;
  source_type: string;
  target_id: string;
  target_type: string;
  edge_kind: string;
  note: string;
}

function generateData(count: number) {
  const accounts: Account[] = [];
  const edges: Edge[] = [];
  const targetNodeId = "target-node-id";

  for (let i = 0; i < count; i++) {
    const id = `account-${i}`;
    accounts.push({
      id,
      type: "garnrolle",
      title: `Account ${i}`,
    });

    edges.push({
      id: `edge-${i}`,
      source_id: id,
      source_type: "account",
      target_id: targetNodeId,
      target_type: "node",
      edge_kind: "reference",
      note: "faden",
    });
  }

  return { accounts, edges, targetNodeId };
}

function originalApproach(accounts: Account[], relatedEdges: Edge[]) {
  return relatedEdges
    .map((edge) => {
      const account = accounts.find(
        (a) => a.id === edge.source_id && edge.source_type === "account",
      );
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

// Mimic the resolver logic with Map-based lookup
function resolverApproach(accounts: Account[], relatedEdges: Edge[]) {
  const accountMap = new Map(accounts.map((a) => [a.id, a]));
  return relatedEdges
    .map((edge) => {
      const account =
        edge.source_type === "account"
          ? accountMap.get(edge.source_id)
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

function runBenchmark() {
  const counts = [100, 500, 1000, 2000];

  console.log(
    "| Data Size (N) | Original (ms) | Resolver (ms) | Improvement |",
  );
  console.log(
    "|---------------|---------------|----------------|-------------|",
  );

  for (const count of counts) {
    const { accounts, edges } = generateData(count);

    // Warmup
    originalApproach(accounts, edges);
    resolverApproach(accounts, edges);

    const startOrig = performance.now();
    for (let i = 0; i < 10; i++) originalApproach(accounts, edges);
    const endOrig = performance.now();
    const avgOrig = (endOrig - startOrig) / 10;

    const startOpt = performance.now();
    for (let i = 0; i < 10; i++) resolverApproach(accounts, edges);
    const endOpt = performance.now();
    const avgOpt = (endOpt - startOpt) / 10;

    const improvement = (((avgOrig - avgOpt) / avgOrig) * 100).toFixed(2);

    console.log(
      `| ${count.toString().padEnd(13)} | ${avgOrig.toFixed(4).padEnd(13)} | ${avgOpt.toFixed(4).padEnd(14)} | ${improvement}% |`,
    );
  }
}

runBenchmark();
