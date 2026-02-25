#!/bin/bash
# ------------------------------------------------------------------
# Local Mock Test for Deployment Logic
# Not intended for CI execution without mock setup.
# ------------------------------------------------------------------
set -euo pipefail

# Ensure we are in the repo root
cd "$(dirname "$0")/../.."

# 0. Setup Mocks
mkdir -p mock_bin

# Mock Docker
cat << 'EOF' > mock_bin/docker
#!/bin/bash
ARGS="$*"
if [[ "$1" == "ps" ]]; then
  if [[ "$MOCK_ZOMBIE" == "1" ]]; then
    # Return zombie with config path matching current repo
    echo "zombie-container compose $(pwd)/infra/compose/compose.prod.yml"
  elif [[ "$MOCK_ZOMBIE" == "GENERIC" ]]; then
      echo "zombie-generic compose"
  else
    echo ""
  fi
elif [[ "$1" == "rm" ]]; then
    if [[ "$ARGS" == *"-f"* ]]; then
        echo "Mocked remove: $ARGS"
        exit 0
    fi
elif [[ "$1" == "compose" ]]; then
  if [[ "$ARGS" == *" config"* ]]; then
     echo "services: {}"
     exit 0
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

if echo "$OUTPUT" | grep -q "Detected foreign compose project using weltgewebe config"; then
   if echo "$OUTPUT" | grep -q "Repo dir:"; then
      if echo "$OUTPUT" | grep -q "docker compose -p <foreign_project> down"; then
         echo "PASS: Detailed error message found."
      else
         echo "FAIL: Remediation hint missing."
         echo "$OUTPUT"
         exit 1
      fi
   else
      echo "FAIL: Repo dir info missing."
      echo "$OUTPUT"
      exit 1
   fi
else
   echo "FAIL: Zombie detection failed or exit code wrong."
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

# Cleanup
rm -rf mock_bin test.env

echo ">>> All refined tests passed."
