import { createRequire } from 'node:module';

// Fail fast in CI if the lockfile resolves to a vulnerable cookie version.
// This guards against transitive downgrades or accidental removal of `overrides`.
const require = createRequire(import.meta.url);
const isCI = process.env.CI === 'true';

const semverLt = (a, b) => {
  const pa = a.split('.').map(Number);
  const pb = b.split('.').map(Number);
  for (let i = 0; i < 3; i += 1) {
    const ai = pa[i] ?? 0;
    const bi = pb[i] ?? 0;
    if (ai < bi) return true;
    if (ai > bi) return false;
  }
  return false;
};

try {
  const installed = require('cookie/package.json').version;
  const minSafe = '0.7.0';
  if (semverLt(installed, minSafe)) {
    const msg =
      `\n[security] cookie@${installed} detected (< ${minSafe}). ` +
      `The advisory requires ${minSafe}+ — check npm overrides and lockfile.\n`;
    if (isCI) {
      console.error(msg);
      process.exit(1);
    } else {
      console.warn(msg.trim(), '\n(continuing locally)');
      process.exit(0);
    }
  }
} catch (err) {
  const msg = `\n[security] Could not verify cookie version: ${err?.message || err}`;
  if (isCI) {
    console.error(msg);
    process.exit(1);
  } else {
    console.warn(msg, '\n(continuing locally)');
    process.exit(0);
  }
}
