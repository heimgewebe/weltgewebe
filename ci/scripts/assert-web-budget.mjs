#!/usr/bin/env node
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, '..', '..');
const budgetPath = resolve(repoRoot, 'ci', 'budget.json');

const expected = {
  js_kb_max: 60,
  tti_ms_p95_max: 2000,
  inp_ms_p75_max: 200,
};

let raw;
try {
  raw = readFileSync(budgetPath, 'utf8');
} catch (error) {
  console.error(`Failed to read performance budget at ${budgetPath}`);
  throw error;
}

let parsed;
try {
  parsed = JSON.parse(raw);
} catch (error) {
  console.error('Performance budget file is not valid JSON');
  throw error;
}

const webBudget = parsed?.budgets?.web;
if (!webBudget) {
  throw new Error('Performance budget missing "budgets.web" entry');
}

for (const [key, expectedValue] of Object.entries(expected)) {
  const actual = webBudget[key];
  if (typeof actual !== 'number' || Number.isNaN(actual)) {
    throw new Error(`Performance budget value "${key}" must be a number`);
  }
  if (actual !== expectedValue) {
    throw new Error(
      `Performance budget "${key}" expected ${expectedValue} but found ${actual}`,
    );
  }
}

console.log('✅ Frontend performance budget matches expected thresholds');
