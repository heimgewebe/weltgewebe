#!/bin/bash
# ------------------------------------------------------------------
# Local Mock Test for Deployment Logic
# Not intended for CI execution without mock setup.
# ------------------------------------------------------------------
set -euo pipefail

# Ensure we are in the repo root
cd "$(dirname "$0")/../.."

# Cleanup Trap
cleanup() {
  rm -rf mock_bin test.env
}
trap cleanup EXIT

# 0. Setup Mocks
mkdir -p mock_bin

# Mock Docker
cat << 'EOF' > mock_bin/docker
#!/bin/bash
ARGS="$*"
if [[ "$1" == "ps" ]]; then
  if [[ "${MOCK_ZOMBIE:-}" == "1" ]]; then
    # Return zombie with config path matching current repo
    echo "zombie-container compose $(pwd)/infra/compose/compose.prod.yml"
  elif [[ "${MOCK_ZOMBIE:-}" == "GENERIC" ]]; then
      echo "zombie-generic compose"
  else
    echo ""
  fi
elif [[ "$1" == "rm" ]]; then
    if [[ "$ARGS" == *"-f"* ]]; then
        echo "Mocked remove: $ARGS"
        exit 0
    fi
elif [[ "$1" == "inspect" ]]; then
    # Return dummy alias if requesting format with Aliases
    if [[ "$ARGS" == *"--format"* && "$ARGS" == *"Aliases"* ]]; then
        echo "weltgewebe-api"
    fi
    exit 0
elif [[ "$1" == "compose" ]]; then
  if [[ "$ARGS" == *" config"* ]]; then
     echo "services: {}"
     exit 0
  fi
  # New: Echo COMPOSE_BAKE state if VERIFY_BAKE is set
  if [[ "${VERIFY_BAKE:-}" == "1" ]]; then
     # We output this to stderr or stdout, so we can grep it in tests
     echo "VERIFY_BAKE: COMPOSE_BAKE=${COMPOSE_BAKE:-<unset>}"
  fi

  echo "Mocked docker compose execution"
  exit 0
else
  echo ""
  exit 0
fi
EOF

# Mock pnpm
cat << 'EOF' > mock_bin/pnpm
#!/bin/bash
echo "Mocked pnpm execution: $*"
if [[ "$*" == *"-C apps/web build"* ]]; then
    mkdir -p apps/web/build
    touch apps/web/build/index.html
fi
exit 0
EOF

# Mock curl
cat << 'EOF' > mock_bin/curl
#!/bin/bash
echo '{"status": "ok"}'
exit 0
EOF

chmod +x mock_bin/*
export PATH="$(pwd)/mock_bin:$PATH"

REPO_DIR=$(pwd)
export REPO_DIR
export ENV_FILE="$REPO_DIR/test.env"
# Create dummy env file
echo "WEB_UPSTREAM_URL=https://example.com" > "$ENV_FILE"
echo "WEB_UPSTREAM_HOST=example.com" >> "$ENV_FILE"

# 1. Test Project Validation
echo ">>> Test 1: Project Validation (fail case)"
export COMPOSE_PROJECT="compose"
if ./scripts/weltgewebe-up --no-pull --no-build >/dev/null 2>&1; then
  echo "FAIL: COMPOSE_PROJECT=compose check failed."
  exit 1
else
  echo "PASS: COMPOSE_PROJECT=compose rejected."
fi

# Reset Project
export COMPOSE_PROJECT="weltgewebe"

# 2. Test Zombie Guard (Fail with Detailed Message)
echo ">>> Test 2: Zombie Guard (Fail Logic)"
export MOCK_ZOMBIE=1
OUTPUT=$(./scripts/weltgewebe-up --no-pull --no-build 2>&1 || true)

# Robust assertions: Check for key markers instead of exact full string
if echo "$OUTPUT" | grep -q "ERROR: Detected foreign compose project"; then
   if echo "$OUTPUT" | grep -q "Repo dir:" && \
      echo "$OUTPUT" | grep -q "Expected project name:" && \
      echo "$OUTPUT" | grep -q "docker compose -p <foreign_project> down"; then
         echo "PASS: Detailed error message found (robust check)."
   else
      echo "FAIL: Missing remediation hints or context info."
      echo "$OUTPUT"
      exit 1
   fi
else
   echo "FAIL: Zombie detection failed or error message mismatch."
   echo "$OUTPUT"
   exit 1
fi

# 3. Test Zombie Guard (Purge)
echo ">>> Test 3: Zombie Guard (Purge)"
export MOCK_ZOMBIE=1
OUTPUT=$(./scripts/weltgewebe-up --no-pull --no-build --purge-compose-leaks 2>&1)
if echo "$OUTPUT" | grep -q "Purging as requested"; then
  echo "PASS: Purge triggered."
else
  echo "FAIL: Purge NOT triggered."
  echo "$OUTPUT"
  exit 1
fi

# 4. Test Bake Auto-Disable (Missing /apps)
echo ">>> Test 4: Bake Auto-Disable (Missing /apps)"
export MOCK_ZOMBIE=0
export VERIFY_BAKE=1
# Use probe override to simulate missing directory
export WELTGEWEBE_APPS_PROBE="./missing_apps_mock"
unset COMPOSE_BAKE
unset COMPOSE_BAKE_VALUE

OUTPUT=$(./scripts/weltgewebe-up --no-pull --no-build 2>&1)
if echo "$OUTPUT" | grep -q "VERIFY_BAKE: COMPOSE_BAKE=0"; then
  echo "PASS: COMPOSE_BAKE=0 set when apps probe fails."
else
  echo "FAIL: COMPOSE_BAKE=0 not detected."
  echo "$OUTPUT"
  exit 1
fi

# 5. Test Bake Preserved (Existing /apps)
echo ">>> Test 5: Bake Preserved (Existing /apps)"
# Point probe to existing repo dir (we know infra exists)
export WELTGEWEBE_APPS_PROBE="infra"
unset COMPOSE_BAKE
unset COMPOSE_BAKE_VALUE

OUTPUT=$(./scripts/weltgewebe-up --no-pull --no-build 2>&1)
if echo "$OUTPUT" | grep -q "VERIFY_BAKE: COMPOSE_BAKE=<unset>"; then
  echo "PASS: COMPOSE_BAKE preserved (unset) when apps probe succeeds."
else
  echo "FAIL: COMPOSE_BAKE forced unexpectedly."
  echo "$OUTPUT"
  exit 1
fi

# 6. Test Bake Override
echo ">>> Test 6: Bake Override (Explicit 0)"
export WELTGEWEBE_COMPOSE_BAKE=0
# Probe should not matter here, but let's point to existing
export WELTGEWEBE_APPS_PROBE="infra"
unset COMPOSE_BAKE
unset COMPOSE_BAKE_VALUE

OUTPUT=$(./scripts/weltgewebe-up --no-pull --no-build 2>&1)
if echo "$OUTPUT" | grep -q "VERIFY_BAKE: COMPOSE_BAKE=0"; then
  echo "PASS: Explicit WELTGEWEBE_COMPOSE_BAKE=0 honored."
else
  echo "FAIL: Override ignored."
  echo "$OUTPUT"
  exit 1
fi
unset WELTGEWEBE_COMPOSE_BAKE

echo ">>> All refined tests passed."
