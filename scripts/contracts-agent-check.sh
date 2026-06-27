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
VALIDATION_SCHEMA="contracts/agent/validation.schema.json"
RUN_RESULT_SCHEMA="contracts/agent/run-result.schema.json"
TASK_FIXTURE="tests/fixtures/agent/handoff-task.json"
VALID_HANDOFF="tests/fixtures/agent/handoff-valid.json"
VALID_VALIDATION="tests/fixtures/agent/validation-valid.json"
VALID_RUN_RESULT="tests/fixtures/agent/run-result-valid.json"
TMP_DIR="$(mktemp -d)"
INVALID_HANDOFF="$TMP_DIR/handoff-invalid.json"
INVALID_VALIDATION="$TMP_DIR/validation-invalid.json"
INVALID_RUN_RESULT="$TMP_DIR/run-result-invalid.json"
AJV_OUTPUT="$TMP_DIR/agent-contract-invalid.out"
trap 'rm -rf -- "${TMP_DIR:?}"' EXIT

INVALID_HANDOFF="$INVALID_HANDOFF" \
INVALID_VALIDATION="$INVALID_VALIDATION" \
INVALID_RUN_RESULT="$INVALID_RUN_RESULT" \
python3 - <<'PY'
import json
import os
from pathlib import Path


def write_mutation(source: str, target_env: str, mutate) -> None:
    data = json.loads(Path(source).read_text())
    mutate(data)
    Path(os.environ[target_env]).write_text(json.dumps(data) + "\n")


write_mutation(
    "tests/fixtures/agent/handoff-valid.json",
    "INVALID_HANDOFF",
    lambda data: data.pop("producer"),
)
write_mutation(
    "tests/fixtures/agent/validation-valid.json",
    "INVALID_VALIDATION",
    lambda data: data.__setitem__("checks", list(reversed(data["checks"]))),
)
write_mutation(
    "tests/fixtures/agent/run-result-valid.json",
    "INVALID_RUN_RESULT",
    lambda data: data.__setitem__("stages", list(reversed(data["stages"]))),
)
PY

for schema in "$TASK_SCHEMA" "$HANDOFF_SCHEMA" "$VALIDATION_SCHEMA" "$RUN_RESULT_SCHEMA"; do
  echo "==> compile $schema"
  "$AJV_BIN" compile -s "$schema" --spec=draft7 --strict=false
done

echo "==> validate positive agent fixtures"
"$AJV_BIN" validate -s "$TASK_SCHEMA" -d "$TASK_FIXTURE" --spec=draft7 --strict=false
"$AJV_BIN" validate -s "$HANDOFF_SCHEMA" -d "$VALID_HANDOFF" --spec=draft7 --strict=false
"$AJV_BIN" validate -s "$VALIDATION_SCHEMA" -d "$VALID_VALIDATION" --spec=draft7 --strict=false
"$AJV_BIN" validate -s "$RUN_RESULT_SCHEMA" -d "$VALID_RUN_RESULT" --spec=draft7 --strict=false

expect_invalid() {
  local schema="$1"
  local fixture="$2"
  local label="$3"
  echo "==> require $label to fail schema validation"
  set +e
  "$AJV_BIN" validate -s "$schema" -d "$fixture" --spec=draft7 --strict=false >"$AJV_OUTPUT" 2>&1
  local rc=$?
  set -e
  if [[ "$rc" -ne 1 ]]; then
    cat "$AJV_OUTPUT" >&2 || true
    echo "error: expected AJV exit 1 for $fixture, got $rc" >&2
    exit 1
  fi
}

expect_invalid "$HANDOFF_SCHEMA" "$INVALID_HANDOFF" "negative handoff fixture"
expect_invalid "$VALIDATION_SCHEMA" "$INVALID_VALIDATION" "reversed validation checks"
expect_invalid "$RUN_RESULT_SCHEMA" "$INVALID_RUN_RESULT" "reversed run-result stages"

echo "Agent contract AJV checks passed."
