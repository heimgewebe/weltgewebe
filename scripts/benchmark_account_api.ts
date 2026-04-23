import { performance } from 'perf_hooks';

const NUM_NODES = 10000;
const NUM_EDGES = 1000;

const demoNodes = Array.from({ length: NUM_NODES }, (_, i) => ({
  id: `node-${i}`,
  title: `Node ${i}`,
  kind: 'Knoten'
}));

const demoEdges = Array.from({ length: NUM_EDGES }, (_, i) => ({
  id: `edge-${i}`,
  source_id: 'account-1',
  target_id: `node-${Math.floor(Math.random() * NUM_NODES)}`,
  edge_kind: 'reference',
  note: 'note',
  source_type: 'account',
  target_type: 'node'
}));

const relatedEdges = demoEdges;

function baseline() {
  const start = performance.now();
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
  const end = performance.now();
  return end - start;
}

function optimized() {
  const start = performance.now();
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
  const end = performance.now();
  return end - start;
}

console.log(`Baseline: ${baseline().toFixed(4)}ms`);
console.log(`Optimized: ${optimized().toFixed(4)}ms`);
