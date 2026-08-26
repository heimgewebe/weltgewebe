import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_PUBLIC_ORIGIN,
  createPublicWebAssetsPlugin,
  normalizePublicOrigin,
  renderRobots,
  renderSitemap,
} from "./generate-public-web-assets.mjs";

test("uses the canonical CommonThing production origin by default", () => {
  assert.equal(DEFAULT_PUBLIC_ORIGIN, "https://commonthing.net");
});

test("emits CommonThing crawler assets when no origin override is supplied", () => {
  const emitted = [];
  const plugin = createPublicWebAssetsPlugin();

  plugin.generateBundle.call({
    emitFile(asset) {
      emitted.push(asset);
      return String(emitted.length);
    },
  });

  assert.match(
    emitted[0].source,
    /^Sitemap: https:\/\/commonthing\.net\/sitemap\.xml$/m,
  );
  assert.match(emitted[1].source, /https:\/\/commonthing\.net\/map/);
  assert.doesNotMatch(emitted[1].source, /https:\/\/weltgewebe\.net/);
});

test("normalizes an origin and removes a trailing slash", () => {
  assert.equal(
    normalizePublicOrigin("https://staging.example.org/"),
    "https://staging.example.org",
  );
});

test("rejects values that are not origin-only HTTP(S) URLs", () => {
  for (const value of [
    "",
    "weltgewebe.net",
    "ftp://weltgewebe.net",
    "https://user:pass@weltgewebe.net",
    "https://weltgewebe.net/path",
    "https://weltgewebe.net/?preview=1",
    "https://weltgewebe.net/#fragment",
  ]) {
    assert.throws(() => normalizePublicOrigin(value), { name: "Error" });
  }
});

test("renders crawler exclusions and one origin-consistent sitemap", () => {
  const origin = "https://preview.example.org";
  const robots = renderRobots(origin);
  const sitemap = renderSitemap(origin);

  assert.match(robots, /^Disallow: \/api\/$/m);
  assert.match(robots, /^Disallow: \/\*\?noinert=$/m);
  assert.match(
    robots,
    /^Sitemap: https:\/\/preview\.example\.org\/sitemap\.xml$/m,
  );
  assert.match(sitemap, /https:\/\/preview\.example\.org\/impressum/);
  assert.doesNotMatch(sitemap, /weltgewebe\.net/);
});

test("emits both assets through one Vite build plugin", () => {
  const emitted = [];
  const plugin = createPublicWebAssetsPlugin({
    origin: "https://staging.example.org/",
  });

  plugin.generateBundle.call({
    emitFile(asset) {
      emitted.push(asset);
      return String(emitted.length);
    },
  });

  assert.deepEqual(
    emitted.map(({ type, fileName }) => ({ type, fileName })),
    [
      { type: "asset", fileName: "robots.txt" },
      { type: "asset", fileName: "sitemap.xml" },
    ],
  );
  assert.match(
    emitted[0].source,
    /https:\/\/staging\.example\.org\/sitemap\.xml/,
  );
  assert.match(
    emitted[1].source,
    /https:\/\/staging\.example\.org\/datenschutz/,
  );
  assert.doesNotMatch(emitted[1].source, /weltgewebe\.net/);
});
