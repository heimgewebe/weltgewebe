import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";

// Ensure we output to build/_app/version.json and src/lib/generated/buildVersion.json
const targetFile = path.resolve(process.cwd(), "build/_app/version.json");
const targetDir = path.dirname(targetFile);

if (!fs.existsSync(targetDir)) {
  fs.mkdirSync(targetDir, { recursive: true });
}

const clientDir = path.resolve(process.cwd(), "src/lib/generated");
if (!fs.existsSync(clientDir)) {
  fs.mkdirSync(clientDir, { recursive: true });
}
const clientFile = path.join(clientDir, "buildVersion.json");

let commit = null;
let shortSha = null;
try {
  commit = execSync("git rev-parse HEAD", { encoding: "utf8" }).trim();
  shortSha = execSync("git rev-parse --short HEAD", {
    encoding: "utf8",
  }).trim();
} catch {
  console.warn(
    "WARNING: Could not determine git commit. Using non-deterministic fallback.",
  );
}

let now = new Date();
if (process.env.SOURCE_DATE_EPOCH) {
  const epoch = parseInt(process.env.SOURCE_DATE_EPOCH, 10);
  if (!isNaN(epoch)) {
    now = new Date(epoch * 1000);
  }
}
const epochMs = now.getTime();
const builtAt = now.toISOString();

// Canonical artifact ID (deterministic). Cannot depend on time.
const version = shortSha || commit || "unknown";

// CI run ID (volatile context)
const buildId = shortSha ? `${shortSha}-${epochMs}` : `unknown-${epochMs}`;

const payload = {
  version,
  build_id: buildId,
  built_at: builtAt,
};

if (commit) {
  payload.commit = commit;
}

const args = process.argv.slice(2);
const writeClient = args.length === 0 || args.includes("--client");
const writeServer = args.length === 0 || args.includes("--server");

const filesWritten = [];

if (writeServer) {
  // Write the server deployment contract file
  // This artifact is served by the Edge proxy with Cache-Control: no-store and acts as the true server version.
  fs.writeFileSync(targetFile, JSON.stringify(payload, null, 2) + "\n", "utf8");
  filesWritten.push(targetFile);
}

if (writeClient) {
  // Write the local client bundle file
  // This artifact is bundled directly into the Svelte client at build-time to statically know its own version.
  fs.writeFileSync(clientFile, JSON.stringify(payload, null, 2) + "\n", "utf8");
  filesWritten.push(clientFile);
}

console.log(
  `Generated build identity: ${version} at ${filesWritten.join(" and ")}`,
);
