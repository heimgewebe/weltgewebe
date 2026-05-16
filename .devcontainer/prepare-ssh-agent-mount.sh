#!/usr/bin/env bash
set -euo pipefail

target="${HOME}/.ssh/devcontainer-ssh-agent.sock"

mkdir -p "${HOME}/.ssh"
chmod 700 "${HOME}/.ssh"

rm -f "$target"

if [ -n "${SSH_AUTH_SOCK:-}" ] && [ -S "${SSH_AUTH_SOCK}" ]; then
  ln -s "${SSH_AUTH_SOCK}" "$target"
  echo "SSH-AGENT-PREP: linked $target -> $SSH_AUTH_SOCK"
else
  : > "$target"
  chmod 600 "$target"
  echo "SSH-AGENT-PREP: no host SSH agent socket found; created placeholder $target"
fi
