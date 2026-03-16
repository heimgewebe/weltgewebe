import { writeFileSync, mkdirSync, existsSync } from "node:fs";
import { resolve } from "node:path";
import { execSync } from "node:child_process";

const outDir = resolve(process.cwd(), "build/_app");

if (!existsSync(outDir)) {
  mkdirSync(outDir, { recursive: true });
}

let commit = "unknown";
if (process.env.GITHUB_SHA) {
  commit = process.env.GITHUB_SHA;
} else if (process.env.SOURCE_COMMIT) {
  commit = process.env.SOURCE_COMMIT;
} else {
  try {
    commit = execSync("git rev-parse HEAD").toString().trim();
  } catch {
    // fallback to unknown if git fails
  }
}

const buildId = `${commit}-${Date.now()}`;
const versionData = {
  version: buildId,
  build: buildId,
  built_at: new Date().toISOString(),
  commit: commit,
};

writeFileSync(
  resolve(outDir, "version.json"),
  JSON.stringify(versionData, null, 2),
);
console.log(`[generate-version] Wrote version.json: ${buildId}`);
