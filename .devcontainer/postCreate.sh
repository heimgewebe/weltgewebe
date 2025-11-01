#!/usr/bin/env bash
set -euo pipefail
corepack enable
corepack prepare pnpm@9.11.0 --activate
pnpm -C apps/web install
