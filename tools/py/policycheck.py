#!/usr/bin/env python3
"""Basic policy consistency checks."""

from __future__ import annotations

import pathlib
import sys

import yaml

FIXED_FADEN_FADE_DAYS = 7


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
        fade_days = lifecycle["fade_days"]
    except (KeyError, TypeError, ValueError) as exc:
        print(f"::error::invalid lifecycle values: {exc}")
        return 1

    default_path = pathlib.Path("configs/app.defaults.yml")
    if not default_path.exists():
        print("::error::configs/app.defaults.yml missing")
        return 1
    defaults = yaml.safe_load(default_path.read_text(encoding="utf-8")) or {}
    default_fade_days = defaults.get("fade_days")

    for source, value in (
        ("policies/retention.yml", fade_days),
        ("configs/app.defaults.yml", default_fade_days),
    ):
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value != FIXED_FADEN_FADE_DAYS
        ):
            print(
                f"::error::{source} fade_days must be exactly {FIXED_FADEN_FADE_DAYS}; "
                "it mirrors the fixed constitutional Faden lifetime and is not a tuning setting"
            )
            return 1

    for source, mapping in (
        ("policies/retention.yml data_lifecycle", lifecycle),
        ("configs/app.defaults.yml", defaults),
    ):
        if "ron_days" in mapping:
            print(
                f"::error::{source} must not publish ron_days; "
                "no runtime RON retention consumer exists"
            )
            return 1

    print("policy ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
