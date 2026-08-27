export const DEFAULT_PUBLIC_ORIGIN = "https://commonthing.net";

const PUBLIC_PATHS = ["/map", "/login", "/impressum", "/datenschutz"];

export function normalizePublicOrigin(value) {
  const candidate = String(value ?? "").trim();
  if (!candidate) {
    throw new Error("PUBLIC_APP_BASE_URL must not be empty");
  }

  let url;
  try {
    url = new URL(candidate);
  } catch {
    throw new Error("PUBLIC_APP_BASE_URL must be an absolute URL");
  }

  if (url.protocol !== "https:" && url.protocol !== "http:") {
    throw new Error("PUBLIC_APP_BASE_URL must use http or https");
  }
  if (url.username || url.password) {
    throw new Error("PUBLIC_APP_BASE_URL must not contain credentials");
  }
  if (url.pathname !== "/" || url.search || url.hash) {
    throw new Error(
      "PUBLIC_APP_BASE_URL must contain only an origin without path, query, or fragment",
    );
  }

  return url.origin;
}

export function renderRobots(origin) {
  return [
    "User-agent: *",
    "Allow: /",
    "Disallow: /api/",
    "Disallow: /*?noinert=",
    "",
    `Sitemap: ${origin}/sitemap.xml`,
    "",
  ].join("\n");
}

export function renderSitemap(origin) {
  const entries = PUBLIC_PATHS.map(
    (pathname) => `  <url><loc>${origin}${pathname}</loc></url>`,
  ).join("\n");

  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    entries,
    "</urlset>",
    "",
  ].join("\n");
}

export function createPublicWebAssetsPlugin({
  origin = process.env.PUBLIC_APP_BASE_URL ?? DEFAULT_PUBLIC_ORIGIN,
} = {}) {
  const normalizedOrigin = normalizePublicOrigin(origin);

  return {
    name: "weltgewebe-public-web-assets",
    apply: "build",
    generateBundle() {
      this.emitFile({
        type: "asset",
        fileName: "robots.txt",
        source: renderRobots(normalizedOrigin),
      });
      this.emitFile({
        type: "asset",
        fileName: "sitemap.xml",
        source: renderSitemap(normalizedOrigin),
      });
    },
  };
}
