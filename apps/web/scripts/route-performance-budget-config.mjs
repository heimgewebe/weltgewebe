import { isAbsolute } from "node:path";

const ROOT_KEYS = new Set([
  "schema_version",
  "measurement",
  "output_directories",
  "routes",
  "emitted_assets",
]);
const ROUTE_BUDGET_KEYS = new Set([
  "max_initial_js_gzip_bytes",
  "max_initial_css_gzip_bytes",
  "forbid_css_markers",
  "require_css_markers",
  "min_initial_js_assets",
  "min_initial_css_assets",
]);
const ASSET_BUDGET_KEYS = new Set([
  "directory",
  "filename_prefix",
  "required_extension",
  "forbid_extensions",
  "max_bytes",
]);

function isPlainObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function assertExactKeys(value, allowedKeys, label) {
  for (const key of Object.keys(value)) {
    if (!allowedKeys.has(key)) {
      throw new Error(label + ": unsupported field " + JSON.stringify(key));
    }
  }
}

function assertInteger(value, label, minimum) {
  if (!Number.isInteger(value) || value < minimum) {
    throw new Error(label + " must be an integer >= " + minimum);
  }
}

function assertStringArray(value, label) {
  if (
    !Array.isArray(value) ||
    value.some((entry) => typeof entry !== "string" || entry.length === 0)
  ) {
    throw new Error(label + " must contain only non-empty strings");
  }
  if (new Set(value).size !== value.length) {
    throw new Error(label + " must not contain duplicates");
  }
}

export function assertSafeRelativeDirectory(value, label) {
  if (
    typeof value !== "string" ||
    value.length === 0 ||
    isAbsolute(value) ||
    value.includes("\\") ||
    value
      .split("/")
      .some((segment) => segment === "" || segment === "." || segment === "..")
  ) {
    throw new Error(label + " must be a safe relative directory");
  }
}

export function routeIdToHtmlFile(routeId) {
  if (
    typeof routeId !== "string" ||
    !routeId.startsWith("/") ||
    routeId.includes("\\") ||
    routeId.includes("?") ||
    routeId.includes("#") ||
    routeId.includes("//")
  ) {
    throw new Error("Route ID must be an absolute clean path: " + routeId);
  }
  if (routeId === "/") return "index.html";

  const trailingSlash = routeId.endsWith("/");
  const path = routeId.slice(1, trailingSlash ? -1 : undefined);
  const segments = path.split("/");
  if (
    segments.some(
      (segment) => segment.length === 0 || segment === "." || segment === "..",
    )
  ) {
    throw new Error("Route ID contains an unsafe segment: " + routeId);
  }
  return trailingSlash ? path + "/index.html" : path + ".html";
}

function validateRouteBudgetDefinition(routeId, budget) {
  if (!isPlainObject(budget)) {
    throw new Error(routeId + ": route budget must be an object");
  }
  assertExactKeys(budget, ROUTE_BUDGET_KEYS, routeId);
  assertInteger(
    budget.min_initial_js_assets,
    routeId + ": min_initial_js_assets",
    1,
  );
  assertInteger(
    budget.min_initial_css_assets,
    routeId + ": min_initial_css_assets",
    1,
  );
  assertInteger(
    budget.max_initial_js_gzip_bytes,
    routeId + ": max_initial_js_gzip_bytes",
    0,
  );
  assertInteger(
    budget.max_initial_css_gzip_bytes,
    routeId + ": max_initial_css_gzip_bytes",
    0,
  );
  assertStringArray(
    budget.forbid_css_markers,
    routeId + ": forbid_css_markers",
  );
  assertStringArray(
    budget.require_css_markers,
    routeId + ": require_css_markers",
  );
}

function validateAssetBudgetDefinition(label, budget) {
  if (!isPlainObject(budget)) {
    throw new Error(label + ": emitted asset budget must be an object");
  }
  assertExactKeys(budget, ASSET_BUDGET_KEYS, label);
  assertSafeRelativeDirectory(budget.directory, label + ": directory");
  if (
    typeof budget.filename_prefix !== "string" ||
    budget.filename_prefix.length === 0 ||
    budget.filename_prefix.includes("/") ||
    budget.filename_prefix.includes("\\")
  ) {
    throw new Error(label + ": filename_prefix must be a safe filename prefix");
  }
  if (
    typeof budget.required_extension !== "string" ||
    !budget.required_extension.startsWith(".") ||
    budget.required_extension.includes("/") ||
    budget.required_extension.includes("\\")
  ) {
    throw new Error(label + ": required_extension must be a safe extension");
  }
  assertStringArray(budget.forbid_extensions, label + ": forbid_extensions");
  for (const extension of budget.forbid_extensions) {
    if (
      !extension.startsWith(".") ||
      extension.includes("/") ||
      extension.includes("\\")
    ) {
      throw new Error(label + ": forbidden extension is unsafe: " + extension);
    }
  }
  assertInteger(budget.max_bytes, label + ": max_bytes", 0);
}

export function validatePerformanceBudget(value) {
  if (!isPlainObject(value)) {
    throw new Error("Route performance budget must be a JSON object");
  }
  assertExactKeys(value, ROOT_KEYS, "route performance budget");
  if (value.schema_version !== 2) {
    throw new Error("Route performance budget must use schema_version 2");
  }
  if (typeof value.measurement !== "string" || value.measurement.length === 0) {
    throw new Error("Route performance budget must define measurement");
  }
  assertStringArray(value.output_directories, "output_directories");
  for (const directory of value.output_directories) {
    assertSafeRelativeDirectory(directory, "output_directories entry");
  }
  if (!isPlainObject(value.routes) || Object.keys(value.routes).length === 0) {
    throw new Error("Route performance budget must define at least one route");
  }
  for (const [routeId, budget] of Object.entries(value.routes)) {
    routeIdToHtmlFile(routeId);
    validateRouteBudgetDefinition(routeId, budget);
  }
  if (!isPlainObject(value.emitted_assets)) {
    throw new Error("Route performance budget must define emitted_assets");
  }
  for (const [label, budget] of Object.entries(value.emitted_assets)) {
    if (label.length === 0) {
      throw new Error("Emitted asset budget labels must not be empty");
    }
    validateAssetBudgetDefinition(label, budget);
  }
  return value;
}

export function parsePerformanceBudget(text) {
  let parsed;
  try {
    parsed = JSON.parse(text);
  } catch (error) {
    throw new Error(
      "Route performance budget is not valid JSON: " +
        (error instanceof Error ? error.message : String(error)),
    );
  }
  return validatePerformanceBudget(parsed);
}
