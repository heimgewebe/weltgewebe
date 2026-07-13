import fs from "node:fs";
import { open, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

import { VectorTile } from "@mapbox/vector-tile";
import Pbf from "pbf";
import { PMTiles, ResolvedValueCache, TileType, tileIdToZxy } from "pmtiles";

const HEADER_SIZE = 127;
const DEFAULT_MAX_SAMPLES = 96;
const MAX_DIRECTORIES = 100_000;
const MAX_DIRECTORY_ENTRIES = 2_000_000;

class NodeFileSource {
  constructor(filePath) {
    this.filePath = path.resolve(filePath);
    this.handle = null;
    this.size = 0;
  }

  getKey() {
    return this.filePath;
  }

  async init() {
    this.handle = await open(this.filePath, "r");
    this.size = (await this.handle.stat()).size;
    if (this.size < HEADER_SIZE) {
      throw new Error(
        `ARCHIVE_TRUNCATED: ${this.filePath} is ${this.size} bytes; ` +
          `expected at least ${HEADER_SIZE}`,
      );
    }
    return this;
  }

  async getBytes(offset, length) {
    if (!Number.isSafeInteger(offset) || !Number.isSafeInteger(length)) {
      throw new Error("RANGE_INVALID: offset and length must be safe integers");
    }
    if (offset < 0 || length <= 0 || offset >= this.size) {
      throw new Error(
        `RANGE_OUT_OF_BOUNDS: ${offset} + ${length} for ${this.size} bytes`,
      );
    }

    const bytesToRead = Math.min(length, this.size - offset);
    const buffer = Buffer.alloc(bytesToRead);
    const { bytesRead } = await this.handle.read(
      buffer,
      0,
      bytesToRead,
      offset,
    );
    if (bytesRead !== bytesToRead) {
      throw new Error(
        `RANGE_READ_SHORT: requested ${bytesToRead} but read ${bytesRead}`,
      );
    }

    return {
      data: buffer.buffer.slice(
        buffer.byteOffset,
        buffer.byteOffset + buffer.byteLength,
      ),
    };
  }

  async close() {
    if (this.handle) {
      await this.handle.close();
      this.handle = null;
    }
  }
}

function invariant(condition, code, message) {
  if (!condition) {
    throw new Error(`${code}: ${message}`);
  }
}

function validateSection(
  name,
  offset,
  length,
  fileSize,
  requiredNonEmpty = false,
) {
  invariant(
    Number.isSafeInteger(offset),
    "HEADER_OFFSET_INVALID",
    `${name} offset ${offset}`,
  );
  invariant(
    Number.isSafeInteger(length),
    "HEADER_LENGTH_INVALID",
    `${name} length ${length}`,
  );
  invariant(
    offset >= HEADER_SIZE,
    "HEADER_OFFSET_BEFORE_DATA",
    `${name} offset ${offset}`,
  );
  invariant(length >= 0, "HEADER_LENGTH_NEGATIVE", `${name} length ${length}`);
  if (requiredNonEmpty) {
    invariant(length > 0, "HEADER_SECTION_EMPTY", `${name} must not be empty`);
  }
  invariant(
    offset + length <= fileSize,
    "HEADER_SECTION_OUT_OF_BOUNDS",
    `${name} ${offset}+${length} exceeds ${fileSize}`,
  );
  return { name, offset, length, end: offset + length };
}

function validateHeader(header, fileSize) {
  invariant(
    header.specVersion === 3,
    "SPEC_VERSION_UNSUPPORTED",
    `expected 3 but found ${header.specVersion}`,
  );
  invariant(
    header.tileType === TileType.Mvt,
    "TILE_TYPE_UNSUPPORTED",
    `expected MVT tile type but found ${header.tileType}`,
  );
  invariant(
    header.minZoom <= header.maxZoom,
    "ZOOM_RANGE_INVALID",
    `${header.minZoom}..${header.maxZoom}`,
  );
  invariant(
    header.minLon >= -180 &&
      header.maxLon <= 180 &&
      header.minLon <= header.maxLon,
    "BOUNDS_LONGITUDE_INVALID",
    `${header.minLon}..${header.maxLon}`,
  );
  invariant(
    header.minLat >= -90 &&
      header.maxLat <= 90 &&
      header.minLat <= header.maxLat,
    "BOUNDS_LATITUDE_INVALID",
    `${header.minLat}..${header.maxLat}`,
  );

  const sections = [
    validateSection(
      "root-directory",
      header.rootDirectoryOffset,
      header.rootDirectoryLength,
      fileSize,
      true,
    ),
    validateSection(
      "json-metadata",
      header.jsonMetadataOffset,
      header.jsonMetadataLength,
      fileSize,
      true,
    ),
    validateSection(
      "leaf-directories",
      header.leafDirectoryOffset,
      header.leafDirectoryLength ?? 0,
      fileSize,
    ),
    validateSection(
      "tile-data",
      header.tileDataOffset,
      header.tileDataLength ?? 0,
      fileSize,
      true,
    ),
  ]
    .filter((section) => section.length > 0)
    .sort((left, right) => left.offset - right.offset);

  for (let index = 1; index < sections.length; index += 1) {
    const previous = sections[index - 1];
    const current = sections[index];
    invariant(
      previous.end <= current.offset,
      "HEADER_SECTION_OVERLAP",
      `${previous.name} ends at ${previous.end}, ` +
        `${current.name} starts at ${current.offset}`,
    );
  }
}

function validateDirectoryEntries(entries, context) {
  invariant(
    Array.isArray(entries) && entries.length > 0,
    "DIRECTORY_EMPTY",
    context,
  );
  for (let index = 0; index < entries.length; index += 1) {
    const entry = entries[index];
    invariant(
      Number.isSafeInteger(entry.tileId) && entry.tileId >= 0,
      "DIRECTORY_TILE_ID_INVALID",
      `${context} index ${index}`,
    );
    invariant(
      Number.isSafeInteger(entry.offset) && entry.offset >= 0,
      "DIRECTORY_OFFSET_INVALID",
      `${context} index ${index}`,
    );
    invariant(
      Number.isSafeInteger(entry.length) && entry.length > 0,
      "DIRECTORY_LENGTH_INVALID",
      `${context} index ${index}`,
    );
    invariant(
      Number.isSafeInteger(entry.runLength) && entry.runLength >= 0,
      "DIRECTORY_RUN_LENGTH_INVALID",
      `${context} index ${index}`,
    );
    if (index > 0) {
      invariant(
        entries[index - 1].tileId < entry.tileId,
        "DIRECTORY_TILE_ID_ORDER",
        `${context} index ${index}`,
      );
    }
  }
}

async function walkDirectories(source, cache, header) {
  const seenDirectories = new Set();
  const tileEntries = [];
  let directoryCount = 0;
  let directoryEntryCount = 0;

  async function visit(offset, length, depth, parentTileId = null) {
    invariant(depth <= 3, "DIRECTORY_DEPTH_EXCEEDED", `depth ${depth}`);
    const key = `${offset}:${length}`;
    invariant(!seenDirectories.has(key), "DIRECTORY_CYCLE_OR_DUPLICATE", key);
    seenDirectories.add(key);
    directoryCount += 1;
    invariant(
      directoryCount <= MAX_DIRECTORIES,
      "DIRECTORY_LIMIT_EXCEEDED",
      String(directoryCount),
    );

    const entries = await cache.getDirectory(source, offset, length, header);
    validateDirectoryEntries(entries, key);
    directoryEntryCount += entries.length;
    invariant(
      directoryEntryCount <= MAX_DIRECTORY_ENTRIES,
      "DIRECTORY_ENTRY_LIMIT_EXCEEDED",
      String(directoryEntryCount),
    );

    if (parentTileId !== null) {
      invariant(
        entries[0].tileId >= parentTileId,
        "LEAF_TILE_RANGE_INVALID",
        `${entries[0].tileId} < ${parentTileId}`,
      );
    }

    for (const entry of entries) {
      if (entry.runLength === 0) {
        const leafLength = header.leafDirectoryLength ?? 0;
        invariant(leafLength > 0, "LEAF_DIRECTORY_SECTION_MISSING", key);
        invariant(
          entry.offset + entry.length <= leafLength,
          "LEAF_DIRECTORY_RANGE_OUT_OF_BOUNDS",
          `${entry.offset}+${entry.length} exceeds ${leafLength}`,
        );
        await visit(
          header.leafDirectoryOffset + entry.offset,
          entry.length,
          depth + 1,
          entry.tileId,
        );
      } else {
        const tileDataLength = header.tileDataLength ?? 0;
        invariant(
          entry.offset + entry.length <= tileDataLength,
          "TILE_DATA_RANGE_OUT_OF_BOUNDS",
          `${entry.offset}+${entry.length} exceeds ${tileDataLength}`,
        );
        tileEntries.push(entry);
      }
    }
  }

  await visit(header.rootDirectoryOffset, header.rootDirectoryLength, 0);

  const sorted = [...tileEntries].sort(
    (left, right) => left.tileId - right.tileId,
  );
  let addressedTiles = 0;
  let previousEnd = -1;
  const contentKeys = new Set();

  for (const entry of sorted) {
    invariant(
      entry.tileId > previousEnd,
      "TILE_ID_RANGE_OVERLAP",
      `${entry.tileId} <= ${previousEnd}`,
    );
    previousEnd = entry.tileId + entry.runLength - 1;
    addressedTiles += entry.runLength;
    contentKeys.add(`${entry.offset}:${entry.length}`);
    tileIdToZxy(entry.tileId);
    tileIdToZxy(previousEnd);
  }

  invariant(
    sorted.length === header.numTileEntries,
    "TILE_ENTRY_COUNT_MISMATCH",
    `${sorted.length} != ${header.numTileEntries}`,
  );
  invariant(
    addressedTiles === header.numAddressedTiles,
    "ADDRESSED_TILE_COUNT_MISMATCH",
    `${addressedTiles} != ${header.numAddressedTiles}`,
  );
  invariant(
    contentKeys.size === header.numTileContents,
    "TILE_CONTENT_COUNT_MISMATCH",
    `${contentKeys.size} != ${header.numTileContents}`,
  );

  return {
    directoryCount,
    directoryEntryCount,
    tileEntries: sorted,
  };
}

function normalizeVectorLayers(metadata) {
  let value = metadata?.vector_layers;
  if (typeof value === "string") {
    try {
      value = JSON.parse(value);
    } catch {
      throw new Error(
        "METADATA_VECTOR_LAYERS_INVALID: string is not valid JSON",
      );
    }
  }
  invariant(
    Array.isArray(value),
    "METADATA_VECTOR_LAYERS_MISSING",
    "vector_layers must be an array",
  );
  const ids = value.map((entry) => entry?.id);
  invariant(
    ids.every((id) => typeof id === "string" && id.length > 0),
    "METADATA_VECTOR_LAYER_ID_INVALID",
    "every vector layer needs a non-empty id",
  );
  return new Set(ids);
}

function decodeMvt(data) {
  let tile;
  try {
    tile = new VectorTile(new Pbf(new Uint8Array(data)));
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    throw new Error(`MVT_DECODE_FAILED: ${message}`);
  }
  const layers = Object.keys(tile.layers);
  invariant(
    layers.length > 0,
    "MVT_LAYERS_EMPTY",
    "decoded tile has no layers",
  );
  return layers;
}

function candidateTileIds(tileEntries, maxSamples) {
  const byZoom = new Map();
  for (const entry of tileEntries) {
    const candidates = [
      entry.tileId,
      entry.tileId + Math.floor((entry.runLength - 1) / 2),
      entry.tileId + entry.runLength - 1,
    ];
    for (const tileId of candidates) {
      const [zoom] = tileIdToZxy(tileId);
      if (!byZoom.has(zoom)) {
        byZoom.set(zoom, new Set());
      }
      byZoom.get(zoom).add(tileId);
    }
  }

  const zooms = [...byZoom.keys()].sort((left, right) => left - right);
  const ordered = [];
  const seen = new Set();
  const append = (tileId) => {
    if (!seen.has(tileId) && ordered.length < maxSamples) {
      seen.add(tileId);
      ordered.push(tileId);
    }
  };

  // First establish stable cross-zoom coverage with first, middle, and last
  // candidates for every zoom. Duplicate positions collapse deterministically.
  for (const zoom of zooms) {
    const ids = [...byZoom.get(zoom)].sort((left, right) => left - right);
    for (const position of [
      0,
      Math.floor((ids.length - 1) / 2),
      ids.length - 1,
    ]) {
      append(ids[position]);
    }
  }

  // Then spend the remaining budget on spatially distributed high-zoom tiles.
  // Those tiles contain the densest style contract (for example buildings),
  // while the first pass already preserves cross-zoom representation.
  for (const zoom of [...zooms].reverse()) {
    const ids = [...byZoom.get(zoom)].sort((left, right) => left - right);
    const remaining = maxSamples - ordered.length;
    if (remaining <= 0) {
      break;
    }
    const take = Math.min(ids.length, remaining);
    for (let index = 0; index < take; index += 1) {
      const position =
        take === 1
          ? Math.floor((ids.length - 1) / 2)
          : Math.round((index * (ids.length - 1)) / (take - 1));
      append(ids[position]);
    }
  }

  return ordered;
}

function loadStyleContract(stylePath, region) {
  const style = JSON.parse(fs.readFileSync(stylePath, "utf8"));
  const alias = `basemap-${region}.pmtiles`;
  const sourceId = Object.entries(style.sources ?? {}).find(
    ([, source]) => source?.url === `pmtiles://${alias}`,
  )?.[0];
  invariant(sourceId, "STYLE_SOURCE_MISSING", `${alias} is not declared`);

  const layers = new Set(
    (style.layers ?? [])
      .filter(
        (entry) =>
          entry.source === sourceId &&
          typeof entry["source-layer"] === "string",
      )
      .map((entry) => entry["source-layer"]),
  );
  invariant(layers.size > 0, "STYLE_SOURCE_LAYERS_MISSING", sourceId);
  return { sourceId, layers };
}

export async function validateArchive({
  region,
  archivePath,
  stylePath,
  maxSamples = DEFAULT_MAX_SAMPLES,
}) {
  invariant(
    typeof region === "string" && region.length > 0,
    "REGION_INVALID",
    String(region),
  );
  invariant(
    Number.isInteger(maxSamples) && maxSamples > 0 && maxSamples <= 256,
    "SAMPLE_LIMIT_INVALID",
    String(maxSamples),
  );

  const source = await new NodeFileSource(archivePath).init();
  try {
    const cache = new ResolvedValueCache(10_000);
    const archive = new PMTiles(source, cache);
    const header = await archive.getHeader();
    validateHeader(header, source.size);

    const metadata = await archive.getMetadata();
    const metadataLayers = normalizeVectorLayers(metadata);
    const styleContract = loadStyleContract(stylePath, region);
    for (const layer of styleContract.layers) {
      invariant(
        metadataLayers.has(layer),
        "STYLE_LAYER_NOT_IN_METADATA",
        `${region}:${layer}`,
      );
    }

    const directory = await walkDirectories(source, cache, header);
    invariant(directory.tileEntries.length > 0, "TILE_ENTRIES_EMPTY", region);

    const candidateIds = candidateTileIds(directory.tileEntries, maxSamples);
    const observedLayers = new Set();
    const samples = [];
    let candidatesRead = 0;

    for (const tileId of candidateIds) {
      if (candidatesRead >= maxSamples) {
        break;
      }
      const [z, x, y] = tileIdToZxy(tileId);
      const response = await archive.getZxy(z, x, y);
      invariant(response?.data, "SAMPLE_TILE_MISSING", `${z}/${x}/${y}`);
      const layers = decodeMvt(response.data);
      for (const layer of layers) {
        invariant(
          metadataLayers.has(layer),
          "SAMPLE_LAYER_NOT_IN_METADATA",
          `${region}:${layer} at ${z}/${x}/${y}`,
        );
        observedLayers.add(layer);
      }
      samples.push({
        tile_id: tileId,
        z,
        x,
        y,
        bytes: response.data.byteLength,
        layers,
      });
      candidatesRead += 1;

      if (
        [...styleContract.layers].every((layer) => observedLayers.has(layer))
      ) {
        break;
      }
    }

    for (const layer of styleContract.layers) {
      invariant(
        observedLayers.has(layer),
        "STYLE_LAYER_NOT_OBSERVED_IN_SAMPLE",
        `${region}:${layer}; read ${samples.length} tiles`,
      );
    }

    return {
      region,
      archive_path: source.filePath,
      file_size: source.size,
      header: {
        spec_version: header.specVersion,
        tile_type: header.tileType,
        min_zoom: header.minZoom,
        max_zoom: header.maxZoom,
        bounds: [header.minLon, header.minLat, header.maxLon, header.maxLat],
        num_addressed_tiles: header.numAddressedTiles,
        num_tile_entries: header.numTileEntries,
        num_tile_contents: header.numTileContents,
      },
      directory: {
        directory_count: directory.directoryCount,
        directory_entry_count: directory.directoryEntryCount,
        tile_entry_count: directory.tileEntries.length,
      },
      metadata_layers: [...metadataLayers].sort(),
      style_source_id: styleContract.sourceId,
      style_layers: [...styleContract.layers].sort(),
      observed_sample_layers: [...observedLayers].sort(),
      samples,
    };
  } finally {
    await source.close();
  }
}

function parseArguments(argv) {
  const result = {
    archives: [],
    stylePath: null,
    outputPath: null,
    maxSamples: DEFAULT_MAX_SAMPLES,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument === "--archive") {
      const value = argv[++index];
      const separator = value?.indexOf("=");
      invariant(
        separator > 0,
        "ARGUMENT_INVALID",
        "--archive expects region=path",
      );
      result.archives.push({
        region: value.slice(0, separator),
        archivePath: value.slice(separator + 1),
      });
    } else if (argument === "--style") {
      result.stylePath = argv[++index];
    } else if (argument === "--output") {
      result.outputPath = argv[++index];
    } else if (argument === "--max-samples") {
      result.maxSamples = Number(argv[++index]);
    } else {
      throw new Error(`ARGUMENT_UNKNOWN: ${argument}`);
    }
  }

  invariant(
    result.archives.length > 0,
    "ARGUMENT_ARCHIVES_MISSING",
    "at least one --archive region=path is required",
  );
  invariant(result.stylePath, "ARGUMENT_STYLE_MISSING", "--style is required");
  return result;
}

async function main() {
  const args = parseArguments(process.argv.slice(2));
  const reports = [];
  for (const archive of args.archives) {
    reports.push(
      await validateArchive({
        ...archive,
        stylePath: args.stylePath,
        maxSamples: args.maxSamples,
      }),
    );
  }

  const output = {
    schema_version: 1,
    verdict: "PROVEN",
    validator: "bounded-pmtiles-deep-validation-v1",
    max_samples_per_archive: args.maxSamples,
    archives: reports,
    does_not_establish: [
      "full_tile_by_tile_scan",
      "cartographic_completeness",
      "osm_semantic_correctness",
      "source_data_freshness",
    ],
  };
  const json = `${JSON.stringify(output, null, 2)}\n`;
  if (args.outputPath) {
    await writeFile(args.outputPath, json, "utf8");
  }
  process.stdout.write(json);
}

const isEntryPoint =
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isEntryPoint) {
  main().catch((error) => {
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`NOT_PROVEN: ${message}\n`);
    process.exitCode = 1;
  });
}
