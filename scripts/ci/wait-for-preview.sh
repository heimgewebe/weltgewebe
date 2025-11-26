#!/usr/bin/env bash
set -euo pipefail

PREVIEW_PORT=${PREVIEW_PORT:-4173}
PREVIEW_PID_FILE=${PREVIEW_PID_FILE:-/tmp/preview.pid}
PREVIEW_LOG=${PREVIEW_LOG:-/tmp/preview.log}
PREVIEW_WAIT_DURATION=${PREVIEW_WAIT_DURATION:-120}
PREVIEW_WAIT_INTERVAL=${PREVIEW_WAIT_INTERVAL:-2}

if [ ! -f "$PREVIEW_PID_FILE" ]; then
  printf 'Preview PID file not found at %s\n' "$PREVIEW_PID_FILE" >&2
  exit 1
fi

PREVIEW_PID=$(cat "$PREVIEW_PID_FILE")

check_preview_ready() {
  curl -sSf "http://127.0.0.1:${PREVIEW_PORT}" >/dev/null 2>&1
}

show_preview_logs() {
  printf '==== Preview logs (%s) ====%s' "$PREVIEW_LOG" "\n" >&2
  if [ -f "$PREVIEW_LOG" ]; then
    tail -n 120 "$PREVIEW_LOG" >&2 || true
  else
    printf 'No preview log found at %s\n' "$PREVIEW_LOG" >&2
  fi
}

verify_port_binding() {
  if ss -ltn | grep -q ":${PREVIEW_PORT}.*LISTEN"; then
    printf 'Preview server is listening on port %s\n' "$PREVIEW_PORT"
    return 0
  fi

  printf 'Preview server is not listening on port %s\n' "$PREVIEW_PORT" >&2
  show_preview_logs
  return 1
}

declare -i end=$((SECONDS + PREVIEW_WAIT_DURATION))

while [ "$SECONDS" -lt "$end" ]; do
  if ! kill -0 "$PREVIEW_PID" 2>/dev/null; then
    printf 'Preview server process (PID %s) exited early\n' "$PREVIEW_PID" >&2
    show_preview_logs
    exit 1
  fi

  if check_preview_ready; then
    printf 'Preview server is available at http://127.0.0.1:%s\n' "$PREVIEW_PORT"
    break
  fi

  sleep "$PREVIEW_WAIT_INTERVAL"
done

if ! check_preview_ready; then
  printf 'Preview server did not start within %s seconds\n' "$PREVIEW_WAIT_DURATION" >&2
  verify_port_binding || true
  show_preview_logs
  exit 1
fi
