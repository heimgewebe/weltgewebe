#!/usr/bin/env node
import { isAbsolute, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
  formatTextReport,
  runBudgetCheck,
  webRoot,
} from "./route-performance-budget-core.mjs";

const scriptPath = fileURLToPath(import.meta.url);

export function parseCliArguments(arguments_) {
  const result = {
    buildDir: undefined,
    json: false,
    reportOnly: false,
  };
  for (let index = 0; index < arguments_.length; index += 1) {
    const argument = arguments_[index];
    if (argument === "--json") {
      if (result.json) throw new Error("--json may only be provided once");
      result.json = true;
    } else if (argument === "--report-only") {
      if (result.reportOnly) {
        throw new Error("--report-only may only be provided once");
      }
      result.reportOnly = true;
    } else if (argument === "--build-dir") {
      if (result.buildDir !== undefined) {
        throw new Error("--build-dir may only be provided once");
      }
      const value = arguments_[index + 1];
      if (!value || value.startsWith("--")) {
        throw new Error("--build-dir requires a value");
      }
      result.buildDir = value;
      index += 1;
    } else if (argument.startsWith("--build-dir=")) {
      if (result.buildDir !== undefined) {
        throw new Error("--build-dir may only be provided once");
      }
      const value = argument.slice("--build-dir=".length);
      if (!value) throw new Error("--build-dir requires a value");
      result.buildDir = value;
    } else {
      throw new Error("Unsupported argument: " + argument);
    }
  }
  return result;
}

export function main(arguments_ = process.argv.slice(2)) {
  const options = parseCliArguments(arguments_);
  const result = runBudgetCheck({
    buildDir: options.buildDir
      ? isAbsolute(options.buildDir)
        ? options.buildDir
        : resolve(webRoot, options.buildDir)
      : undefined,
    reportOnly: options.reportOnly,
  });
  console.log(
    options.json ? JSON.stringify(result, null, 2) : formatTextReport(result),
  );
}

const isMain =
  process.argv[1] && resolve(process.argv[1]) === resolve(scriptPath);
if (isMain) main();
