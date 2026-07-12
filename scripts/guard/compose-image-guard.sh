#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="${REPO_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." > /dev/null 2>&1 && pwd)}"
python3 - "$REPO_ROOT" << 'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
compose_dir = root / "infra" / "compose"
prod = compose_dir / "compose.prod.yml"
failures: list[str] = []

if not prod.is_file():
    failures.append(f"production compose file missing: {prod}")
else:
    text = prod.read_text(encoding="utf-8")
    expected = "image: weltgewebe-api:${API_VERSION:?API_VERSION must be set}"
    if expected not in text:
        failures.append("production API image must require a concrete API_VERSION")

image_re = re.compile(r"^\s*image:\s*([^\s#]+)")
digest_re = re.compile(r"@sha256:[0-9a-f]{64}$")

for path in sorted(compose_dir.glob("*.y*ml")):
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = image_re.match(line)
        if not match:
            continue
        image = match.group(1)
        rel = path.relative_to(root)
        if image == "weltgewebe-api:${API_VERSION:?API_VERSION":
            # The unquoted Compose interpolation contains spaces; verify the full line.
            if line.strip() != "image: weltgewebe-api:${API_VERSION:?API_VERSION must be set}":
                failures.append(f"{rel}:{line_no} malformed API image contract")
            continue
        if "${" in image:
            failures.append(f"{rel}:{line_no} variable image reference is not statically reviewable: {image}")
            continue
        if ":latest" in image or ":-latest" in image:
            failures.append(f"{rel}:{line_no} latest tag/fallback is forbidden: {image}")
        if not digest_re.search(image):
            failures.append(f"{rel}:{line_no} external image is not pinned by sha256 digest: {image}")

if failures:
    for finding in failures:
        print(f"ERROR: {finding}", file=sys.stderr)
    raise SystemExit(1)
print("PASS: all external Compose images are digest-pinned and the API tag is fail-closed")
PY
