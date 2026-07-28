#!/usr/bin/env node
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import Ajv from "ajv";
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";

const SUPPORTED_COMMANDS = new Set(["compile", "validate"]);
const SUPPORTED_SPECS = new Set(["draft7", "draft2020"]);
const SCHEMA_DECLARATIONS = new Map([
  ["http://json-schema.org/draft-07/schema", "draft7"],
  ["http://json-schema.org/draft-07/schema#", "draft7"],
  ["https://json-schema.org/draft-07/schema", "draft7"],
  ["https://json-schema.org/draft-07/schema#", "draft7"],
  ["http://json-schema.org/draft/2020-12/schema", "draft2020"],
  ["http://json-schema.org/draft/2020-12/schema#", "draft2020"],
  ["https://json-schema.org/draft/2020-12/schema", "draft2020"],
  ["https://json-schema.org/draft/2020-12/schema#", "draft2020"],
]);

function usage() {
  return [
    "Usage:",
    "  node scripts/json-schema-check.mjs compile --schema <file> [--spec draft7|draft2020]",
    "  node scripts/json-schema-check.mjs validate --schema <file> --data <file> [--spec draft7|draft2020]",
  ].join("\n");
}

function parseArguments(arguments_) {
  const [command, ...rest] = arguments_;
  if (!SUPPORTED_COMMANDS.has(command)) {
    throw new Error(
      `unsupported command ${JSON.stringify(command)}\n${usage()}`,
    );
  }

  const options = {
    command,
    schema: undefined,
    data: undefined,
    spec: undefined,
  };
  for (let index = 0; index < rest.length; index += 1) {
    const argument = rest[index];
    const assignValue = (name) => {
      const value = rest[index + 1];
      if (!value || value.startsWith("--")) {
        throw new Error(`${name} requires a value`);
      }
      index += 1;
      return value;
    };

    if (argument === "--schema") {
      if (options.schema !== undefined)
        throw new Error("--schema may only be provided once");
      options.schema = assignValue("--schema");
    } else if (argument.startsWith("--schema=")) {
      if (options.schema !== undefined)
        throw new Error("--schema may only be provided once");
      options.schema = argument.slice("--schema=".length);
    } else if (argument === "--data") {
      if (options.data !== undefined)
        throw new Error("--data may only be provided once");
      options.data = assignValue("--data");
    } else if (argument.startsWith("--data=")) {
      if (options.data !== undefined)
        throw new Error("--data may only be provided once");
      options.data = argument.slice("--data=".length);
    } else if (argument === "--spec") {
      if (options.spec !== undefined)
        throw new Error("--spec may only be provided once");
      options.spec = assignValue("--spec");
    } else if (argument.startsWith("--spec=")) {
      if (options.spec !== undefined)
        throw new Error("--spec may only be provided once");
      options.spec = argument.slice("--spec=".length);
    } else {
      throw new Error(
        `unsupported argument ${JSON.stringify(argument)}\n${usage()}`,
      );
    }
  }

  if (!options.schema) throw new Error(`--schema is required\n${usage()}`);
  if (command === "validate" && !options.data) {
    throw new Error(`validate requires --data\n${usage()}`);
  }
  if (command === "compile" && options.data !== undefined) {
    throw new Error("compile does not accept --data");
  }
  if (options.spec !== undefined && !SUPPORTED_SPECS.has(options.spec)) {
    throw new Error(`unsupported --spec ${JSON.stringify(options.spec)}`);
  }

  return options;
}

function readJson(path, label) {
  const absolutePath = resolve(path);
  let text;
  try {
    text = readFileSync(absolutePath, "utf8");
  } catch (error) {
    throw new Error(
      `${label} cannot be read at ${path}: ${error instanceof Error ? error.message : String(error)}`,
    );
  }
  try {
    return JSON.parse(text);
  } catch (error) {
    throw new Error(
      `${label} is not valid JSON at ${path}: ${error instanceof Error ? error.message : String(error)}`,
    );
  }
}

function detectDeclaredSpec(schema) {
  const declaration = schema?.$schema;
  if (declaration === undefined) return undefined;
  if (typeof declaration !== "string") {
    throw new Error("schema $schema declaration must be a string");
  }
  const declaredSpec = SCHEMA_DECLARATIONS.get(declaration);
  if (!declaredSpec) {
    throw new Error(`unsupported schema $schema ${JSON.stringify(declaration)}`);
  }
  return declaredSpec;
}

function detectSpec(schema, explicitSpec) {
  const declaredSpec = detectDeclaredSpec(schema);
  if (explicitSpec && declaredSpec && explicitSpec !== declaredSpec) {
    throw new Error(
      `--spec ${JSON.stringify(explicitSpec)} conflicts with schema $schema ${JSON.stringify(schema.$schema)}`,
    );
  }
  return explicitSpec ?? declaredSpec ?? "draft7";
}

function createValidator(spec) {
  const options = { allErrors: true, strict: false };
  const ajv = spec === "draft2020" ? new Ajv2020(options) : new Ajv(options);
  addFormats(ajv);
  return ajv;
}

function formatErrors(errors) {
  return JSON.stringify(errors ?? [], null, 2);
}

export function main(arguments_ = process.argv.slice(2)) {
  const options = parseArguments(arguments_);
  const schema = readJson(options.schema, "schema");
  const spec = detectSpec(schema, options.spec);
  const ajv = createValidator(spec);
  const validate = ajv.compile(schema);

  if (options.command === "compile") {
    console.log(`schema ${options.schema} is valid (${spec})`);
    return 0;
  }

  const data = readJson(options.data, "data");
  if (validate(data)) {
    console.log(`${options.data} valid`);
    return 0;
  }

  console.error(`${options.data} invalid`);
  console.error(formatErrors(validate.errors));
  return 1;
}

const isMain =
  process.argv[1] &&
  resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url));
if (isMain) {
  try {
    process.exitCode = main();
  } catch (error) {
    console.error(
      `error: ${error instanceof Error ? error.message : String(error)}`,
    );
    process.exitCode = 2;
  }
}
