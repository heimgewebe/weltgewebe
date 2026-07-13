import assert from "node:assert/strict";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { validateArchive } from "./validate-pmtiles.mjs";

function encodeVarint(value) {
  const bytes = [];
  let remaining = value;
  do {
    let byte = remaining & 0x7f;
    remaining = Math.floor(remaining / 128);
    if (remaining > 0) {
      byte |= 0x80;
    }
    bytes.push(byte);
  } while (remaining > 0);
  return Buffer.from(bytes);
}

function writeUint64(buffer, offset, value) {
  buffer.writeUInt32LE(value >>> 0, offset);
  buffer.writeUInt32LE(Math.floor(value / 2 ** 32), offset + 4);
}

function writeCoordinate(buffer, offset, value) {
  buffer.writeInt32LE(Math.round(value * 10_000_000), offset);
}

function minimalMvt() {
  const feature = Buffer.from([0x18, 0x01, 0x22, 0x03, 0x09, 0x00, 0x00]);
  const layer = Buffer.concat([
    Buffer.from([0x0a, 0x05]),
    Buffer.from("water", "utf8"),
    Buffer.from([0x12, feature.length]),
    feature,
    Buffer.from([0x28, 0x80, 0x20]),
    Buffer.from([0x78, 0x02]),
  ]);
  return Buffer.concat([Buffer.from([0x1a, layer.length]), layer]);
}

function makeArchive({ corruptDirectory = false, corruptMvt = false } = {}) {
  const tile = corruptMvt
    ? Buffer.alloc(minimalMvt().length, 0xff)
    : minimalMvt();
  const metadata = Buffer.from(
    JSON.stringify({
      vector_layers: [
        {
          id: "water",
          fields: {},
          minzoom: 0,
          maxzoom: 0,
        },
      ],
    }),
    "utf8",
  );
  const directory = Buffer.concat([
    encodeVarint(corruptDirectory ? 0 : 1),
    ...(corruptDirectory
      ? []
      : [
          encodeVarint(0),
          encodeVarint(1),
          encodeVarint(tile.length),
          encodeVarint(1),
        ]),
  ]);

  const rootOffset = 127;
  const metadataOffset = rootOffset + directory.length;
  const leafOffset = metadataOffset + metadata.length;
  const tileOffset = leafOffset;
  const header = Buffer.alloc(127);
  header.write("PMTiles", 0, "ascii");
  header[7] = 3;
  writeUint64(header, 8, rootOffset);
  writeUint64(header, 16, directory.length);
  writeUint64(header, 24, metadataOffset);
  writeUint64(header, 32, metadata.length);
  writeUint64(header, 40, leafOffset);
  writeUint64(header, 48, 0);
  writeUint64(header, 56, tileOffset);
  writeUint64(header, 64, tile.length);
  writeUint64(header, 72, corruptDirectory ? 0 : 1);
  writeUint64(header, 80, corruptDirectory ? 0 : 1);
  writeUint64(header, 88, corruptDirectory ? 0 : 1);
  header[96] = 1;
  header[97] = 1;
  header[98] = 1;
  header[99] = 1;
  header[100] = 0;
  header[101] = 0;
  writeCoordinate(header, 102, -180);
  writeCoordinate(header, 106, -85);
  writeCoordinate(header, 110, 180);
  writeCoordinate(header, 114, 85);
  header[118] = 0;
  writeCoordinate(header, 119, 0);
  writeCoordinate(header, 123, 0);

  return Buffer.concat([header, directory, metadata, tile]);
}

async function fixtureContext(t) {
  const directory = await mkdtemp(path.join(os.tmpdir(), "pmtiles-validator-"));
  t.after(async () => rm(directory, { recursive: true, force: true }));
  const stylePath = path.join(directory, "style.json");
  await writeFile(
    stylePath,
    JSON.stringify({
      version: 8,
      sources: {
        fixture: {
          type: "vector",
          url: "pmtiles://basemap-fixture.pmtiles",
        },
      },
      layers: [
        {
          id: "water",
          type: "fill",
          source: "fixture",
          "source-layer": "water",
        },
      ],
    }),
  );
  return { directory, stylePath };
}

test("accepts a structurally valid PMTiles v3 archive and decodes MVT", async (t) => {
  const { directory, stylePath } = await fixtureContext(t);
  const archivePath = path.join(directory, "valid.pmtiles");
  await writeFile(archivePath, makeArchive());

  const report = await validateArchive({
    region: "fixture",
    archivePath,
    stylePath,
    maxSamples: 4,
  });

  assert.equal(report.header.spec_version, 3);
  assert.equal(report.directory.directory_count, 1);
  assert.equal(report.directory.tile_entry_count, 1);
  assert.deepEqual(report.observed_sample_layers, ["water"]);
  assert.equal(report.samples.length, 1);
});

test("rejects a truncated archive before publication", async (t) => {
  const { directory, stylePath } = await fixtureContext(t);
  const archivePath = path.join(directory, "truncated.pmtiles");
  await writeFile(archivePath, makeArchive().subarray(0, 100));

  await assert.rejects(
    validateArchive({ region: "fixture", archivePath, stylePath }),
    /ARCHIVE_TRUNCATED/,
  );
});

test("rejects an empty or corrupt root directory", async (t) => {
  const { directory, stylePath } = await fixtureContext(t);
  const archivePath = path.join(directory, "directory-corrupt.pmtiles");
  await writeFile(archivePath, makeArchive({ corruptDirectory: true }));

  await assert.rejects(
    validateArchive({ region: "fixture", archivePath, stylePath }),
    /DIRECTORY_EMPTY|TILE_ENTRIES_EMPTY/,
  );
});

test("rejects malformed MVT tile payloads", async (t) => {
  const { directory, stylePath } = await fixtureContext(t);
  const archivePath = path.join(directory, "mvt-corrupt.pmtiles");
  await writeFile(archivePath, makeArchive({ corruptMvt: true }));

  await assert.rejects(
    validateArchive({ region: "fixture", archivePath, stylePath }),
    /MVT_DECODE_FAILED|MVT_LAYERS_EMPTY/,
  );
});
