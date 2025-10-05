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
from typing import Sequence


REQUIRED_TOP_LEVEL_KEYS = ("version", "env_priority", "tooling", "tasks")
REQUIRED_TASKS = ("up", "lint", "test", "build", "smoke")


def _error(message: str) -> None:
    """Emit a GitHub Actions friendly error message."""

    print(f"::error::{message}")


def _missing_keys(data: dict[str, object], keys: Iterable[str]) -> list[str]:
    return [key for key in keys if key not in data]


def _load_yaml_module() -> ModuleType | None:
    existing = sys.modules.get("yaml")
    if isinstance(existing, ModuleType):
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

    print("wgx profile OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
