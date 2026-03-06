const { performance } = require('perf_hooks');

const markersData = Array.from({ length: 100000 }, (_, i) => ({ id: `id-${i}` }));

function measure(name, fn) {
  const runs = 100;
  let total = 0;

  // warmup
  for (let i = 0; i < 10; i++) fn();

  for (let i = 0; i < runs; i++) {
    const start = performance.now();
    fn();
    total += (performance.now() - start);
  }

  console.log(`${name}: ${total / runs} ms per run`);
}

measure('Array.map + new Set', () => {
  return new Set(markersData.map(p => p.id));
});

measure('Array.reduce + Set.add', () => {
  return markersData.reduce((set, p) => set.add(p.id), new Set());
});

measure('For loop + Set.add', () => {
  const set = new Set();
  for (let i = 0; i < markersData.length; i++) {
    set.add(markersData[i].id);
  }
  return set;
});

measure('For..of + Set.add', () => {
  const set = new Set();
  for (const p of markersData) {
    set.add(p.id);
  }
  return set;
});
