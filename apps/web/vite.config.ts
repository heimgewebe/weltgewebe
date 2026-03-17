import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vite";
import type { ViteDevServer } from "vite";
import fs from "fs";
import path from "path";

function serveSovereignAssets() {
  return {
    name: "serve-sovereign-assets",
    configureServer(server: ViteDevServer) {
      const basemapDir = path.resolve(__dirname, "../../build/basemap");
      const styleDir = path.resolve(__dirname, "../../map-style");

      server.middlewares.use((req, res, next) => {
        if (!req.url) return next();

        let targetPath = null;
        if (req.url.startsWith("/local-basemap/")) {
          targetPath = path.join(
            basemapDir,
            req.url.replace("/local-basemap/", ""),
          );
        } else if (req.url.startsWith("/local-style/")) {
          targetPath = path.join(
            styleDir,
            req.url.replace("/local-style/", ""),
          );
        }

        if (targetPath && fs.existsSync(targetPath)) {
          req.url = "/@fs/" + targetPath;
        }
        next();
      });
    },
  };
}

export default defineConfig({
  plugins: [sveltekit(), serveSovereignAssets()],
  server: {
    fs: {
      allow: ["../../build/basemap", "../../map-style"],
    },
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
  },
});
