#!/usr/bin/env bash
set -euo pipefail

if [ -z "${SSH_AUTH_SOCK:-}" ] || [ ! -S "${SSH_AUTH_SOCK}" ]; then
  cat >&2 <<'EOF'
SSH-AGENT-GUARD: no forwarded SSH agent socket found.

Expected:
  SSH_AUTH_SOCK points to the forwarded host SSH agent.

Meaning:
  The devcontainer should use the host SSH agent. Private SSH keys must stay on the host.

Fix on host:
  eval "$(ssh-agent -s)"
  ssh-add ~/.ssh/id_ed25519
  then rebuild/reopen the devcontainer.

Do not copy private keys into the container.
EOF
  exit 68
fi

if ! ssh-add -l >/dev/null 2>&1; then
  cat >&2 <<'EOF'
SSH-AGENT-GUARD: forwarded SSH agent is available, but no identities are loaded.

Fix on host:
  ssh-add ~/.ssh/id_ed25519
  then rebuild/reopen the devcontainer.
EOF
  exit 69
fi

mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"

if ! ssh-keygen -F github.com -f "$HOME/.ssh/known_hosts" >/dev/null 2>&1; then
  ssh-keyscan github.com >> "$HOME/.ssh/known_hosts" 2>/dev/null || true
  chmod 600 "$HOME/.ssh/known_hosts" || true
fi

echo "SSH-AGENT-GUARD: ok agent=${SSH_AUTH_SOCK}"
