import { defineConfig, type ReporterDescription } from "@playwright/test";
import { resolve } from "node:path";

const isCI = /^(1|true)$/i.test(process.env.CI ?? "");
const port = Number(process.env.GOVERNANCE_PROOF_WEB_PORT ?? 4175);
const apiPort = Number(process.env.GOVERNANCE_PROOF_API_PORT ?? 18083);
const webOrigin = `http://127.0.0.1:${port}`;
const proofDatabaseUrl = process.env.GOVERNANCE_PROOF_DATABASE_URL;
if (!proofDatabaseUrl) {
  throw new Error(
    "GOVERNANCE_PROOF_DATABASE_URL must point at a disposable PostgreSQL database",
  );
}
const cargoBin = process.env.GOVERNANCE_PROOF_CARGO_BIN ?? "cargo";
const inheritedEnv = { ...process.env };
delete inheritedEnv.DATABASE_URL;
const htmlReportDir = resolve(
  process.cwd(),
  process.env.PLAYWRIGHT_HTML_REPORT ?? "playwright-report-governance",
);
const reporter: ReporterDescription[] = [
  [isCI ? "dot" : "line"],
  ["html", { open: "never", outputFolder: htmlReportDir }],
  ["junit", { outputFile: resolve(htmlReportDir, "governance-results.xml") }],
];

export default defineConfig({
  testDir: "tests/proofs",
  testMatch: "**/governance-full-flow.proof.ts",
  timeout: 180_000,
  retries: 0,
  workers: 1,
  use: { baseURL: webOrigin, trace: "retain-on-failure" },
  reporter,
  webServer: [
    {
      command: `${cargoBin} run --locked --features integration-testing`,
      cwd: resolve(process.cwd(), "../api"),
      name: "API",
      url: `http://127.0.0.1:${apiPort}/health/ready`,
      timeout: 150_000,
      reuseExistingServer: false,
      env: {
        ...inheritedEnv,
        DATABASE_URL: proofDatabaseUrl,
        API_BIND: `127.0.0.1:${apiPort}`,
        AUTH_COOKIE_SECURE: "0",
        CSRF_ALLOWED_ORIGINS: webOrigin,
        WELTGEWEBE_API_STARTUP_MIGRATIONS: "run",
        WELTGEWEBE_DOMAIN_READ_SOURCE: "postgres",
        WELTGEWEBE_DOMAIN_ACCOUNT_WRITE_SOURCE: "postgres",
      },
    },
    {
      command: `pnpm run build:e2e && pnpm preview --host 0.0.0.0 --port ${port}`,
      cwd: process.cwd(),
      name: "Web",
      url: webOrigin,
      timeout: 150_000,
      reuseExistingServer: false,
      env: {
        ...process.env,
        PORT: String(port),
        AUTH_PASSKEY_PROOF_PROXY: "1",
        AUTH_PASSKEY_PROOF_PROXY_TARGET: `http://127.0.0.1:${apiPort}`,
      },
    },
  ],
});
