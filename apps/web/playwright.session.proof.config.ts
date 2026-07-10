import { defineConfig, type ReporterDescription } from "@playwright/test";
import { resolve } from "node:path";

const isCI = /^(1|true)$/i.test(process.env.CI ?? "");
const PORT = Number(process.env.PORT ?? (isCI ? 5173 : 4173));
const htmlReportDir = resolve(
  process.cwd(),
  process.env.PLAYWRIGHT_HTML_REPORT ?? "playwright-report",
);
const reporter: ReporterDescription[] = [
  [isCI ? "dot" : "line"],
  ["html", { open: "never", outputFolder: htmlReportDir }],
  [
    "junit",
    {
      outputFile: resolve(
        htmlReportDir,
        process.env.PLAYWRIGHT_JUNIT_OUTPUT_NAME ?? "results.xml",
      ),
    },
  ],
];

export default defineConfig({
  testDir: "tests/proofs",
  testMatch: "**/persistent-browser-session.proof.ts",
  timeout: 120_000,
  retries: isCI ? 1 : 0,
  workers: 1,
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: "on-first-retry",
  },
  reporter,
  webServer: [
    {
      command: "cargo run --locked --features integration-testing",
      cwd: resolve(process.cwd(), "../api"),
      name: "API",
      url: "http://127.0.0.1:8080/health/ready",
      timeout: 120_000,
      reuseExistingServer: !isCI,
      env: {
        ...process.env,
        API_BIND: "127.0.0.1:8080",
        AUTH_COOKIE_SECURE: "0",
        AUTH_SESSION_TTL_SECONDS: "2592000",
        CSRF_ALLOWED_ORIGINS: `http://localhost:${PORT}`,
      },
    },
    {
      command: `pnpm run build:e2e && pnpm preview --host 0.0.0.0 --port ${PORT}`,
      cwd: process.cwd(),
      name: "Web",
      url: `http://127.0.0.1:${PORT}`,
      timeout: 120_000,
      reuseExistingServer: !isCI,
      env: {
        ...process.env,
        PORT: String(PORT),
        AUTH_PASSKEY_PROOF_PROXY: "1",
      },
    },
  ],
});
