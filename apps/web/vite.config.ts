import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8080",
        changeOrigin: true,
      },
    },
  },
  preview: {
    port: process.env.PREVIEW_PORT
      ? parseInt(process.env.PREVIEW_PORT, 10) || 4173
      : 4173,
    strictPort: true,
    // No proxy in preview mode - tests use Playwright mocking instead
  },
});
