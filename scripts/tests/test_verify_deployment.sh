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
  rm -rf mock_bin test.env custom_state
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
  elif [[ "$ARGS" == *"-q api"* ]]; then
      echo "api_container_id"
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
    elif [[ "$ARGS" == *"--format"* && "$ARGS" == *"Health.Status"* ]]; then
        echo "healthy"
    elif [[ "$ARGS" == *"--format"* && "$ARGS" == *"Health.Log"* ]]; then
        echo "[{\"Output\": \"Ok\"}]"
    fi
    exit 0
elif [[ "$1" == "compose" ]]; then
  if [[ "$ARGS" == *" config"* ]]; then
     # Check if we should simulate Caddy presence
     if [[ "${MOCK_HAS_CADDY:-0}" == "1" && "$ARGS" == *"--services"* ]]; then
        echo "caddy"
     fi
     if [[ "$ARGS" != *"--services"* ]]; then
         # config check succeeds
         echo "services: {}"
     fi
     exit 0
  fi

  # New: Echo COMPOSE_BAKE state if VERIFY_BAKE is set
  if [[ "${VERIFY_BAKE:-}" == "1" ]]; then
     # We output this to stderr or stdout, so we can grep it in tests
     echo "VERIFY_BAKE: COMPOSE_BAKE=${COMPOSE_BAKE:-<unset>}"
  fi

  # Port Mocking
  if [[ "$ARGS" == *" port api"* ]]; then
      # Extract requested internal port (last argument usually, or verify it)
      REQUESTED_PORT=$(echo "$ARGS" | awk '{print $NF}')

      # If we are testing custom internal port, verify it was passed correctly
      if [[ -n "${EXPECT_INTERNAL_PORT:-}" && "$REQUESTED_PORT" != "$EXPECT_INTERNAL_PORT" ]]; then
          echo "FAIL: Expected internal port $EXPECT_INTERNAL_PORT, got $REQUESTED_PORT" >&2
          exit 1
      fi

      if [[ "${MOCK_PORT_MODE:-}" == "0" ]]; then
          echo "0.0.0.0:0"
      elif [[ "${MOCK_PORT_MODE:-}" == "VALID" ]]; then
          echo "0.0.0.0:32768"
      else
          echo ""
      fi
      exit 0
  fi

  # Exec Mocking (deprecated in new strategy, but kept for completeness if needed)
  if [[ "$ARGS" == *" exec -T api"* ]]; then
      if [[ "${MOCK_EXEC_FAIL:-0}" == "1" ]]; then
          exit 1
      else
          # Check if the exec command uses the expected internal port
          if [[ -n "${EXPECT_INTERNAL_PORT:-}" ]]; then
             if [[ "$ARGS" != *":${EXPECT_INTERNAL_PORT}/health"* ]]; then
                 echo "FAIL: Exec command did not use expected port $EXPECT_INTERNAL_PORT" >&2
                 exit 1
             fi
          fi
          exit 0
      fi
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
# Fail if trying to connect to port 0
if [[ "$*" == *":0/health/ready"* ]]; then
    exit 7
fi
echo '{"status": "ok"}'
exit 0
EOF

# Mock Git
cat << 'EOF' > mock_bin/git
#!/bin/bash
ARGS="$*"
if [[ "$1" == "rev-parse" ]]; then
    if [[ "$ARGS" == *"--show-toplevel"* ]]; then
        # Return the exported REPO_DIR
        echo "$REPO_DIR"
    elif [[ "$ARGS" == *"HEAD"* ]]; then
        echo "mock-sha-12345"
    fi
    exit 0
elif [[ "$1" == "fetch" ]]; then
    exit 0
elif [[ "$1" == "pull" ]]; then
    exit 0
elif [[ "$1" == "symbolic-ref" ]]; then
    echo "main"
    exit 0
else
    # Fallback to true
    exit 0
fi
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
# Clean environment
unset COMPOSE_BAKE
unset COMPOSE_BAKE_VALUE
export WELTGEWEBE_COMPOSE_BAKE="auto"
export MOCK_ZOMBIE=0
export VERIFY_BAKE=1
# Use probe override to simulate missing directory
export WELTGEWEBE_APPS_PROBE="./missing_apps_mock"

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
# Clean environment
unset COMPOSE_BAKE
unset COMPOSE_BAKE_VALUE
export WELTGEWEBE_COMPOSE_BAKE="auto"
export VERIFY_BAKE=1
# Point probe to existing repo dir (we know infra exists)
export WELTGEWEBE_APPS_PROBE="infra"

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
# Clean environment
unset COMPOSE_BAKE
unset COMPOSE_BAKE_VALUE
export VERIFY_BAKE=1
export WELTGEWEBE_COMPOSE_BAKE=0
# Probe should not matter here, but let's point to existing
export WELTGEWEBE_APPS_PROBE="infra"

OUTPUT=$(./scripts/weltgewebe-up --no-pull --no-build 2>&1)
if echo "$OUTPUT" | grep -q "VERIFY_BAKE: COMPOSE_BAKE=0"; then
  echo "PASS: Explicit WELTGEWEBE_COMPOSE_BAKE=0 honored."
else
  echo "FAIL: Override ignored."
  echo "$OUTPUT"
  exit 1
fi

# 7. Test Bake Override Invalid
echo ">>> Test 7: Bake Override Invalid (Warning)"
# Clean environment
unset COMPOSE_BAKE
unset COMPOSE_BAKE_VALUE
export VERIFY_BAKE=1
export WELTGEWEBE_COMPOSE_BAKE="invalid_value"
export WELTGEWEBE_APPS_PROBE="infra"

OUTPUT=$(./scripts/weltgewebe-up --no-pull --no-build 2>&1)
if echo "$OUTPUT" | grep -q "Unrecognized WELTGEWEBE_COMPOSE_BAKE"; then
  echo "PASS: Warning detected for invalid value."
else
  echo "FAIL: Warning missing."
  echo "$OUTPUT"
  exit 1
fi

# 8. Test REPO_DIR Auto-Detection (Unset)
echo ">>> Test 8: REPO_DIR Auto-Detection"
# Harden tests against host environment
unset REPO_DIR COMPOSE_BAKE WELTGEWEBE_COMPOSE_BAKE WELTGEWEBE_APPS_PROBE VERIFY_BAKE

# We rely on CWD/Git fallback since we are in repo root (managed by test setup cd)
# Ensure we are in a path that has the config file
if [[ ! -f "infra/compose/compose.prod.yml" ]]; then
    echo "FAIL: Test setup error - config file not found in CWD."
    exit 1
fi

# We expect success (exit 0) and validation that correct repo was picked
OUTPUT=$(./scripts/weltgewebe-up --no-pull --no-build 2>&1)
if echo "$OUTPUT" | grep -qF "Repo:    $(pwd)"; then
    echo "PASS: Auto-detection worked and selected current directory."
else
    echo "FAIL: Auto-detection failed or selected wrong repo."
    echo "$OUTPUT"
    exit 1
fi

# 9. Test REPO_DIR Strictness (Invalid Path)
echo ">>> Test 9: REPO_DIR Strictness (Invalid Path)"
export REPO_DIR="/invalid/path/to/repo"
OUTPUT=$(./scripts/weltgewebe-up --no-pull --no-build 2>&1 || true)

if echo "$OUTPUT" | grep -q "ERROR: REPO_DIR explicitly set"; then
   if echo "$OUTPUT" | grep -q "Refusing fallback"; then
      echo "PASS: Strict check rejected invalid REPO_DIR."
   else
      echo "FAIL: Error message missing 'Refusing fallback'."
      echo "$OUTPUT"
      exit 1
   fi
else
   echo "FAIL: Script did not fail on invalid REPO_DIR."
   echo "$OUTPUT"
   exit 1
fi

# 10. Test REPO_DIR System Path Rejection
echo ">>> Test 10: REPO_DIR System Path Rejection"
export REPO_DIR="/usr"
# Create fake file to bypass first check
touch /usr/infra/compose/compose.prod.yml 2>/dev/null || true
# We can't really test this easily without root, but let's try assuming the script checks string value
# Actually the script checks file existence first, so if we can't write to /usr, it fails early.
# We will skip this test if we can't write to /usr (likely).
if [[ -w "/usr" ]]; then
   OUTPUT=$(./scripts/weltgewebe-up --no-pull --no-build 2>&1 || true)
   if echo "$OUTPUT" | grep -q "ERROR: Resolved REPO_DIR is system path"; then
        echo "PASS: System path rejected."
   else
        echo "FAIL: System path NOT rejected."
        exit 1
   fi
else
   echo "SKIP: Cannot write to /usr to test system path rejection."
fi
unset REPO_DIR

# 11. Test Health: Internal Fallback (Docker Native)
echo ">>> Test 11: Health - Internal Fallback (Docker Native)"
export MOCK_PORT_MODE="0"
export MOCK_EXEC_FAIL="0"
# Strategy should default to Docker Native if no port mapping and no gateway
OUTPUT=$(./scripts/weltgewebe-up --no-pull --no-build 2>&1)

if echo "$OUTPUT" | grep -q "Health strategy selected: Docker Native Health"; then
    echo "PASS: Fell back to Docker Native check."
else
    echo "FAIL: Did not use Docker Native check."
    echo "$OUTPUT"
    exit 1
fi

# 12. Test Health: Host Port (Valid)
echo ">>> Test 12: Health - Host Port (Valid)"
export MOCK_PORT_MODE="VALID"
export MOCK_EXEC_FAIL="0"
OUTPUT=$(./scripts/weltgewebe-up --no-pull --no-build 2>&1)

if echo "$OUTPUT" | grep -q "Health strategy selected: Host Port Mapping"; then
    echo "PASS: Used Host Port check when valid."
else
    echo "FAIL: Did not use Host Port check."
    echo "$OUTPUT"
    exit 1
fi

# 13. Test Health: Gateway (Explicit)
echo ">>> Test 13: Health - Gateway (Explicit)"
export MOCK_PORT_MODE="0"
export WELTGEWEBE_GATEWAY_PORT="9081"
OUTPUT=$(./scripts/weltgewebe-up --no-pull --no-build 2>&1)

if echo "$OUTPUT" | grep -q "Health strategy selected: Gateway (Explicit)"; then
    if echo "$OUTPUT" | grep -q "http://127.0.0.1:9081/health/ready"; then
        echo "PASS: Used Gateway check with correct port."
    else
        echo "FAIL: Incorrect gateway URL used."
        echo "$OUTPUT"
        exit 1
    fi
else
    echo "FAIL: Did not use Gateway check."
    echo "$OUTPUT"
    exit 1
fi
unset WELTGEWEBE_GATEWAY_PORT

# 14. Test Health: Explicit URL
echo ">>> Test 14: Health - Explicit URL"
export HEALTH_URL="http://explicit-url:8080/health"
export MOCK_PORT_MODE="VALID"
OUTPUT=$(./scripts/weltgewebe-up --no-pull --no-build 2>&1)

if echo "$OUTPUT" | grep -q "Health strategy selected: ENV:HEALTH_URL"; then
    echo "PASS: Used explicit HEALTH_URL."
else
    echo "FAIL: Did not use explicit HEALTH_URL."
    echo "$OUTPUT"
    exit 1
fi
unset HEALTH_URL

# 15. Test State Dir Customization
echo ">>> Test 15: State Dir Customization"
export WELTGEWEBE_STATE_DIR="$(pwd)/custom_state"
mkdir -p "$WELTGEWEBE_STATE_DIR"
# ENABLE PULL (no flag) so git mock is used and CURRENT_HEAD is set
OUTPUT=$(./scripts/weltgewebe-up --no-build 2>&1)

if [[ -f "$WELTGEWEBE_STATE_DIR/weltgewebe-up.state" ]]; then
    CONTENT=$(cat "$WELTGEWEBE_STATE_DIR/weltgewebe-up.state")
    if [[ "$CONTENT" == "mock-sha-12345" ]]; then
        echo "PASS: State file created in custom directory with correct SHA."
    else
        echo "FAIL: State file content incorrect. Got: $CONTENT"
        exit 1
    fi
else
    echo "FAIL: State file not found in custom directory."
    echo "$OUTPUT"
    exit 1
fi
rm -rf "$WELTGEWEBE_STATE_DIR"
unset WELTGEWEBE_STATE_DIR

# 16. Test Gateway Warning (Port 8081)
echo ">>> Test 16: Gateway Warning (Port 8081)"
export WELTGEWEBE_GATEWAY_PORT="8081"
export MOCK_PORT_MODE="0"
OUTPUT=$(./scripts/weltgewebe-up --no-pull --no-build 2>&1)

if echo "$OUTPUT" | grep -q "WARNING: Port 8081 is usually reserved for Pi-hole"; then
    echo "PASS: Warning detected for port 8081."
else
    echo "FAIL: Warning missing for port 8081."
    echo "$OUTPUT"
    exit 1
fi
unset WELTGEWEBE_GATEWAY_PORT

# 17. Test Configurable Internal Port (Port check verify)
echo ">>> Test 17: Configurable Internal Port (Port check)"
export MOCK_PORT_MODE="0"
export API_INTERNAL_PORT="9090"
# We expect the script to call `docker compose port api 9090`
# Our mock docker will verify this if we set EXPECT_INTERNAL_PORT (though currently only for port check if needed)
# Actually, the mock checks "REQUESTED_PORT" against "EXPECT_INTERNAL_PORT" for port command
export EXPECT_INTERNAL_PORT="9090"
OUTPUT=$(./scripts/weltgewebe-up --no-pull --no-build 2>&1)

if echo "$OUTPUT" | grep -q "Health strategy selected: Docker Native Health"; then
     echo "PASS: Script ran successfully with custom internal port."
else
     echo "FAIL: Script failed or wrong strategy."
     echo "$OUTPUT"
     exit 1
fi
unset API_INTERNAL_PORT
unset EXPECT_INTERNAL_PORT

# Final Cleanup
unset WELTGEWEBE_COMPOSE_BAKE
unset WELTGEWEBE_APPS_PROBE
unset VERIFY_BAKE
unset MOCK_ZOMBIE
unset REPO_DIR
unset MOCK_PORT_MODE
unset MOCK_EXEC_FAIL
unset MOCK_HAS_CADDY

echo ">>> All refined tests passed."
