#!/bin/bash
set -e
pnpm --dir apps/web check
pnpm --dir apps/web lint
pnpm --dir apps/web test
