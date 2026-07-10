import { defineConfig, type ReporterDescription } from "@playwright/test";
import { resolve } from "node:path";

const isCI = /^(1|true)$/i.test(process.env.CI ?? "");
const apiPort = Number(process.env.AUTH_SESSION_PROOF_API_PORT ?? 18081);
const apiOrigin = `http://127.0.0.1:${apiPort}`;
const htmlReportDir = resolve(
  process.cwd(),
  process.env.PLAYWRIGHT_HTML_REPORT ?? "playwright-report-session",
);
const htmlOpenSetting = (process.env.PLAYWRIGHT_HTML_REPORT_OPEN ?? "never") as
  | "never"
  | "on-failure"
  | "always";
const junitOutputName =
  process.env.PLAYWRIGHT_JUNIT_OUTPUT_NAME ?? "session-results.xml";
const reporter: ReporterDescription[] = [
  [isCI ? "dot" : "line"],
  ["html", { open: htmlOpenSetting, outputFolder: htmlReportDir }],
  ["junit", { outputFile: resolve(htmlReportDir, junitOutputName) }],
];

export default defineConfig({
  testDir: "tests/proofs",
  testMatch: "**/session-persistence.proof.ts",
  timeout: 120_000,
  retries: isCI ? 1 : 0,
  workers: 1,
  use: {
    baseURL: apiOrigin,
    trace: "on-first-retry",
  },
  reporter,
  webServer: {
    command: "cargo run --locked --features integration-testing",
    cwd: resolve(process.cwd(), "../api"),
    name: "API",
    url: `${apiOrigin}/health/ready`,
    timeout: 120_000,
    reuseExistingServer: !isCI,
    env: {
      ...process.env,
      API_BIND: `127.0.0.1:${apiPort}`,
      AUTH_COOKIE_SECURE: "0",
      AUTH_SESSION_TTL_SECONDS: "2592000",
      CSRF_ALLOWED_ORIGINS: apiOrigin,
    },
  },
});
