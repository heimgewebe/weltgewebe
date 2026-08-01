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

    default_path = pathlib.Path("configs/app.defaults.yml")
    if not default_path.exists():
        print("::error::configs/app.defaults.yml missing")
        return 1
    defaults = yaml.safe_load(default_path.read_text(encoding="utf-8")) or {}

    for source, mapping in (
        ("policies/retention.yml data_lifecycle", lifecycle),
        ("configs/app.defaults.yml", defaults),
    ):
        if "fade_days" in mapping:
            print(
                f"::error::{source} must not publish fade_days; the Faden lifetime is "
                f"the fixed constitutional value of {FIXED_FADEN_FADE_DAYS} days"
            )
            return 1
        if "ron_days" in mapping:
            print(
                f"::error::{source} must not publish ron_days; "
                "no runtime RON retention consumer exists"
            )
            return 1
        if "delegation_expire_days" in mapping:
            print(
                f"::error::{source} must not publish delegation_expire_days; "
                "no runtime delegation-expiry consumer exists"
            )
            return 1
        if "anonymize_opt_in" in mapping:
            print(
                f"::error::{source} must not publish anonymize_opt_in; "
                "no runtime anonymization consumer exists"
            )
            return 1

    print("policy ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
