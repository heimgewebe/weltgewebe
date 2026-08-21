#!/usr/bin/env python3
"""Basic policy consistency checks."""

from __future__ import annotations

import json
import pathlib
import sys

import yaml

FIXED_FADEN_FADE_DAYS = 7
SLO_ALLOWED_ROOT_KEYS = {"version", "contract_kind", "performance_contract", "services"}
SLO_ALLOWED_SERVICE_KEYS = {"availability_target_pct", "performance_measurement_ref"}
SLO_REQUIRED_SERVICES = {"web", "api"}


def validate_slo_policy() -> str | None:
    slo_path = pathlib.Path("policies/slo.yaml")
    if not slo_path.exists():
        return "policies/slo.yaml missing"
    slo = yaml.safe_load(slo_path.read_text(encoding="utf-8")) or {}
    if not isinstance(slo, dict):
        return "policies/slo.yaml root must be a mapping"

    unknown_root = sorted(set(slo) - SLO_ALLOWED_ROOT_KEYS)
    missing_root = sorted(SLO_ALLOWED_ROOT_KEYS - set(slo))
    if unknown_root or missing_root:
        return (
            "policies/slo.yaml must be objectives-only with exact root keys; "
            f"unknown={unknown_root}, missing={missing_root}"
        )
    if slo.get("version") != 3:
        return "policies/slo.yaml version must be 3 for the objectives-only contract"
    if slo.get("contract_kind") != "objectives_only":
        return "policies/slo.yaml contract_kind must be objectives_only; it is not a runtime control surface"

    performance_ref = slo.get("performance_contract")
    if performance_ref != "policies/performance.v1.json":
        return "policies/slo.yaml performance_contract must reference policies/performance.v1.json"
    performance_path = pathlib.Path(str(performance_ref))
    if not performance_path.exists():
        return f"referenced performance contract missing: {performance_ref}"
    try:
        performance = json.loads(performance_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return f"failed to read referenced performance contract {performance_ref}: {error}"
    measurements = performance.get("measurements") if isinstance(performance, dict) else None
    if not isinstance(measurements, dict):
        return f"referenced performance contract {performance_ref} has no measurements mapping"

    services = slo.get("services")
    if not isinstance(services, dict) or set(services) != SLO_REQUIRED_SERVICES:
        return (
            "policies/slo.yaml services must contain exactly web and api; "
            f"found={sorted(services) if isinstance(services, dict) else type(services).__name__}"
        )
    for service_name, service in services.items():
        if not isinstance(service, dict):
            return f"policies/slo.yaml services.{service_name} must be a mapping"
        unknown_service = sorted(set(service) - SLO_ALLOWED_SERVICE_KEYS)
        missing_service = sorted(SLO_ALLOWED_SERVICE_KEYS - set(service))
        if unknown_service or missing_service:
            return (
                f"policies/slo.yaml services.{service_name} must expose objectives only; "
                f"unknown={unknown_service}, missing={missing_service}"
            )
        target = service.get("availability_target_pct")
        if isinstance(target, bool) or not isinstance(target, (int, float)) or not (0 < target <= 100):
            return (
                f"policies/slo.yaml services.{service_name}.availability_target_pct "
                "must be a percentage greater than 0 and at most 100"
            )
        measurement_ref = service.get("performance_measurement_ref")
        prefix = "measurements."
        if not isinstance(measurement_ref, str) or not measurement_ref.startswith(prefix):
            return (
                f"policies/slo.yaml services.{service_name}.performance_measurement_ref "
                "must reference measurements.<name> in the canonical performance contract"
            )
        measurement_name = measurement_ref[len(prefix) :]
        if not measurement_name or measurement_name not in measurements:
            return (
                f"policies/slo.yaml services.{service_name}.performance_measurement_ref "
                f"points to missing measurement {measurement_ref!r}"
            )
    return None


def find_key_paths(value: object, target: str, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if key == target:
                paths.append(path)
            paths.extend(find_key_paths(child, target, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            paths.extend(find_key_paths(child, target, f"{prefix}[{index}]"))
    return paths


def main() -> int:
    policy_path = pathlib.Path("policies/retention.yml")
    if not policy_path.exists():
        print("::error::policies/retention.yml missing")
        return 1

    data = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        print("::error::policies/retention.yml root must be a mapping")
        return 1
    lifecycle = data.get("data_lifecycle")
    if not isinstance(lifecycle, dict):
        print("::error::data_lifecycle section missing")
        return 1

    default_path = pathlib.Path("configs/app.defaults.yml")
    if not default_path.exists():
        print("::error::configs/app.defaults.yml missing")
        return 1
    defaults = yaml.safe_load(default_path.read_text(encoding="utf-8")) or {}
    if not isinstance(defaults, dict):
        print("::error::configs/app.defaults.yml root must be a mapping")
        return 1

    slo_error = validate_slo_policy()
    if slo_error is not None:
        print(f"::error::{slo_error}")
        return 1

    if "forget_pipeline" in data:
        print(
            "::error::policies/retention.yml must not publish forget_pipeline; "
            "guest exit is immediate and no deferred forget scheduler exists"
        )
        return 1

    for source, mapping in (
        ("policies/retention.yml", data),
        ("configs/app.defaults.yml", defaults),
    ):
        deadline_paths = find_key_paths(mapping, "deadline_days")
        if deadline_paths:
            print(
                f"::error::{source} must not publish unsupported deadline_days "
                f"at {', '.join(deadline_paths)}; no runtime deadline consumer exists"
            )
            return 1

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
