#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${1:-python3}"

output="$(
  "$PYTHON_BIN" -m scripts.agent.validate_handoff \
    --task-file tests/fixtures/agent/handoff-task.json \
    --handoff-file tests/fixtures/agent/handoff-valid.json
)"

printf '%s\n' "$output" | "$PYTHON_BIN" -m json.tool >/dev/null
printf '%s\n' "$output" | grep -F '"status": "valid"' >/dev/null
printf '%s\n' "$output" | grep -F '"findings_count": 0' >/dev/null
printf '%s\n' 'handoff-readiness-smoke:valid'
