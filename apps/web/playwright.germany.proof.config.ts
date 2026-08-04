import { defineConfig } from "@playwright/test";
import baseConfig from "./playwright.config";

export default defineConfig({
  ...baseConfig,
  testDir: "tests/proofs",
  testMatch: "**/basemap-real-germany-visual.proof.ts",
  workers: 1,
});
