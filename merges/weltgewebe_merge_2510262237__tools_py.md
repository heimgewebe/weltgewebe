### 📄 tools/py/README.md

**Größe:** 296 B | **md5:** `6a43f76336f99f1d2caf09c2b5ad8e7f`

```markdown
# Weltgewebe – Python Tools

## Schnellstart

```bash
cd tools/py
uv sync        # erstellt venv, installiert deps (aktuell leer)
uv run python -V
```

## Abhängigkeiten hinzufügen

```bash
uv add ruff black
```

Das erzeugt/aktualisiert `uv.lock` – damit sind Builds in CI reproduzierbar.
```

### 📄 tools/py/policycheck.py

**Größe:** 1 KB | **md5:** `1531eb55d304c38c6b8ceb91980e0a7c`

```python
#!/usr/bin/env python3
"""Basic policy consistency checks."""

from __future__ import annotations

import pathlib
import sys

import yaml


def main() -> int:
    policy_path = pathlib.Path("policies/retention.yml")
    if not policy_path.exists():
        print("::error::policies/retention.yml missing")
        return 1

    data = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
    lifecycle = data.get("data_lifecycle")
    if not isinstance(lifecycle, dict):
        print("::error::data_lifecycle section missing")
        return 1

    try:
        fade_days = int(lifecycle["fade_days"])
        ron_days = int(lifecycle["ron_days"])
    except (KeyError, TypeError, ValueError) as exc:
        print(f"::error::invalid lifecycle values: {exc}")
        return 1

    if fade_days <= 0:
        print("::error::fade_days must be > 0")
        return 1

    if ron_days < fade_days:
        print("::error::ron_days must be >= fade_days")
        return 1

    print("policy ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### 📄 tools/py/pyproject.toml

**Größe:** 259 B | **md5:** `96b3e59f00667138a66ea5d634b58b6b`

```toml
[project]
name = "weltgewebe-tools"
version = "0.1.0"
description = "Python tooling for Weltgewebe (CLI, lint, ETL, experiments)"
requires-python = ">=3.11"
dependencies = []

[tool.uv]
# uv verwaltet Lockfile uv.lock im Projektroot oder hier im Unterordner.
```

