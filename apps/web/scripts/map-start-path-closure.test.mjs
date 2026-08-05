import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import {
  collectStaticManifestClosure,
  findMapRuntimeEntry,
  measureMapStartPath,
} from "./map-start-path-closure.mjs";

const manifest = {
  entry: {
    file: "_app/entry.js",
    imports: ["shared"],
    css: ["_app/entry.css"],
    dynamicImports: ["src/lib/map/overlay/nodes.ts", "interaction"],
  },
  shared: { file: "_app/shared.js", imports: ["leaf"] },
  leaf: { file: "_app/leaf.js", css: ["_app/leaf.css"] },
  "src/lib/map/overlay/nodes.ts": {
    file: "_app/nodes.js",
    name: "nodes",
  },
  interaction: { file: "_app/context.js", name: "ContextPanel" },
};

test("collects recursive static imports without counting dynamic roots", () => {
  const result = collectStaticManifestClosure(manifest, ["_app/entry.js"]);
  assert.deepEqual(result.assets, [
    "_app/entry.css",
    "_app/entry.js",
    "_app/leaf.css",
    "_app/leaf.js",
    "_app/shared.js",
  ]);
  assert.equal(findMapRuntimeEntry(manifest), "entry");
});

test("measures HTML assets, static closure and dynamic frontier separately", () => {
  const directory = mkdtempSync(join(tmpdir(), "map-start-path-"));
  try {
    mkdirSync(join(directory, "_app"));
    for (const file of [
      "entry.js",
      "shared.js",
      "leaf.js",
      "nodes.js",
      "context.js",
    ]) {
      writeFileSync(
        join(directory, "_app", file),
        `export const value = ${JSON.stringify(file)};`,
      );
    }
    writeFileSync(join(directory, "_app/entry.css"), ".entry{display:block}");
    writeFileSync(join(directory, "_app/leaf.css"), ".leaf{display:block}");
    writeFileSync(
      join(directory, "map.html"),
      '<link rel="modulepreload" href="./_app/entry.js"><link rel="stylesheet" href="./_app/entry.css">',
    );
    const manifestPath = join(directory, "manifest.json");
    writeFileSync(manifestPath, JSON.stringify(manifest));
    const result = measureMapStartPath({ buildDir: directory, manifestPath });
    assert.equal(result.html_initial.js.asset_count, 1);
    assert.equal(result.static_import_closure.js.asset_count, 3);
    assert.equal(result.additional_static_imports.js.asset_count, 2);
    assert.equal(result.dynamic_frontier.length, 2);
    assert.equal(result.missing_manifest_entries.length, 0);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});
