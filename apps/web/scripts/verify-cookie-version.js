import { createRequire } from 'node:module';

// Fail fast in CI if the lockfile resolves to a vulnerable cookie version.
// Skip silently when cookie isn't present (e.g. npm ci --omit=dev / production).
// This guards against transitive downgrades or accidental removal of `overrides`.
const require = createRequire(import.meta.url);
const isCI = !!process.env.CI && process.env.CI !== 'false';

// Minimal semver check for our purposes: we just need to know if a version is
// less than the minimum safe version, using exact numeric components.
const semverLt = (a, b) => {
  const aParts = a.split('.').map(Number);
  const bParts = b.split('.').map(Number);
  for (let i = 0; i < Math.max(aParts.length, bParts.length); i++) {
    const aVal = aParts[i] || 0;
    const bVal = bParts[i] || 0;
    if (aVal < bVal) return true;
    if (aVal > bVal) return false;
  }
  return false;
};

const isModuleNotFound = (err) =>
  err?.code === 'MODULE_NOT_FOUND' ||
  err?.code === 'ERR_MODULE_NOT_FOUND' ||
  /Cannot find module/.test(String(err?.message || err));

try {
  const pkg = require('cookie/package.json');
  const installed = pkg?.version;
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
  // If cookie is not installed at all (e.g. prod install without dev deps),
  // skip the check so production installs still succeed.
  if (isModuleNotFound(err)) {
    // Be quiet in CI to avoid noisy logs in production pipelines.
    // Uncomment next line if you prefer an explicit note:
    // console.log('[security] cookie not present in this install; skipping version check.');
    process.exit(0);
  }
  // Other errors: strict in CI, lenient locally.
  const msg =
    `\n[security] Could not verify cookie version (unexpected error): ${err?.message || err}`;
  if (isCI) {
    console.error(msg);
    process.exit(1);
  }
  console.warn(msg, '\n(continuing locally)');
  process.exit(0);
}
