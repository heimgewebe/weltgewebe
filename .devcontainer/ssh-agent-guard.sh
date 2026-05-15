#!/usr/bin/env bash
set -euo pipefail

mode="${1:-agent}"
required="${REQUIRE_SSH_AGENT:-0}"

fail_or_warn() {
  code="$1"
  shift
  if [ "$required" = "1" ]; then
    printf '%s\n' "$*" >&2
    exit "$code"
  fi

  printf '%s\n' "$*" >&2
  printf '%s\n' "SSH-AGENT-GUARD: warning only. Set REQUIRE_SSH_AGENT=1 to make this fatal." >&2
  exit 0
}

if [ -z "${SSH_AUTH_SOCK:-}" ] || [ ! -S "${SSH_AUTH_SOCK}" ]; then
  fail_or_warn 68 "SSH-AGENT-GUARD: no forwarded SSH agent socket found.

Expected:
  SSH_AUTH_SOCK points to the forwarded host SSH agent.

Meaning:
  The devcontainer should use the host SSH agent. Private SSH keys must stay on the host.

Fix on host:
  eval \"\$(ssh-agent -s)\"
  ssh-add ~/.ssh/id_ed25519
  then rebuild/reopen the devcontainer.

Do not copy private keys into the container."
fi

if ! ssh-add -l >/dev/null 2>&1; then
  fail_or_warn 69 "SSH-AGENT-GUARD: forwarded SSH agent is available, but no identities are loaded.

Fix on host:
  ssh-add ~/.ssh/id_ed25519
  then rebuild/reopen the devcontainer."
fi

mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"

if [ ! -f "$HOME/.ssh/known_hosts" ]; then
  touch "$HOME/.ssh/known_hosts"
  chmod 600 "$HOME/.ssh/known_hosts"
fi

if ! ssh-keygen -F github.com -f "$HOME/.ssh/known_hosts" >/dev/null 2>&1; then
  echo "SSH-AGENT-GUARD: github.com missing from known_hosts; adding via ssh-keyscan TOFU." >&2
  ssh-keyscan github.com >> "$HOME/.ssh/known_hosts" 2>/dev/null || true
  chmod 600 "$HOME/.ssh/known_hosts" || true
fi

if [ "$mode" = "github" ]; then
  output="$(ssh -T git@github.com 2>&1 || true)"
  printf '%s\n' "$output"

  case "$output" in
    *"successfully authenticated"*)
      echo "SSH-AGENT-GUARD: ok GitHub SSH authentication works."
      ;;
    *)
      echo "SSH-AGENT-GUARD: GitHub SSH authentication was not proven." >&2
      exit 70
      ;;
  esac
else
  echo "SSH-AGENT-GUARD: ok agent=${SSH_AUTH_SOCK}"
fi
