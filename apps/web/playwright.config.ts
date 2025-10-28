import { defineConfig, type ReporterDescription } from "@playwright/test";

const PORT = Number(process.env.PORT ?? 4173);
const shouldStartWebServer = process.env.PLAYWRIGHT_SKIP_WEBSERVER !== "1";
const htmlReportDir = process.env.PLAYWRIGHT_HTML_REPORT ?? "playwright-report";
const reporter: ReporterDescription[] = [
  ["line"],
  ["html", { open: "never", outputFolder: htmlReportDir }]
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
          timeout: 120_000,
          reuseExistingServer: !process.env.CI
        }
      }
    : {})
});
