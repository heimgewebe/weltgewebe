import assert from "node:assert/strict";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";
import { fileURLToPath } from "node:url";

const repositoryRoot = resolve(
  fileURLToPath(new URL("../..", import.meta.url)),
);
const checker = join(repositoryRoot, "scripts", "json-schema-check.mjs");

function run(...arguments_) {
  return spawnSync(process.execPath, [checker, ...arguments_], {
    cwd: repositoryRoot,
    encoding: "utf8",
  });
}

function fixtureDirectory() {
  return mkdtempSync(join(tmpdir(), "weltgewebe-json-schema-check-"));
}

test("compiles draft-07 and validates positive and negative data", () => {
  const directory = fixtureDirectory();
  try {
    const schema = join(directory, "schema.json");
    const valid = join(directory, "valid.json");
    const invalid = join(directory, "invalid.json");
    writeFileSync(
      schema,
      JSON.stringify({
        $schema: "http://json-schema.org/draft-07/schema#",
        type: "object",
        required: ["name"],
        properties: { name: { type: "string", minLength: 1 } },
        additionalProperties: false,
      }),
    );
    writeFileSync(valid, JSON.stringify({ name: "Weltgewebe" }));
    writeFileSync(invalid, JSON.stringify({ name: "" }));

    assert.equal(run("compile", "--schema", schema).status, 0);
    assert.equal(
      run("compile", "--schema", schema, "--spec", "draft7").status,
      0,
    );
    assert.equal(
      run("validate", "--schema", schema, "--data", valid).status,
      0,
    );
    const rejected = run("validate", "--schema", schema, "--data", invalid);
    assert.equal(rejected.status, 1);
    assert.match(rejected.stderr, /invalid/);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test("edge lifecycle schema couples explicit null timestamps", () => {
  const directory = fixtureDirectory();
  try {
    const schema = join(
      repositoryRoot,
      "contracts",
      "domain",
      "edge.schema.json",
    );
    const baseEdge = {
      id: "d3f6c9b1-4e2a-4d7f-8b1c-2a9e5f6d7c8b",
      source_type: "account",
      source_id: "7d97a42e-3704-4a33-a61f-0e0a6b4d65d8",
      target_type: "node",
      target_id: "b52be17c-4ab7-4434-98ce-520f86290cf0",
      edge_kind: "reference",
    };
    const undated = join(directory, "undated.json");
    const datedLegacy = join(directory, "dated-legacy.json");
    const datedNullExpiry = join(directory, "dated-null-expiry.json");
    writeFileSync(
      undated,
      JSON.stringify({ ...baseEdge, created_at: null, expires_at: null }),
    );
    writeFileSync(
      datedLegacy,
      JSON.stringify({ ...baseEdge, created_at: "2026-07-29T12:00:00Z" }),
    );
    writeFileSync(
      datedNullExpiry,
      JSON.stringify({
        ...baseEdge,
        created_at: "2026-07-29T12:00:00Z",
        expires_at: null,
      }),
    );

    assert.equal(
      run("validate", "--schema", schema, "--data", undated).status,
      0,
    );
    assert.equal(
      run("validate", "--schema", schema, "--data", datedLegacy).status,
      0,
    );
    const rejected = run(
      "validate",
      "--schema",
      schema,
      "--data",
      datedNullExpiry,
    );
    assert.equal(rejected.status, 1);
    assert.match(rejected.stderr, /invalid/);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test("auto-detects draft 2020-12 and loads formats", () => {
  const directory = fixtureDirectory();
  try {
    const schema = join(directory, "schema.json");
    const data = join(directory, "data.json");
    writeFileSync(
      schema,
      JSON.stringify({
        $schema: "https://json-schema.org/draft/2020-12/schema",
        type: "object",
        required: ["created_at"],
        properties: { created_at: { type: "string", format: "date-time" } },
      }),
    );
    writeFileSync(data, JSON.stringify({ created_at: "2026-07-28T12:00:00Z" }));

    const result = run("validate", "--schema", schema, "--data", data);
    assert.equal(result.status, 0, result.stderr);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test("rejects unsupported schema declarations even with an explicit spec", () => {
  const directory = fixtureDirectory();
  try {
    const schema = join(directory, "schema.json");
    writeFileSync(
      schema,
      JSON.stringify({
        $schema: "http://json-schema.org/draft-04/schema#",
        type: "object",
      }),
    );

    for (const arguments_ of [
      ["compile", "--schema", schema],
      ["compile", "--schema", schema, "--spec", "draft7"],
    ]) {
      const result = run(...arguments_);
      assert.equal(result.status, 2);
      assert.match(result.stderr, /unsupported schema \$schema/);
    }
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test("rejects an explicit spec that conflicts with the schema declaration", () => {
  const directory = fixtureDirectory();
  try {
    const schema = join(directory, "schema.json");
    writeFileSync(
      schema,
      JSON.stringify({
        $schema: "https://json-schema.org/draft/2020-12/schema",
        type: "object",
      }),
    );

    const result = run("compile", "--schema", schema, "--spec", "draft7");
    assert.equal(result.status, 2);
    assert.match(result.stderr, /conflicts with schema \$schema/);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test("uses exit code 2 for malformed invocation or JSON", () => {
  const directory = fixtureDirectory();
  try {
    const malformed = join(directory, "malformed.json");
    writeFileSync(malformed, "{not-json}\n");

    assert.equal(run("unknown", "--schema", malformed).status, 2);
    assert.equal(run("compile", "--schema", malformed).status, 2);
    assert.equal(run("validate", "--schema", malformed).status, 2);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});
