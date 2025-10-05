"""Validate the minimal schema for .wgx/profile.yml."""

from __future__ import annotations

import pathlib
import sys
from typing import Sequence

import yaml


def _error(message: str) -> None:
    print(f"::error::{message}")


def _require_keys(data: dict[str, object], keys: Sequence[str]) -> bool:
    missing = [key for key in keys if key not in data]
    if missing:
        _error(f"missing keys: {missing}")
        return False
    return True


def main() -> int:
    profile_path = pathlib.Path(".wgx/profile.yml")
    try:
        contents = profile_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        _error(".wgx/profile.yml missing")
        return 1

    try:
        data = yaml.safe_load(contents)
    except yaml.YAMLError as exc:  # pragma: no cover - best effort logging
        _error(f"failed to parse YAML: {exc}")
        return 1

    if not isinstance(data, dict):
        _error("profile must be a mapping")
        return 1

    top_level_required = ["version", "env_priority", "tooling", "tasks"]
    if not _require_keys(data, top_level_required):
        return 1

    env_priority = data.get("env_priority")
    if not isinstance(env_priority, list) or not env_priority:
        _error("env_priority must be a non-empty list")
        return 1

    tasks = data.get("tasks")
    if not isinstance(tasks, dict):
        _error("tasks must be a mapping")
        return 1

    for task_name in ["up", "lint", "test", "build", "smoke"]:
        if task_name not in tasks:
            _error(f"task '{task_name}' missing")
            return 1

    print("wgx profile OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
