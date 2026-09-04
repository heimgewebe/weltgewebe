import { defineConfig } from "@playwright/test";
import baseConfig from "./playwright.config";
import { buildExactRevisionAliases } from "./scripts/web-runtime-evidence.mjs";

const inheritedEnvironment: Record<string, string> = Object.fromEntries(
  Object.entries(process.env).filter(
    (entry): entry is [string, string] => typeof entry[1] === "string",
  ),
);
const exactRevisionEnvironment = buildExactRevisionAliases();
const webServer = Array.isArray(baseConfig.webServer)
  ? baseConfig.webServer.map((server) => ({
      ...server,
      // Performance evidence must never come from an unrelated preview that
      // happens to occupy the configured port. A collision fails closed.
      reuseExistingServer: false,
      env: {
        ...inheritedEnvironment,
        ...server.env,
        ...exactRevisionEnvironment,
      },
    }))
  : baseConfig.webServer
    ? {
        ...baseConfig.webServer,
        // Keep local and CI evidence on the same isolation rule.
        reuseExistingServer: false,
        env: {
          ...inheritedEnvironment,
          ...baseConfig.webServer.env,
          ...exactRevisionEnvironment,
        },
      }
    : undefined;

export default defineConfig({
  ...baseConfig,
  webServer,
  testDir: "tests/proofs",
  testMatch: [
    "**/web-runtime.performance.proof.ts",
    "**/map-cardinality.performance.proof.ts",
  ],
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
