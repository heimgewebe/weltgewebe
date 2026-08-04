#!/usr/bin/env bash
set -euo pipefail

# Build, deep-validate and publish one immutable Germany version from isolated
# staging. Preparation deliberately does not touch stable aliases: the selected
# version is exposed only inside the separately reviewed activation transaction.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" > /dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." > /dev/null 2>&1 && pwd)"
BASEMAP_VERSION="${BASEMAP_VERSION:-0.1.0}"
BUILD_DIR="${GERMANY_BASEMAP_BUILD_DIR:-$REPO_ROOT/build/basemap-staging/germany}"
TARGET_DIR_EXPLICIT=0
if (($# > 1)); then
  echo "ERROR: usage: $0 [existing-target-directory]" >&2
  exit 1
elif (($# == 1)); then
  [[ -n "$1" ]] || {
    echo "ERROR: explicit target directory must not be empty" >&2
    exit 1
  }
  TARGET_DIR="$1"
  TARGET_DIR_EXPLICIT=1
elif [[ ${GERMANY_BASEMAP_TARGET_DIR+x} == x ]]; then
  [[ -n "$GERMANY_BASEMAP_TARGET_DIR" ]] || {
    echo "ERROR: GERMANY_BASEMAP_TARGET_DIR must not be empty when set" >&2
    exit 1
  }
  TARGET_DIR="$GERMANY_BASEMAP_TARGET_DIR"
  TARGET_DIR_EXPLICIT=1
else
  TARGET_DIR="$REPO_ROOT/build/basemap"
fi
ARTIFACT_NAME="basemap-germany-v${BASEMAP_VERSION}.pmtiles"
META_NAME="basemap-germany-v${BASEMAP_VERSION}.meta.json"
BUILD_RECEIPT_NAME="basemap-germany-v${BASEMAP_VERSION}.build.json"
PROOF_NAME="basemap-germany-v${BASEMAP_VERSION}.validation.json"
RAW_PROOF_NAME="basemap-germany-v${BASEMAP_VERSION}.validation.raw.json"
ALIAS_ARTIFACT_NAME="basemap-germany.pmtiles"
ALIAS_META_NAME="basemap-germany.meta.json"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

path_state() {
  local path="$1"
  if [[ -L "$path" ]]; then
    printf 'symlink:%s\n' "$(readlink -- "$path")"
  elif [[ -e "$path" ]]; then
    printf 'file:%s:%s\n' \
      "$(wc -c < "$path" | tr -d '[:space:]')" \
      "$(sha256sum "$path" | awk '{print $1}')"
  else
    printf 'absent\n'
  fi
}

on_interrupt() {
  exit 130
}

on_terminate() {
  exit 143
}

[[ "$BASEMAP_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] ||
  fail "BASEMAP_VERSION must use numeric semantic versioning"
command -v pnpm > /dev/null 2>&1 || fail "pnpm is required"
command -v python3 > /dev/null 2>&1 || fail "python3 is required"
command -v readlink > /dev/null 2>&1 || fail "readlink is required"
command -v sha256sum > /dev/null 2>&1 || fail "sha256sum is required"

mkdir -p "$BUILD_DIR"
if [[ "$TARGET_DIR_EXPLICIT" == "0" ]]; then
  mkdir -p "$TARGET_DIR"
else
  [[ -d "$TARGET_DIR" ]] || fail "explicit target directory does not exist: $TARGET_DIR"
fi
BUILD_DIR="$(cd "$BUILD_DIR" > /dev/null 2>&1 && pwd)"
TARGET_DIR="$(cd "$TARGET_DIR" > /dev/null 2>&1 && pwd)"
[[ "$BUILD_DIR" != "$TARGET_DIR" ]] ||
  fail "Germany build and published target directories must differ"

ARTIFACT="$BUILD_DIR/$ARTIFACT_NAME"
META="$BUILD_DIR/$META_NAME"
BUILD_RECEIPT="$BUILD_DIR/$BUILD_RECEIPT_NAME"
RAW_PROOF="$BUILD_DIR/$RAW_PROOF_NAME"
PROOF_OUTPUT="${GERMANY_BASEMAP_PROOF_OUTPUT:-$BUILD_DIR/$PROOF_NAME}"
TARGET_ARTIFACT="$TARGET_DIR/$ARTIFACT_NAME"
TARGET_META="$TARGET_DIR/$META_NAME"
TARGET_BUILD_RECEIPT="$TARGET_DIR/$BUILD_RECEIPT_NAME"
TARGET_PROOF="$TARGET_DIR/$PROOF_NAME"
ALIAS_ARTIFACT="$TARGET_DIR/$ALIAS_ARTIFACT_NAME"
ALIAS_META="$TARGET_DIR/$ALIAS_META_NAME"

for published_path in "$TARGET_ARTIFACT" "$TARGET_PROOF" "$TARGET_BUILD_RECEIPT" "$TARGET_META"; do
  if [[ -e "$published_path" || -L "$published_path" ]]; then
    fail "published Germany version already exists: $published_path; choose a new BASEMAP_VERSION"
  fi
done

ALIAS_ARTIFACT_STATE_BEFORE="$(path_state "$ALIAS_ARTIFACT")"
ALIAS_META_STATE_BEFORE="$(path_state "$ALIAS_META")"

if [[ "${GERMANY_BASEMAP_SKIP_BUILD:-0}" != "1" ]]; then
  BASEMAP_DIR="$BUILD_DIR" bash "$SCRIPT_DIR/build-germany-pmtiles.sh"
fi

[[ -s "$ARTIFACT" ]] || fail "Germany artifact missing: $ARTIFACT"
[[ -s "$META" ]] || fail "Germany metadata missing: $META"
[[ -s "$BUILD_RECEIPT" ]] || fail "Germany measured build receipt missing: $BUILD_RECEIPT"

ARTIFACT_SHA256="$(sha256sum "$ARTIFACT" | awk '{print $1}')"
ARTIFACT_SIZE="$(wc -c < "$ARTIFACT" | tr -d '[:space:]')"

META_PATH="$META" \
  ARTIFACT_NAME="$ARTIFACT_NAME" \
  EXPECTED_VERSION="$BASEMAP_VERSION" \
  EXPECTED_SHA256="$ARTIFACT_SHA256" \
  EXPECTED_SIZE="$ARTIFACT_SIZE" \
  python3 << 'PY'
import json
import os
from pathlib import Path

meta = json.loads(Path(os.environ["META_PATH"]).read_text(encoding="utf-8"))
if meta.get("schema_version") != 1:
    raise SystemExit("Germany sentinel schema mismatch")
if meta.get("status") != "ready" or meta.get("region") != "germany":
    raise SystemExit("Germany sentinel is not ready for Germany")
if meta.get("activation") != "opt-in":
    raise SystemExit("Germany sentinel must remain opt-in during preparation")
if meta.get("version") != os.environ["EXPECTED_VERSION"]:
    raise SystemExit("Germany sentinel version mismatch")
if meta.get("artifact_name") != os.environ["ARTIFACT_NAME"]:
    raise SystemExit("Germany sentinel artifact_name mismatch")
if meta.get("size_bytes") != int(os.environ["EXPECTED_SIZE"]):
    raise SystemExit("Germany sentinel size mismatch")
if meta.get("sha256") != os.environ["EXPECTED_SHA256"]:
    raise SystemExit("Germany sentinel SHA256 mismatch")
PY

BUILD_RECEIPT_PATH="$BUILD_RECEIPT" \
  EXPECTED_VERSION="$BASEMAP_VERSION" \
  EXPECTED_ARTIFACT_NAME="$ARTIFACT_NAME" \
  EXPECTED_SHA256="$ARTIFACT_SHA256" \
  EXPECTED_SIZE="$ARTIFACT_SIZE" \
  python3 << 'PY'
import json, os
from pathlib import Path
r=json.loads(Path(os.environ["BUILD_RECEIPT_PATH"]).read_text())
if r.get("schema_version")!=1 or r.get("verdict")!="PROVEN": raise SystemExit("Germany measured build receipt is not PROVEN")
if r.get("contract")!="germany-pmtiles-measured-build-v1": raise SystemExit("Germany measured build receipt contract mismatch")
if r.get("version")!=os.environ["EXPECTED_VERSION"]: raise SystemExit("Germany measured build receipt version mismatch")
if r.get("artifact")!={"name":os.environ["EXPECTED_ARTIFACT_NAME"],"sha256":os.environ["EXPECTED_SHA256"],"size_bytes":int(os.environ["EXPECTED_SIZE"])}: raise SystemExit("Germany measured build receipt artifact mismatch")
x=r.get("execution");p=r.get("peaks")
if not isinstance(x,dict) or not isinstance(p,dict): raise SystemExit("Germany measured build receipt lacks execution or peaks")
for f in ("duration_seconds","sample_count"):
 v=x.get(f)
 if not isinstance(v,(int,float)) or v<=0: raise SystemExit(f"Germany measured build execution {f} must be positive")
for f in ("cpu_percent","memory_bytes","workspace_growth_bytes","filesystem_consumed_bytes"):
 v=p.get(f)
 if not isinstance(v,(int,float)) or v<=0: raise SystemExit(f"Germany measured build peak {f} must be positive")
PY

if [[ ! -d "$REPO_ROOT/apps/web/node_modules" ]]; then
  pnpm -C "$REPO_ROOT/apps/web" install --frozen-lockfile
fi

rm -f "$RAW_PROOF" "$PROOF_OUTPUT"
pnpm -C "$REPO_ROOT/apps/web" validate:pmtiles -- \
  --archive "germany=$ARTIFACT" \
  --style "$REPO_ROOT/map-style/style-germany.json" \
  --output "$RAW_PROOF"
[[ -s "$RAW_PROOF" ]] || fail "raw deep-validation report was not written"

RAW_PROOF_PATH="$RAW_PROOF" \
  PROOF_OUTPUT_PATH="$PROOF_OUTPUT" \
  ARTIFACT_NAME="$ARTIFACT_NAME" \
  ARTIFACT_SHA256="$ARTIFACT_SHA256" \
  ARTIFACT_SIZE="$ARTIFACT_SIZE" \
  python3 << 'PY'
import json
import os
from pathlib import Path

raw = json.loads(Path(os.environ["RAW_PROOF_PATH"]).read_text(encoding="utf-8"))
if raw.get("schema_version") != 1 or raw.get("verdict") != "PROVEN":
    raise SystemExit("raw Germany deep-validation verdict is not PROVEN")
if raw.get("validator") != "bounded-pmtiles-deep-validation-v1":
    raise SystemExit("raw Germany deep-validation validator mismatch")
archives = raw.get("archives")
if not isinstance(archives, list) or len(archives) != 1:
    raise SystemExit("raw Germany deep-validation must contain one archive")
archive = archives[0]
if archive.get("region") != "germany":
    raise SystemExit("raw Germany deep-validation region mismatch")
if archive.get("file_size") != int(os.environ["ARTIFACT_SIZE"]):
    raise SystemExit("raw Germany deep-validation size mismatch")
if archive.get("directory", {}).get("tile_entry_count", 0) <= 0:
    raise SystemExit("raw Germany deep-validation contains no tiles")
if not archive.get("samples"):
    raise SystemExit("raw Germany deep-validation contains no samples")

envelope = {
    "schema_version": 1,
    "verdict": "PROVEN",
    "contract": "germany-pmtiles-prepared-validation-v1",
    "artifact": {
        "name": os.environ["ARTIFACT_NAME"],
        "sha256": os.environ["ARTIFACT_SHA256"],
        "size_bytes": int(os.environ["ARTIFACT_SIZE"]),
    },
    "validation": raw,
}
Path(os.environ["PROOF_OUTPUT_PATH"]).write_text(
    json.dumps(envelope, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY
[[ -s "$PROOF_OUTPUT" ]] || fail "artifact-bound validation envelope was not written"

ARTIFACT_TMP="$TARGET_DIR/.${ARTIFACT_NAME}.tmp.$$"
PROOF_TMP="$TARGET_DIR/.${PROOF_NAME}.tmp.$$"
BUILD_RECEIPT_TMP="$TARGET_DIR/.${BUILD_RECEIPT_NAME}.tmp.$$"
META_TMP="$TARGET_DIR/.${META_NAME}.tmp.$$"
ARTIFACT_CREATED=0
PROOF_CREATED=0
BUILD_RECEIPT_CREATED=0
META_CREATED=0
PUBLISH_COMPLETE=0

cleanup_publish() {
  rm -f "$ARTIFACT_TMP" "$PROOF_TMP" "$BUILD_RECEIPT_TMP" "$META_TMP"
  if [[ "$PUBLISH_COMPLETE" != "1" ]]; then
    [[ "$META_CREATED" == "1" ]] && rm -f "$TARGET_META"
    [[ "$BUILD_RECEIPT_CREATED" == "1" ]] && rm -f "$TARGET_BUILD_RECEIPT"
    [[ "$PROOF_CREATED" == "1" ]] && rm -f "$TARGET_PROOF"
    [[ "$ARTIFACT_CREATED" == "1" ]] && rm -f "$TARGET_ARTIFACT"
  fi
}

publish_immutable_set() {
  local failed=0

  # Protect the non-atomic three-link publication window. Ownership flags and
  # all three links become visible as one cleanup transaction before signals
  # are handled again.
  trap '' INT TERM

  if ! ln "$ARTIFACT_TMP" "$TARGET_ARTIFACT"; then
    echo "ERROR: could not publish immutable Germany artifact: $TARGET_ARTIFACT" >&2
    failed=1
  else
    ARTIFACT_CREATED=1
  fi

  if [[ "$failed" == "0" ]]; then
    if ! ln "$PROOF_TMP" "$TARGET_PROOF"; then
      echo "ERROR: could not publish immutable Germany validation report: $TARGET_PROOF" >&2
      failed=1
    else
      PROOF_CREATED=1
    fi
  fi

  if [[ "$failed" == "0" ]]; then
    if ! ln "$BUILD_RECEIPT_TMP" "$TARGET_BUILD_RECEIPT"; then
      echo "ERROR: could not publish immutable Germany build receipt: $TARGET_BUILD_RECEIPT" >&2
      failed=1
    else
      BUILD_RECEIPT_CREATED=1
    fi
  fi

  if [[ "$failed" == "0" ]]; then
    if ! ln "$META_TMP" "$TARGET_META"; then
      echo "ERROR: could not publish immutable Germany sentinel: $TARGET_META" >&2
      failed=1
    else
      META_CREATED=1
    fi
  fi

  trap on_interrupt INT
  trap on_terminate TERM
  return "$failed"
}

trap cleanup_publish EXIT
trap on_interrupt INT
trap on_terminate TERM

install -m 0644 "$ARTIFACT" "$ARTIFACT_TMP"
install -m 0644 "$PROOF_OUTPUT" "$PROOF_TMP"
install -m 0644 "$BUILD_RECEIPT" "$BUILD_RECEIPT_TMP"
install -m 0644 "$META" "$META_TMP"

publish_immutable_set || fail "could not publish the immutable Germany version set"

for published_path in "$TARGET_ARTIFACT" "$TARGET_PROOF" "$TARGET_BUILD_RECEIPT" "$TARGET_META"; do
  [[ -s "$published_path" ]] || fail "published Germany version file missing: $published_path"
done
cmp -s "$ARTIFACT" "$TARGET_ARTIFACT" || fail "published Germany artifact differs from staging"
cmp -s "$PROOF_OUTPUT" "$TARGET_PROOF" || fail "published Germany validation differs from staging"
cmp -s "$BUILD_RECEIPT" "$TARGET_BUILD_RECEIPT" || fail "published Germany build receipt differs from staging"
cmp -s "$META" "$TARGET_META" || fail "published Germany sentinel differs from staging"

ALIAS_ARTIFACT_STATE_AFTER="$(path_state "$ALIAS_ARTIFACT")"
ALIAS_META_STATE_AFTER="$(path_state "$ALIAS_META")"
[[ "$ALIAS_ARTIFACT_STATE_AFTER" == "$ALIAS_ARTIFACT_STATE_BEFORE" ]] ||
  fail "preparation changed the stable Germany artifact alias"
[[ "$ALIAS_META_STATE_AFTER" == "$ALIAS_META_STATE_BEFORE" ]] ||
  fail "preparation changed the stable Germany metadata alias"

PUBLISH_COMPLETE=1
cleanup_publish
trap - EXIT INT TERM

echo "Germany PMTiles version preparation is complete."
echo "Isolated build: $BUILD_DIR"
echo "Published immutable version files:"
echo "  $TARGET_ARTIFACT"
echo "  $TARGET_META"
echo "  $TARGET_BUILD_RECEIPT"
echo "  $TARGET_PROOF"
echo "Stable aliases were NOT changed:"
echo "  $ALIAS_ARTIFACT"
echo "  $ALIAS_META"
echo "Activation remains a separate reviewed transaction."
