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

          // This middleware is for local DEV-Hosting only, to proxy map styles and basemaps without polluting public/
          // It securely combines /map-style/ and /build/basemap/ into a single /local-basemap/ dev-prefix.
          const repoRoot = path.resolve(__dirname, "../../");
          const mapStyleDir = path.resolve(repoRoot, "map-style");
          const buildBasemapDir = path.resolve(repoRoot, "build", "basemap");

          // Safely parse pathname
          let pathname = "";
          try {
            pathname = decodeURIComponent(req.url.split("?")[0]);
            if (pathname.includes("\0"))
              throw new Error("Null bytes not allowed");
          } catch {
            res.statusCode = 400;
            res.end("Bad Request");
            return;
          }

          // Strip leading slashes to cleanly join
          const safeRelPath = pathname.replace(/^\/+/, "");

          let baseDir = "";
          if (
            safeRelPath.endsWith(".pmtiles") ||
            safeRelPath.endsWith(".meta.json")
          ) {
            baseDir = buildBasemapDir;
          } else {
            baseDir = mapStyleDir;
          }

          // Strict path containment check to prevent directory traversal
          // We use path.join to prefix the relative pathname, then path.resolve to get the absolute path.
          const targetPath = path.resolve(path.join(baseDir, safeRelPath));

          if (
            !targetPath.startsWith(baseDir + path.sep) &&
            targetPath !== baseDir
          ) {
            res.statusCode = 403;
            res.end("Forbidden");
            return;
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

          // Map obvious asset content types
          if (safeRelPath.endsWith(".pmtiles")) {
            res.setHeader("Content-Type", "application/octet-stream");
          } else if (safeRelPath.endsWith(".json")) {
            res.setHeader("Content-Type", "application/json");
          } else if (safeRelPath.endsWith(".pbf")) {
            res.setHeader("Content-Type", "application/x-protobuf");
          } else if (safeRelPath.endsWith(".png")) {
            res.setHeader("Content-Type", "image/png");
          } else if (safeRelPath.endsWith(".svg")) {
            res.setHeader("Content-Type", "image/svg+xml");
          }

          const stat = fs.statSync(targetPath);
          if (!stat.isFile()) {
            res.statusCode = 403;
            res.end("Forbidden");
            return;
          }

          const range = req.headers.range;

          if (range) {
            const parts = range
              .replace(/bytes=/, "")
              .trim()
              .split("-");
            if (parts.length > 2 || parts[0] === "") {
              res.statusCode = 416;
              res.setHeader("Content-Range", `bytes */${stat.size}`);
              res.end();
              return;
            }

            const start = parseInt(parts[0], 10);
            const end = parts[1] ? parseInt(parts[1], 10) : stat.size - 1;

            // Strict Range Validation
            if (
              isNaN(start) ||
              start < 0 ||
              start >= stat.size ||
              (parts[1] !== undefined &&
                parts[1] !== "" &&
                (isNaN(end) || end < start || end >= stat.size))
            ) {
              res.statusCode = 416;
              res.setHeader("Content-Range", `bytes */${stat.size}`);
              res.end();
              return;
            }

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
