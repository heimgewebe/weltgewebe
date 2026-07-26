import { createHash } from "node:crypto";
import { lstatSync, readFileSync, readdirSync, realpathSync } from "node:fs";
import { isAbsolute, relative, resolve, sep } from "node:path";

const SHA256_PATTERN = /^[0-9a-f]{64}$/;
const REVISION_PATTERN = /^[0-9a-f]{40}$/;
const VERSION_PATH = "_app/version.json";
const COMPILE_REVISION_PATH = "_app/compile-revision.json";

function isInside(root, target) {
  const pathFromRoot = relative(root, target);
  return (
    pathFromRoot === "" ||
    (!pathFromRoot.startsWith(".." + sep) &&
      pathFromRoot !== ".." &&
      !isAbsolute(pathFromRoot))
  );
}

function portablePath(path) {
  return path.split(sep).join("/");
}

function readCompileRevision(root) {
  const markerPath = resolve(root, COMPILE_REVISION_PATH);
  const metadata = lstatSync(markerPath);
  if (!metadata.isFile() || metadata.isSymbolicLink()) {
    throw new Error("Compiled revision marker is not a regular file");
  }
  const resolvedMarker = realpathSync(markerPath);
  if (!isInside(root, resolvedMarker)) {
    throw new Error("Compiled revision marker escapes the build root");
  }
  const payload = JSON.parse(readFileSync(markerPath, "utf8"));
  if (
    !payload ||
    typeof payload !== "object" ||
    Array.isArray(payload) ||
    payload.schema_version !== 1 ||
    typeof payload.compile_revision !== "string" ||
    !REVISION_PATTERN.test(payload.compile_revision)
  ) {
    throw new Error("Compiled revision marker is invalid");
  }
  return payload.compile_revision;
}

function collectFiles(root, directory = root, files = []) {
  for (const name of readdirSync(directory).sort()) {
    const path = resolve(directory, name);
    const metadata = lstatSync(path);
    const relativePath = portablePath(relative(root, path));
    if (metadata.isSymbolicLink()) {
      throw new Error(`Build artifact contains symbolic link: ${relativePath}`);
    }
    if (metadata.isDirectory()) {
      collectFiles(root, path, files);
      continue;
    }
    if (!metadata.isFile()) {
      throw new Error(
        `Build artifact contains non-regular entry: ${relativePath}`,
      );
    }
    if (relativePath === VERSION_PATH) continue;
    const bytes = readFileSync(path);
    files.push({
      path: relativePath,
      size: bytes.byteLength,
      sha256: createHash("sha256").update(bytes).digest("hex"),
    });
  }
  return files;
}

export function computeBuildArtifactTree(buildDir) {
  const root = realpathSync(resolve(buildDir));
  const compileRevision = readCompileRevision(root);
  const files = collectFiles(root).sort((left, right) =>
    left.path < right.path ? -1 : left.path > right.path ? 1 : 0,
  );
  const digest = createHash("sha256");
  for (const file of files) {
    digest.update(file.path, "utf8");
    digest.update("\0", "utf8");
    digest.update(String(file.size), "utf8");
    digest.update("\0", "utf8");
    digest.update(file.sha256, "ascii");
    digest.update("\n", "utf8");
  }
  return {
    schemaVersion: 1,
    sha256: digest.digest("hex"),
    fileCount: files.length,
    compileRevision,
  };
}

export function readBuildArtifactEvidence(buildDir) {
  let root;
  try {
    root = realpathSync(resolve(buildDir));
  } catch {
    return { revision: null, verified: false, status: "artifact_unverifiable" };
  }
  const versionPath = resolve(root, VERSION_PATH);
  let metadata;
  try {
    metadata = lstatSync(versionPath);
  } catch {
    return { revision: null, verified: false, status: "artifact_unverifiable" };
  }
  if (!metadata.isFile() || metadata.isSymbolicLink()) {
    return { revision: null, verified: false, status: "artifact_invalid" };
  }
  const resolvedVersion = realpathSync(versionPath);
  if (!isInside(root, resolvedVersion)) {
    return { revision: null, verified: false, status: "artifact_invalid" };
  }

  let payload;
  try {
    payload = JSON.parse(readFileSync(versionPath, "utf8"));
  } catch {
    return { revision: null, verified: false, status: "artifact_invalid" };
  }
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return { revision: null, verified: false, status: "artifact_invalid" };
  }
  const revision =
    typeof payload.commit === "string"
      ? payload.commit.trim().toLowerCase()
      : null;
  if (!revision || !REVISION_PATTERN.test(revision)) {
    return { revision: null, verified: false, status: "artifact_invalid" };
  }
  const declared = payload.artifact_tree;
  if (
    !declared ||
    typeof declared !== "object" ||
    Array.isArray(declared) ||
    declared.schema_version !== 1 ||
    typeof declared.sha256 !== "string" ||
    !SHA256_PATTERN.test(declared.sha256) ||
    !Number.isSafeInteger(declared.file_count) ||
    declared.file_count < 1 ||
    typeof declared.compile_revision !== "string" ||
    !REVISION_PATTERN.test(declared.compile_revision) ||
    declared.compile_revision !== revision ||
    declared.provenance !== "unattested"
  ) {
    return { revision, verified: false, status: "artifact_unverifiable" };
  }

  let observed;
  try {
    observed = computeBuildArtifactTree(root);
  } catch {
    return { revision, verified: false, status: "artifact_invalid" };
  }
  const treeMatches =
    observed.sha256 === declared.sha256 &&
    observed.fileCount === declared.file_count;
  const compileRevisionMatches =
    observed.compileRevision === declared.compile_revision &&
    observed.compileRevision === revision;
  const verified = treeMatches && compileRevisionMatches;
  return {
    revision,
    verified,
    status: verified
      ? "verified"
      : compileRevisionMatches
        ? "artifact_tree_mismatch"
        : "artifact_compile_revision_mismatch",
    treeSha256: declared.sha256,
    observedTreeSha256: observed.sha256,
    fileCount: declared.file_count,
    observedFileCount: observed.fileCount,
    compileRevision: declared.compile_revision,
    observedCompileRevision: observed.compileRevision,
    provenanceVerified: false,
    provenanceStatus: "unattested",
  };
}
