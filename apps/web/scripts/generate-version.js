import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";

// Ensure we output to build/_app/version.json
const targetFile = path.resolve(process.cwd(), "build/_app/version.json");
const targetDir = path.dirname(targetFile);

if (!fs.existsSync(targetDir)) {
  fs.mkdirSync(targetDir, { recursive: true });
}

let commit = null;
let shortSha = null;
try {
  commit = execSync("git rev-parse HEAD", { encoding: "utf8" }).trim();
  shortSha = execSync("git rev-parse --short HEAD", {
    encoding: "utf8",
  }).trim();
} catch {
  console.warn("WARNING: Could not determine git commit. Using fallback.");
}

const now = process.env.SOURCE_DATE_EPOCH
  ? new Date(parseInt(process.env.SOURCE_DATE_EPOCH, 10) * 1000)
  : new Date();
const epochMs = now.getTime();
const builtAt = now.toISOString();

// Canonical artifact ID (deterministic). Fallback to epoch if no commit exists.
const version = shortSha || `${epochMs}`;

// CI run ID (volatile context)
const buildId = shortSha ? `${shortSha}-${epochMs}` : `${epochMs}`;

const payload = {
  version,
  build_id: buildId,
  built_at: builtAt,
};

if (commit) {
  payload.commit = commit;
}

// Write the file
fs.writeFileSync(targetFile, JSON.stringify(payload, null, 2), "utf8");

console.log(`Generated build identity: ${version} at ${targetFile}`);
