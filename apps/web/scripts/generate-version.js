import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { execSync } from "child_process";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, "..");
const clientTargetDir = path.resolve(rootDir, "src/lib/generated");
const serverTargetDir = path.resolve(rootDir, "build/_app");

let shortSha = "dev";
try {
  shortSha = execSync("git rev-parse --short HEAD", {
    cwd: rootDir,
    stdio: "pipe",
  })
    .toString()
    .trim();
} catch {
  // Ignore
}

const versionData = {
  version: shortSha,
  built_at: new Date().toISOString(),
};

const args = process.argv.slice(2);
const isClient = args.includes("--client");
const isServer = args.includes("--server") || (!isClient && args.length === 0);

if (isClient) {
  if (!fs.existsSync(clientTargetDir)) {
    fs.mkdirSync(clientTargetDir, { recursive: true });
  }
  fs.writeFileSync(
    path.join(clientTargetDir, "buildVersion.json"),
    JSON.stringify(versionData, null, 2) + "\n",
  );
  console.log(`Generated client build identity: ${shortSha}`);
}

if (isServer) {
  if (!fs.existsSync(serverTargetDir)) {
    fs.mkdirSync(serverTargetDir, { recursive: true });
  }
  fs.writeFileSync(
    path.join(serverTargetDir, "version.json"),
    JSON.stringify(versionData, null, 2) + "\n",
  );
  console.log(
    `Generated build identity: ${shortSha} at ${path.join(serverTargetDir, "version.json")}`,
  );
}
