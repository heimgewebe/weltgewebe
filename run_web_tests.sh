#!/bin/bash
# Convenience wrapper for running apps/web checks from the repository root
set -e
pnpm --dir apps/web check
pnpm --dir apps/web lint
pnpm --dir apps/web test
