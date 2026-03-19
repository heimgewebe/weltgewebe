/**
 * Synthetic benchmark to demonstrate the performance benefit of
 * Promise.all() over sequential await for independent I/O operations.
 */

const LATENCY_MS = 100;

async function simulatedFetch(name, duration) {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({
        ok: true,
        json: async () => [{ id: name }],
        text: async () => "error text",
        status: 200
      });
    }, duration);
  });
}

async function runSequential() {
  const start = performance.now();
  let nodes = [];
  let accounts = [];
  let edges = [];

  // Simulate nodes fetch
  try {
    const res = await simulatedFetch('nodes', LATENCY_MS);
    if (res.ok) {
      nodes = await res.json();
    }
  } catch (e) {}

  // Simulate accounts fetch
  try {
    const res = await simulatedFetch('accounts', LATENCY_MS);
    if (res.ok) {
      accounts = await res.json();
    }
  } catch (e) {}

  // Simulate edges fetch
  try {
    const res = await simulatedFetch('edges', LATENCY_MS);
    if (res.ok) {
      edges = await res.json();
    }
  } catch (e) {}

  const end = performance.now();
  return { duration: end - start, data: { nodes, accounts, edges } };
}

async function runConcurrent() {
  const start = performance.now();

  const fetchResource = async (name) => {
    try {
      const res = await simulatedFetch(name, LATENCY_MS);
      if (res.ok) {
        return await res.json();
      }
    } catch (e) {}
    return [];
  };

  const [nodes, accounts, edges] = await Promise.all([
    fetchResource('nodes'),
    fetchResource('accounts'),
    fetchResource('edges')
  ]);

  const end = performance.now();
  return { duration: end - start, data: { nodes, accounts, edges } };
}

async function main() {
  console.log(`Running benchmark with simulated ${LATENCY_MS}ms latency per request...`);

  const seqResults = [];
  const conResults = [];
  const iterations = 5;

  for (let i = 0; i < iterations; i++) {
    seqResults.push((await runSequential()).duration);
    conResults.push((await runConcurrent()).duration);
  }

  const seqAvg = seqResults.reduce((a, b) => a + b) / iterations;
  const conAvg = conResults.reduce((a, b) => a + b) / iterations;

  console.log(`\nResults (average of ${iterations} runs):`);
  console.log(`Sequential: ${seqAvg.toFixed(2)}ms`);
  console.log(`Concurrent: ${conAvg.toFixed(2)}ms`);
  console.log(`Improvement: ${((seqAvg - conAvg) / seqAvg * 100).toFixed(2)}%`);

  if (conAvg < seqAvg * 0.5) {
     console.log("\n✅ Concurrent fetching is significantly faster!");
  }
}

main().catch(console.error);