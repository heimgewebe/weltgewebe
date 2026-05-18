import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vite";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const LOCAL_BASEMAP_PREFIX = "/local-basemap/";
const HAMBURG_PMTILES_FILE = "basemap-hamburg-v0.1.0.pmtiles";

function createLocalBasemapMiddleware() {
  const repoRoot = path.resolve(__dirname, "../../");
  const mapStyleDir = path.resolve(repoRoot, "map-style");
  const buildBasemapDir = path.resolve(repoRoot, "build", "basemap");

  const pipeStreamSafe = (
    stream: fs.ReadStream,
    res: import("http").ServerResponse,
  ) => {
    stream.on("error", (err) => {
      console.error("[local-basemap-serve] Stream error:", err);
      if (!res.headersSent) {
        res.statusCode = 500;
        res.end("Internal Server Error");
      } else {
        res.destroy(err);
      }
    });
    stream.pipe(res);
  };

  return (
    req: import("http").IncomingMessage,
    res: import("http").ServerResponse,
    next: () => void,
  ) => {
    if (!req.url) return next();

    let pathname = "";
    try {
      pathname = decodeURIComponent(req.url.split("?")[0]);
      if (pathname.includes("\0")) throw new Error("Null bytes not allowed");
    } catch {
      res.statusCode = 400;
      res.end("Bad Request");
      return;
    }

    const safeRelPath = pathname
      .replace(/^\/+/, "")
      .replace(/^local-basemap\//, "");

    if (safeRelPath === "style.json") {
      const canonicalStylePath = path.resolve(
        path.join(mapStyleDir, "style.json"),
      );
      if (!canonicalStylePath.startsWith(mapStyleDir + path.sep)) {
        res.statusCode = 403;
        res.end("Forbidden");
        return;
      }
      if (!fs.existsSync(canonicalStylePath)) {
        res.statusCode = 404;
        res.end("Not found");
        return;
      }

      let parsed: Record<string, unknown>;
      try {
        parsed = JSON.parse(
          fs.readFileSync(canonicalStylePath, "utf8"),
        ) as Record<string, unknown>;
      } catch {
        res.statusCode = 500;
        res.end("Invalid style JSON");
        return;
      }

      const sources = parsed.sources as Record<string, unknown> | undefined;
      const basemapSource = sources?.basemap as
        | Record<string, unknown>
        | undefined;
      if (basemapSource) {
        basemapSource.url = `pmtiles://${HAMBURG_PMTILES_FILE}`;
      }

      const body = JSON.stringify(parsed);
      res.setHeader("Access-Control-Allow-Origin", "*");
      res.setHeader("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS");
      res.setHeader("Content-Type", "application/json; charset=utf-8");
      res.setHeader("Content-Length", Buffer.byteLength(body));
      if (req.method === "HEAD") {
        res.end();
      } else {
        res.end(body);
      }
      return;
    }

    let baseDir = "";
    if (
      safeRelPath.endsWith(".pmtiles") ||
      safeRelPath.endsWith(".meta.json")
    ) {
      baseDir = buildBasemapDir;
    } else {
      baseDir = mapStyleDir;
    }

    const targetPath = path.resolve(path.join(baseDir, safeRelPath));
    if (!targetPath.startsWith(baseDir + path.sep) && targetPath !== baseDir) {
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
      res.setHeader("Content-Range", `bytes ${start}-${end}/${stat.size}`);
      res.setHeader("Content-Length", chunksize);

      if (req.method === "HEAD") {
        res.end();
      } else {
        pipeStreamSafe(fs.createReadStream(targetPath, { start, end }), res);
      }
      return;
    }

    res.setHeader("Content-Length", stat.size);
    if (req.method === "HEAD") {
      res.end();
    } else {
      pipeStreamSafe(fs.createReadStream(targetPath), res);
    }
  };
}

export default defineConfig({
  plugins: [
    sveltekit(),
    {
      name: "local-basemap-serve",
      configurePreviewServer(server) {
        server.middlewares.use(
          LOCAL_BASEMAP_PREFIX,
          createLocalBasemapMiddleware(),
        );
      },
      configureServer(server) {
        server.middlewares.use(
          LOCAL_BASEMAP_PREFIX,
          createLocalBasemapMiddleware(),
        );
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
