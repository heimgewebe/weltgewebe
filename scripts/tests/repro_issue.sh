#!/bin/bash
set -euo pipefail

# ------------------------------------------------------------------
# Reproduction Test for Issue: "Detected API port: 0"
# ------------------------------------------------------------------

# Ensure we are in the repo root
cd "$(dirname "$0")/../.."

# Cleanup Trap
cleanup() {
  rm -rf mock_bin_repro test_repro.env
}
trap cleanup EXIT

# 0. Setup Mocks
mkdir -p mock_bin_repro

# Mock Docker
cat << 'EOF' > mock_bin_repro/docker
#!/bin/bash
ARGS="$*"

if [[ "$1" == "compose" ]]; then
  if [[ "$ARGS" == *" config"* ]]; then
     echo "services: {}"
     exit 0
  fi

  if [[ "$ARGS" == *" port api 8080"* ]]; then
     # SIMULATE THE BUG: Return 0.0.0.0:0 or empty depending on how docker behaves
     # The issue description says "Detected API port: 0", which implies the output
     # of `docker compose port` was parsed to 0.
     # Typically `docker compose port` returns nothing if not mapped, or 0.0.0.0:0 if explicitly mapped to random/0.
     # Let's simulate returning 0.0.0.0:0 to match the "Port 0" symptom.
     echo "0.0.0.0:0"
     exit 0
  fi

  if [[ "$ARGS" == *" ps"* ]]; then
      echo "api"
      exit 0
  fi

  # Mock up -d
  if [[ "$ARGS" == *" up -d"* ]]; then
      exit 0
  fi

  echo "Mocked docker compose execution: $ARGS"
  exit 0
fi

# Fallback
echo ""
exit 0
EOF

# Mock curl (always fails on port 0)
cat << 'EOF' > mock_bin_repro/curl
#!/bin/bash
# If the URL contains port 0, fail
if [[ "$*" == *":0/health/ready"* ]]; then
    echo "curl: (7) Failed to connect to 127.0.0.1 port 0: Connection refused" >&2
    exit 7
fi
echo '{"status": "ok"}'
exit 0
EOF

chmod +x mock_bin_repro/*
export PATH="$(pwd)/mock_bin_repro:$PATH"

REPO_DIR=$(pwd)
export REPO_DIR
export ENV_FILE="$REPO_DIR/test_repro.env"
# Create dummy env file
echo "WEB_UPSTREAM_URL=https://example.com" > "$ENV_FILE"
echo "WEB_UPSTREAM_HOST=example.com" >> "$ENV_FILE"

# Run weltgewebe-up
echo ">>> Running reproduction test..."
# We expect failure because curl to port 0 will fail
if ./scripts/weltgewebe-up --no-pull --no-build > output.log 2>&1; then
    echo "FAIL: Script succeeded unexpectedly."
    cat output.log
    exit 1
else
    echo "Script failed as expected (exit code $?)."
fi

echo ">>> Analyze Output:"
cat output.log

if grep -q "Detected API port: 0" output.log; then
    echo "REPRODUCTION SUCCESS: Found 'Detected API port: 0' in output."
else
    echo "REPRODUCTION FAILED: Did not find 'Detected API port: 0'."
    exit 1
fi
