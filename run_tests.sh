#!/bin/bash
set -e
pnpm check
pnpm lint
pnpm test
