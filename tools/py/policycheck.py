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
