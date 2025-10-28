import { defineConfig, type ReporterDescription } from "@playwright/test";
import { resolve } from "node:path";

const PORT = Number(process.env.PORT ?? (process.env.CI ? 5173 : 4173));
const shouldStartWebServer = process.env.PLAYWRIGHT_SKIP_WEBSERVER !== "1";
const htmlReportDir = resolve(
  process.cwd(),
  process.env.PLAYWRIGHT_HTML_REPORT ?? "playwright-report"
);
// Ensure CI uploads always find an HTML report directory.
const htmlReporter: ReporterDescription = [
  "html",
  { open: "never", outputFolder: htmlReportDir }
];
const isCI = /^(1|true)$/i.test(process.env.CI ?? "");
const consoleReporter: ReporterDescription = isCI ? ["dot"] : ["line"];
const junitReporter: ReporterDescription = ["junit", { outputFile: resolve(htmlReportDir, "results.xml") }];
const reporter: ReporterDescription[] = [
  consoleReporter,
  htmlReporter,
  ...(isCI ? [junitReporter] : [])
];

export default defineConfig({
  testDir: "tests",
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? undefined : 2,
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: "on-first-retry"
  },
  reporter,
  ...(shouldStartWebServer
    ? {
        webServer: {
          command: `npm run preview -- --host 0.0.0.0 --port ${PORT}`,
          url: `http://127.0.0.1:${PORT}`,
          timeout: 90_000,
          reuseExistingServer: !process.env.CI
        }
      }
    : {})
});
