### 📄 weltgewebe/ci/scripts/db-wait.sh

**Größe:** 498 B | **md5:** `4e3c7e73e15e8450e658938904534c12`

```bash
#!/usr/bin/env bash
set -euo pipefail

HOST=${PGHOST:-localhost}
PORT=${PGPORT:-5432}
TIMEOUT=${DB_WAIT_TIMEOUT:-60}
INTERVAL=${DB_WAIT_INTERVAL:-2}

declare -i end=$((SECONDS + TIMEOUT))

while (( SECONDS < end )); do
    if (echo >"/dev/tcp/${HOST}/${PORT}") >/dev/null 2>&1; then
        printf 'Postgres is available at %s:%s\n' "$HOST" "$PORT"
        exit 0
    fi
    sleep "$INTERVAL"
done

printf 'Timed out waiting for Postgres at %s:%s after %ss\n' "$HOST" "$PORT" "$TIMEOUT" >&2
exit 1
```

### 📄 weltgewebe/ci/scripts/validate_wgx_profile.py

**Größe:** 4 KB | **md5:** `53f8d63e9450ddffc57ceff725f860ee`

```python
# SPDX-License-Identifier: MIT
# -*- coding: utf-8 -*-

"""Validate the minimal schema for ``.wgx/profile.yml``.

The wgx-guard workflow embeds this script and previously relied on an inline
Python snippet. A subtle indentation slip in that snippet caused
``IndentationError`` failures in CI.  To make the validation robust we keep the
logic in this dedicated module and ensure the implementation is intentionally
simple and well formatted.
"""

from __future__ import annotations

import importlib
import importlib.util
import pathlib
import sys
from types import ModuleType
from collections.abc import Iterable, Mapping


REQUIRED_TOP_LEVEL_KEYS = ("version", "env_priority", "tooling", "tasks", "wgx")
REQUIRED_WGX_KEYS = ("org",)
REQUIRED_TASKS = ("up", "lint", "test", "build", "smoke")


def _error(message: str) -> None:
    """Emit a GitHub Actions friendly error message."""

    print(f"::error::{message}")


def _missing_keys(data: Mapping[str, object], keys: Iterable[str]) -> list[str]:
    return [key for key in keys if key not in data]


def _load_yaml_module() -> ModuleType | None:
    existing = sys.modules.get("yaml")
    if isinstance(existing, ModuleType) and hasattr(existing, "safe_load"):
        return existing

    module = importlib.util.find_spec("yaml")
    if module is None:
        _error(
            "PyYAML not installed. Install it with 'python -m pip install pyyaml' before running this script."
        )
        return None

    return importlib.import_module("yaml")


def main() -> int:
    yaml = _load_yaml_module()
    if yaml is None:
        return 1

    profile_path = pathlib.Path(".wgx/profile.yml")

    try:
        contents = profile_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        _error(".wgx/profile.yml missing")
        return 1

    try:
        data = yaml.safe_load(contents) or {}
    except yaml.YAMLError as exc:  # pragma: no cover - best effort logging
        _error(f"failed to parse YAML: {exc}")
        return 1

    if not isinstance(data, dict):
        _error("profile must be a mapping")
        return 1

    missing_top_level = _missing_keys(data, REQUIRED_TOP_LEVEL_KEYS)
    if missing_top_level:
        _error(f"missing keys: {missing_top_level}")
        return 1

    env_priority = data.get("env_priority")
    if not isinstance(env_priority, list) or not env_priority:
        _error("env_priority must be a non-empty list")
        return 1

    tasks = data.get("tasks")
    if not isinstance(tasks, dict):
        _error("tasks must be a mapping")
        return 1

    missing_tasks = _missing_keys(tasks, REQUIRED_TASKS)
    if missing_tasks:
        _error(f"missing tasks: {missing_tasks}")
        return 1

    wgx_block = data.get("wgx")
    if not isinstance(wgx_block, dict):
        _error("wgx must be a mapping")
        return 1

    missing_wgx = _missing_keys(wgx_block, REQUIRED_WGX_KEYS)
    if missing_wgx:
        _error(f"wgx missing keys: {missing_wgx}")
        return 1

    org = wgx_block.get("org")
    if not isinstance(org, str) or not org.strip():
        _error("wgx.org must be a non-empty string")
        return 1

    meta = data.get("meta")
    if isinstance(meta, dict) and "owner" in meta:
        owner = meta.get("owner")
        if not isinstance(owner, str) or not owner.strip():
            _error("meta.owner must be a non-empty string when provided")
            return 1
        if owner != org:
            _error(f"meta.owner ({owner!r}) must match wgx.org ({org!r})")
            return 1

    print("wgx profile OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

