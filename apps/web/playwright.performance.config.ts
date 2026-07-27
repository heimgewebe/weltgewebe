import { defineConfig } from "@playwright/test";
import baseConfig from "./playwright.config";

const exactRevision =
  process.env.GIT_COMMIT_SHA ?? process.env.GITHUB_SHA ?? undefined;
const inheritedEnvironment = Object.fromEntries(
  Object.entries(process.env).filter(
    (entry): entry is [string, string] => typeof entry[1] === "string",
  ),
);
const exactRevisionEnvironment = exactRevision
  ? {
      GIT_COMMIT_SHA: exactRevision,
      GITHUB_SHA: exactRevision,
    }
  : {};
const webServer = Array.isArray(baseConfig.webServer)
  ? baseConfig.webServer.map((server) => ({
      ...server,
      env: {
        ...inheritedEnvironment,
        ...server.env,
        ...exactRevisionEnvironment,
      },
    }))
  : baseConfig.webServer
    ? {
        ...baseConfig.webServer,
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
