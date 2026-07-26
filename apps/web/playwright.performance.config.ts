import { defineConfig } from "@playwright/test";
import baseConfig from "./playwright.config";

export default defineConfig({
  ...baseConfig,
  testDir: "tests/proofs",
  testMatch: "**/web-runtime.performance.proof.ts",
  timeout: 240_000,
  retries: 0,
  workers: 1,
  fullyParallel: false,
  use: {
    ...baseConfig.use,
    browserName: "chromium",
    trace: "retain-on-failure",
  },
});
