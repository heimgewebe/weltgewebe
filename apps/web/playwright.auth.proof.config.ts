import { defineConfig, type ReporterDescription } from "@playwright/test";
import { resolve } from "node:path";

const isCI = /^(1|true)$/i.test(process.env.CI ?? "");
const PORT = Number(process.env.PORT ?? (isCI ? 5173 : 4173));
const htmlReportDir = resolve(
  process.cwd(),
  process.env.PLAYWRIGHT_HTML_REPORT ?? "playwright-report",
);
const htmlOpenSetting = (process.env.PLAYWRIGHT_HTML_REPORT_OPEN ?? "never") as
  | "never"
  | "on-failure"
  | "always";
const junitOutputName =
  process.env.PLAYWRIGHT_JUNIT_OUTPUT_NAME ?? "results.xml";
const reporter: ReporterDescription[] = [
  [isCI ? "dot" : "line"],
  ["html", { open: htmlOpenSetting, outputFolder: htmlReportDir }],
  ["junit", { outputFile: resolve(htmlReportDir, junitOutputName) }],
];

export default defineConfig({
  testDir: "tests/proofs",
  testMatch: "**/passkey-register-positive.proof.ts",
  timeout: 90_000,
  retries: isCI ? 2 : 0,
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
        AUTH_DEV_LOGIN: "1",
        CSRF_ALLOWED_ORIGINS: `http://localhost:${PORT}`,
        WEBAUTHN_RP_ID: "localhost",
        WEBAUTHN_RP_ORIGIN: `http://localhost:${PORT}`,
        WEBAUTHN_RP_NAME: "Weltgewebe Test",
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
