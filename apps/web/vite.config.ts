import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vite";
import fs from "fs";
import path from "path";

export default defineConfig({
  plugins: [
    sveltekit(),
    {
      name: "local-basemap-serve",
      configureServer(server) {
        server.middlewares.use("/local-basemap/", (req, res, next) => {
          if (!req.url) return next();

          const repoRoot = path.resolve(__dirname, "../../");
          const mapStyleDir = path.join(repoRoot, "map-style");
          const buildBasemapDir = path.join(repoRoot, "build", "basemap");

          // Strip query parameters from URL
          const pathname = req.url.split("?")[0];

          let targetPath = "";
          if (
            pathname.endsWith(".pmtiles") ||
            pathname.endsWith(".meta.json")
          ) {
            targetPath = path.join(buildBasemapDir, pathname);
          } else {
            targetPath = path.join(mapStyleDir, pathname);
          }

          if (!fs.existsSync(targetPath)) {
            res.statusCode = 404;
            res.end("Not found");
            return;
          }

          res.setHeader("Access-Control-Allow-Origin", "*");
          res.setHeader("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS");
          res.setHeader("Access-Control-Allow-Headers", "Range, If-None-Match");
          res.setHeader(
            "Access-Control-Expose-Headers",
            "ETag, Content-Length, Content-Range, Accept-Ranges",
          );
          res.setHeader("Accept-Ranges", "bytes");

          if (req.method === "OPTIONS") {
            res.statusCode = 204;
            res.end();
            return;
          }

          if (pathname.endsWith(".pmtiles")) {
            res.setHeader("Content-Type", "application/octet-stream");
          } else if (pathname.endsWith(".json")) {
            res.setHeader("Content-Type", "application/json");
          }

          const stat = fs.statSync(targetPath);
          const range = req.headers.range;

          if (range) {
            const parts = range.replace(/bytes=/, "").split("-");
            const start = parseInt(parts[0], 10);
            const end = parts[1] ? parseInt(parts[1], 10) : stat.size - 1;
            const chunksize = end - start + 1;

            res.statusCode = 206;
            res.setHeader(
              "Content-Range",
              `bytes ${start}-${end}/${stat.size}`,
            );
            res.setHeader("Content-Length", chunksize);

            if (req.method === "HEAD") {
              res.end();
            } else {
              fs.createReadStream(targetPath, { start, end }).pipe(res);
            }
          } else {
            res.setHeader("Content-Length", stat.size);
            if (req.method === "HEAD") {
              res.end();
            } else {
              fs.createReadStream(targetPath).pipe(res);
            }
          }
        });
      },
    },
  ],
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
  },
});
