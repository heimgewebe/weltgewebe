#!/usr/bin/env bash
# Validate repository-owned agent contracts with the pinned AJV libraries.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v node > /dev/null 2>&1; then
  echo "error: node is required; install the repository Node toolchain first" >&2
  exit 2
fi
if [[ ! -d node_modules/ajv || ! -d node_modules/ajv-formats ]]; then
  echo "error: pinned AJV libraries are missing; run pnpm install first" >&2
  exit 2
fi

SCHEMA_CHECK=(node scripts/json-schema-check.mjs)
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
CHECK_OUTPUT="$TMP_DIR/agent-contract-invalid.out"
trap 'rm -rf -- "${TMP_DIR:?}"' EXIT

INVALID_HANDOFF="$INVALID_HANDOFF" \
  INVALID_VALIDATION="$INVALID_VALIDATION" \
  INVALID_RUN_RESULT="$INVALID_RUN_RESULT" \
  python3 - << 'PY'
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
  "${SCHEMA_CHECK[@]}" compile --schema "$schema" --spec draft7
done

echo "==> validate positive agent fixtures"
"${SCHEMA_CHECK[@]}" validate --schema "$TASK_SCHEMA" --data "$TASK_FIXTURE" --spec draft7
"${SCHEMA_CHECK[@]}" validate --schema "$HANDOFF_SCHEMA" --data "$VALID_HANDOFF" --spec draft7
"${SCHEMA_CHECK[@]}" validate --schema "$VALIDATION_SCHEMA" --data "$VALID_VALIDATION" --spec draft7
"${SCHEMA_CHECK[@]}" validate --schema "$RUN_RESULT_SCHEMA" --data "$VALID_RUN_RESULT" --spec draft7

expect_invalid() {
  local schema="$1"
  local fixture="$2"
  local label="$3"
  echo "==> require $label to fail schema validation"
  set +e
  "${SCHEMA_CHECK[@]}" validate --schema "$schema" --data "$fixture" --spec draft7 > "$CHECK_OUTPUT" 2>&1
  local rc=$?
  set -e
  if [[ "$rc" -ne 1 ]]; then
    cat "$CHECK_OUTPUT" >&2 || true
    echo "error: expected schema-check exit 1 for $fixture, got $rc" >&2
    exit 1
  fi
}

expect_invalid "$HANDOFF_SCHEMA" "$INVALID_HANDOFF" "negative handoff fixture"
expect_invalid "$VALIDATION_SCHEMA" "$INVALID_VALIDATION" "reversed validation checks"
expect_invalid "$RUN_RESULT_SCHEMA" "$INVALID_RUN_RESULT" "reversed run-result stages"

echo "Agent contract AJV checks passed."
