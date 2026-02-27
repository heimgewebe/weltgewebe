#!/bin/bash
set -euo pipefail

# ------------------------------------------------------------------
# Regression Test for Issue: "Detected API port: 0"
# Verifies that port 0 is NOT used and fallback to Docker Health occurs.
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

if [[ "$1" == "ps" ]]; then
    # Return dummy API container ID
    echo "api_cid_12345"
    exit 0
elif [[ "$1" == "inspect" ]]; then
    # Mock Docker Health Status
    if [[ "$ARGS" == *".State.Health.Status"* ]]; then
        echo "healthy"
    elif [[ "$ARGS" == *".State.Health.Log"* ]]; then
        echo "[]"
    # Mock Network Aliases check (needed to pass the final check)
    elif [[ "$ARGS" == *".NetworkSettings.Networks"* ]]; then
        echo "weltgewebe-api"
    fi
    exit 0
fi

if [[ "$1" == "compose" ]]; then
  if [[ "$ARGS" == *" config"* ]]; then
     echo "services: {}"
     exit 0
  fi

  if [[ "$ARGS" == *" port api"* ]]; then
     # SIMULATE THE SCENARIO: Port 0 returned (unpublished)
     echo "0.0.0.0:0"
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

# Mock curl (fail on port 0)
cat << 'EOF' > mock_bin_repro/curl
#!/bin/bash
# If the URL contains port 0, fail hard to catch regression
if [[ "$*" == *":0/health/ready"* ]]; then
    echo "curl: (7) Failed to connect to 127.0.0.1 port 0: Connection refused" >&2
    exit 7
fi
echo '{"status": "ok"}'
exit 0
EOF

# Mock git (needed for state file logic)
cat << 'EOF' > mock_bin_repro/git
#!/bin/bash
if [[ "$1" == "rev-parse" && "$2" == "HEAD" ]]; then
    echo "mock-commit-hash"
    exit 0
fi
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
echo ">>> Running regression test..."

# We expect SUCCESS now (fix applied)
# Disable git pull via flag, but allow our mock git to run for HEAD detection if needed (though --no-pull skips it usually, let's see)
if ./scripts/weltgewebe-up --no-pull --no-build > output.log 2>&1; then
    echo "PASS: Script succeeded (Exit 0)."
else
    echo "FAIL: Script failed unexpectedly."
    cat output.log
    exit 1
fi

echo ">>> Analyze Output:"
cat output.log

# Assertions
if grep -q "Detected API port: 0" output.log; then
    echo "FAIL: Regression detected - Found 'Detected API port: 0'."
    exit 1
fi

if grep -q "Health strategy selected: Docker Native Health" output.log; then
    echo "PASS: Correct strategy selected (Docker Native Health)."
else
    echo "FAIL: Wrong strategy selected."
    exit 1
fi

if grep -q "curl: (7)" output.log; then
    echo "FAIL: Regression detected - Tried to curl port 0."
    exit 1
fi

echo "REGRESSION TEST PASSED."
