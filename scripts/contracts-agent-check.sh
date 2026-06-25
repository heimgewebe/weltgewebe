#!/usr/bin/env bash
# Validate repository-owned agent contracts with the pinned AJV toolchain.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

AJV_BIN="${AJV_BIN:-node_modules/.bin/ajv}"
if [[ ! -x "$AJV_BIN" ]]; then
  echo "error: pinned AJV executable not found at $AJV_BIN; run pnpm install first" >&2
  exit 2
fi

TASK_SCHEMA="contracts/agent/task.schema.json"
HANDOFF_SCHEMA="contracts/agent/handoff.schema.json"
TASK_FIXTURE="tests/fixtures/agent/handoff-task.json"
VALID_HANDOFF="tests/fixtures/agent/handoff-valid.json"
TMP_DIR="$(mktemp -d)"
INVALID_HANDOFF="$TMP_DIR/handoff-invalid.json"
AJV_OUTPUT="$TMP_DIR/agent-contract-invalid.out"
trap 'rm -rf -- "${TMP_DIR:?}"' EXIT
python3 - <<'PY' > "$INVALID_HANDOFF"
import json
from pathlib import Path
data = json.loads(Path("tests/fixtures/agent/handoff-valid.json").read_text())
data.pop("producer")
print(json.dumps(data))
PY

for schema in "$TASK_SCHEMA" "$HANDOFF_SCHEMA"; do
  echo "==> compile $schema"
  "$AJV_BIN" compile -s "$schema" --spec=draft7 --strict=false
done

echo "==> validate positive agent fixtures"
"$AJV_BIN" validate -s "$TASK_SCHEMA" -d "$TASK_FIXTURE" --spec=draft7 --strict=false
"$AJV_BIN" validate -s "$HANDOFF_SCHEMA" -d "$VALID_HANDOFF" --spec=draft7 --strict=false

echo "==> require negative handoff fixture to fail schema validation"
set +e
"$AJV_BIN" validate -s "$HANDOFF_SCHEMA" -d "$INVALID_HANDOFF" --spec=draft7 --strict=false >"$AJV_OUTPUT" 2>&1
rc=$?
set -e
if [[ "$rc" -ne 1 ]]; then
  cat "$AJV_OUTPUT" >&2 || true
  echo "error: expected AJV exit 1 for $INVALID_HANDOFF, got $rc" >&2
  exit 1
fi

echo "Agent contract AJV checks passed."
