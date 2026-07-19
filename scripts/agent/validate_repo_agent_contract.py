#!/usr/bin/env python3
"""Validate the canonical repository agent contract and projection parity.

The repository owns machine-readable agent norms as strict JSON. YAML files that
still expose overlapping path/check fields are compatibility projections only.
This validator:

1. loads agent-contract.json with the strict JSON contract loader
2. validates it against contracts/agent/agent-contract.schema.json
3. enforces semantic invariants beyond pure schema shape
4. checks exact parity of declared projection fields in YAML mirrors

The established PyYAML parser is used to load projections. Extraction is limited
to the declared top-level list keys that the contract itself names.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any

import yaml


class StrictSafeLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        mapping = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in mapping:
                raise yaml.constructor.ConstructorError(
                    f"found duplicate key {key!r}", key_node.start_mark
                )
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping

StrictSafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    StrictSafeLoader.construct_mapping
)

def load_yaml_strict(text: str) -> Any:
    return yaml.load(text, Loader=StrictSafeLoader)

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.agent.json_contract import (
    DuplicateKeyError,
    UnsupportedSchemaError,
    load_json_strict,
    validate_instance,
)
from scripts.docmeta.docmeta import REPO_ROOT

CONTRACT_REL = "agent-contract.json"
SCHEMA_REL = "contracts/agent/agent-contract.schema.json"

READING_ORDER_REQUIRED = [
    "agent-contract.json",
    "repo.meta.yaml",
    "AGENTS.md",
    "agent-policy.yaml",
    "docs/policies/agent-reading-protocol.md",
]

ARCHITECTURE_REQUIRED = {
    "repo_role": "repo_contract_authority",
    "operator_role": "external_operator_execution",
    "operator_name": "grabowski",
    "repo_generic_write_mode": "rejected",
}

AUTHORITY_GUARDED_PATHS = [
    ".wgx/generated-artifacts.yml",
    "agent-contract.json",
]

ALLOWED_GENERATED_TARGET_PREFIXES = ["docs/_generated/"]


def _finding(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def extract_top_level_string_list(text: str, key: str) -> list[str] | Exception | None:
    """Extract one top-level YAML list of scalar strings, or return Exception if invalid YAML."""
    try:
        data = load_yaml_strict(text)
        if isinstance(data, dict):
            value = data.get(key)
            if isinstance(value, list) and all(isinstance(v, str) for v in value):
                return value
    except yaml.YAMLError as e:
        return e
    except Exception as e:
        return e
    return None


def _is_safe_repo_relative_file_path(path: str) -> bool:
    if not path or "\\" in path:
        return False
    parsed = PurePosixPath(path)
    return not parsed.is_absolute() and ".." not in parsed.parts and path == parsed.as_posix()


def _path_is_under_prefix(path: str, prefix: str) -> bool:
    if prefix.endswith("/"):
        return path == prefix[:-1] or path.startswith(prefix)
    return path == prefix or path.startswith(prefix + "/")


def _is_generated_target(path: str, target_prefixes: list[str]) -> bool:
    for prefix in target_prefixes:
        if _path_is_under_prefix(path, prefix):
            return True
    return False


def validate_semantic_invariants(
    repo_root: Path, contract: dict[str, Any]
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []

    architecture = contract.get("architecture")
    if not isinstance(architecture, dict):
        findings.append(
            _finding(
                "AGENT_CONTRACT_ARCHITECTURE",
                "$.architecture",
                "architecture block is required",
            )
        )
    else:
        for key, expected in ARCHITECTURE_REQUIRED.items():
            if architecture.get(key) != expected:
                findings.append(
                    _finding(
                        "AGENT_CONTRACT_ARCHITECTURE",
                        f"$.architecture.{key}",
                        f"expected {expected!r}",
                    )
                )

    reading_order = contract.get("reading_order")
    if not isinstance(reading_order, list):
        findings.append(
            _finding(
                "AGENT_CONTRACT_READING_ORDER",
                "$.reading_order",
                "reading_order must be an array",
            )
        )
    else:
        if reading_order != READING_ORDER_REQUIRED:
            findings.append(
                _finding(
                    "AGENT_CONTRACT_READING_ORDER",
                    "$.reading_order",
                    "reading_order must equal the canonical schema-version-1 sequence",
                )
            )

    for field in (
        "safe_read_paths",
        "guarded_write_paths",
        "forbidden_write_paths",
        "required_checks",
        "local_checks_before_patch",
    ):
        value = contract.get(field)
        if not isinstance(value, list) or not value:
            findings.append(
                _finding(
                    "AGENT_CONTRACT_PATHS",
                    f"$.{field}",
                    f"{field} must be a non-empty list",
                )
            )

    guarded = contract.get("guarded_write_paths")
    if isinstance(guarded, list):
        for authority_path in AUTHORITY_GUARDED_PATHS:
            if authority_path not in guarded:
                findings.append(
                    _finding(
                        "AGENT_CONTRACT_AUTHORITY_GUARD",
                        "$.guarded_write_paths",
                        f"authority path must be guarded: {authority_path}",
                    )
                )

    forbidden = contract.get("forbidden_write_paths")
    if isinstance(forbidden, list) and "docs/_generated/" not in forbidden:
        findings.append(
            _finding(
                "AGENT_CONTRACT_FORBIDDEN",
                "$.forbidden_write_paths",
                "docs/_generated/ must be a direct forbidden write path",
            )
        )

    generated = contract.get("generated_artifacts")
    if not isinstance(generated, dict):
        findings.append(
            _finding(
                "AGENT_CONTRACT_GENERATED",
                "$.generated_artifacts",
                "generated_artifacts block is required",
            )
        )
        return findings

    if generated.get("direct_agent_edit") != "forbidden":
        findings.append(
            _finding(
                "AGENT_CONTRACT_GENERATED",
                "$.generated_artifacts.direct_agent_edit",
                "direct agent edits of generated artifacts must be forbidden",
            )
        )
    if generated.get("derived_write_authority") != "trusted_generators_only":
        findings.append(
            _finding(
                "AGENT_CONTRACT_GENERATED",
                "$.generated_artifacts.derived_write_authority",
                "only trusted generators may write derived artifacts",
            )
        )

    allowed_target_prefixes = generated.get("allowed_target_prefixes")
    if allowed_target_prefixes != ALLOWED_GENERATED_TARGET_PREFIXES:
        findings.append(
            _finding(
                "AGENT_CONTRACT_GENERATED_TARGETS",
                "$.generated_artifacts.allowed_target_prefixes",
                (
                    "allowed_target_prefixes must be exactly "
                    f"{ALLOWED_GENERATED_TARGET_PREFIXES!r}"
                ),
            )
        )
    if isinstance(forbidden, list):
        for prefix in ALLOWED_GENERATED_TARGET_PREFIXES:
            if prefix not in forbidden:
                findings.append(
                    _finding(
                        "AGENT_CONTRACT_GENERATED_TARGETS",
                        "$.forbidden_write_paths",
                        f"trusted generated target prefix must remain directly forbidden: {prefix}",
                    )
                )

    registry_path = generated.get("trusted_generator_registry")
    if not isinstance(registry_path, str) or not registry_path.strip():
        findings.append(
            _finding(
                "AGENT_CONTRACT_GENERATED",
                "$.generated_artifacts.trusted_generator_registry",
                "trusted_generator_registry path is required",
            )
        )
        return findings

    if registry_path != ".wgx/generated-artifacts.yml":
        findings.append(
            _finding(
                "AGENT_CONTRACT_REGISTRY_ERROR",
                registry_path,
                "trusted_generator_registry must be exactly '.wgx/generated-artifacts.yml'",
            )
        )
        return findings

    abs_registry = repo_root / registry_path
    if not abs_registry.is_file():
        findings.append(
            _finding(
                "AGENT_CONTRACT_REGISTRY_MISSING",
                registry_path,
                "generator registry file is missing",
            )
        )
        return findings

    try:
        registry_text = abs_registry.read_text(encoding="utf-8")
        registry_data = load_yaml_strict(registry_text)
    except (yaml.YAMLError, OSError, TypeError, ValueError) as e:
        findings.append(
            _finding(
                "AGENT_CONTRACT_REGISTRY_ERROR",
                registry_path,
                f"invalid YAML: {e}",
            )
        )
        return findings

    if not isinstance(registry_data, dict):
        findings.append(
            _finding(
                "AGENT_CONTRACT_REGISTRY_ERROR",
                registry_path,
                "registry must be an object",
            )
        )
        return findings

    artifacts = registry_data.get("artifacts")
    if not isinstance(artifacts, list):
        findings.append(
            _finding(
                "AGENT_CONTRACT_REGISTRY_ERROR",
                f"{registry_path}:artifacts",
                "artifacts must be a list",
            )
        )
        return findings

    seen_paths: set[str] = set()

    for index, artifact in enumerate(artifacts):
        base = f"{registry_path}:artifacts[{index}]"
        if not isinstance(artifact, dict):
            findings.append(
                _finding(
                    "AGENT_CONTRACT_REGISTRY_ERROR",
                    base,
                    "artifact entry must be an object",
                )
            )
            continue

        path = artifact.get("path")
        if not isinstance(path, str) or not path.strip():
            findings.append(
                _finding(
                    "AGENT_CONTRACT_REGISTRY_ERROR",
                    f"{base}.path",
                    "artifact path is required",
                )
            )
            continue

        if not _is_safe_repo_relative_file_path(path):
            findings.append(
                _finding(
                    "AGENT_CONTRACT_REGISTRY_ERROR",
                    f"{base}.path",
                    "artifact path must be a normalized repository-relative file path",
                )
            )
            continue

        if path in seen_paths:
            findings.append(
                _finding(
                    "AGENT_CONTRACT_REGISTRY_ERROR",
                    f"{base}.path",
                    f"duplicate artifact path: {path}",
                )
            )
        seen_paths.add(path)

        kind = artifact.get("kind")
        if kind == "generated":
            if not _is_generated_target(path, ALLOWED_GENERATED_TARGET_PREFIXES):
                findings.append(
                    _finding(
                        "AGENT_CONTRACT_REGISTRY_ERROR",
                        f"{base}.path",
                        "generated artifact must stay under an allowed_target_prefixes prefix",
                    )
                )

            generator = artifact.get("generator")
            if not isinstance(generator, list) or not generator:
                findings.append(
                    _finding(
                        "AGENT_CONTRACT_REGISTRY_ERROR",
                        f"{base}.generator",
                        "generated artifact must declare a non-empty generator argv list",
                    )
                )
            elif not all(isinstance(v, str) and v.strip() for v in generator):
                findings.append(
                    _finding(
                        "AGENT_CONTRACT_REGISTRY_ERROR",
                        f"{base}.generator",
                        "generator must be a list of strings",
                    )
                )

        checks = artifact.get("checks")
        if checks is not None:
            if not isinstance(checks, list):
                findings.append(
                    _finding(
                        "AGENT_CONTRACT_REGISTRY_ERROR",
                        f"{base}.checks",
                        "checks must be a list of argv lists",
                    )
                )
            else:
                for c_idx, check in enumerate(checks):
                    if not isinstance(check, list) or not check or not all(
                        isinstance(v, str) and v.strip() for v in check
                    ):
                        findings.append(
                            _finding(
                                "AGENT_CONTRACT_REGISTRY_ERROR",
                                f"{base}.checks[{c_idx}]",
                                "each check must be an argv list of strings",
                            )
                        )

    profiles = contract.get("validation_profiles")
    if not isinstance(profiles, dict) or not profiles:
        findings.append(
            _finding(
                "AGENT_CONTRACT_PROFILES",
                "$.validation_profiles",
                "named validation profiles are required",
            )
        )
    else:
        for name, profile in profiles.items():
            if not isinstance(profile, dict):
                findings.append(
                    _finding(
                        "AGENT_CONTRACT_PROFILES",
                        f"$.validation_profiles.{name}",
                        "profile must be an object",
                    )
                )
                continue
            named_checks = profile.get("named_checks")
            if not isinstance(named_checks, list) or not named_checks:
                findings.append(
                    _finding(
                        "AGENT_CONTRACT_PROFILES",
                        f"$.validation_profiles.{name}.named_checks",
                        "profile must declare named_checks",
                    )
                )

    return findings


def validate_projection_parity(
    repo_root: Path, contract: dict[str, Any]
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    projections = contract.get("compatibility_projections")
    if not isinstance(projections, list):
        return [
            _finding(
                "AGENT_CONTRACT_PROJECTION",
                "$.compatibility_projections",
                "compatibility_projections must be an array",
            )
        ]

    for index, projection in enumerate(projections):
        base = f"$.compatibility_projections[{index}]"
        if not isinstance(projection, dict):
            findings.append(
                _finding(
                    "AGENT_CONTRACT_PROJECTION",
                    base,
                    "projection must be an object",
                )
            )
            continue
        if projection.get("role") != "compatibility_projection":
            findings.append(
                _finding(
                    "AGENT_CONTRACT_PROJECTION",
                    f"{base}.role",
                    "projection role must be compatibility_projection",
                )
            )

        rel_path = projection.get("path")
        if not isinstance(rel_path, str) or not rel_path.strip():
            findings.append(
                _finding(
                    "AGENT_CONTRACT_PROJECTION",
                    f"{base}.path",
                    "projection path is required",
                )
            )
            continue

        if not _is_safe_repo_relative_file_path(rel_path):
            findings.append(
                _finding(
                    "AGENT_CONTRACT_PROJECTION",
                    f"{base}.path",
                    "projection path must be a normalized repository-relative file path",
                )
            )
            continue

        abs_path = repo_root / rel_path
        if not abs_path.is_file():
            findings.append(
                _finding(
                    "AGENT_CONTRACT_PROJECTION",
                    rel_path,
                    "compatibility projection file is missing",
                )
            )
            continue

        text = abs_path.read_text(encoding="utf-8")
        marker_tokens = (
            "compatibility projection",
            "compatibility_projection",
            "Compatibility Projection",
        )
        if not any(token in text for token in marker_tokens):
            findings.append(
                _finding(
                    "AGENT_CONTRACT_PROJECTION_MARKER",
                    rel_path,
                    "projection must declare itself as a Compatibility Projection",
                )
            )

        field_map = projection.get("projected_fields")
        if not isinstance(field_map, dict):
            findings.append(
                _finding(
                    "AGENT_CONTRACT_PROJECTION",
                    f"{base}.projected_fields",
                    "projected_fields must be an object",
                )
            )
            continue

        for canonical_field, projection_key in field_map.items():
            expected = contract.get(canonical_field)
            if not isinstance(expected, list):
                findings.append(
                    _finding(
                        "AGENT_CONTRACT_PROJECTION",
                        f"$.{canonical_field}",
                        "canonical projected field must be a list",
                    )
                )
                continue
            if not isinstance(projection_key, str) or not projection_key.strip():
                findings.append(
                    _finding(
                        "AGENT_CONTRACT_PROJECTION",
                        f"{base}.projected_fields.{canonical_field}",
                        "projection key must be a non-empty string",
                    )
                )
                continue
            actual = extract_top_level_string_list(text, projection_key)
            if isinstance(actual, Exception):
                findings.append(
                    _finding(
                        "AGENT_CONTRACT_PROJECTION_YAML_ERROR",
                        f"{rel_path}",
                        f"invalid YAML format: {actual}",
                    )
                )
                continue
            if actual is None:
                findings.append(
                    _finding(
                        "AGENT_CONTRACT_PROJECTION_DRIFT",
                        f"{rel_path}:{projection_key}",
                        f"could not extract projected list for {projection_key}",
                    )
                )
                continue
            if actual != expected:
                findings.append(
                    _finding(
                        "AGENT_CONTRACT_PROJECTION_DRIFT",
                        f"{rel_path}:{projection_key}",
                        (
                            f"projection drift for {canonical_field}: "
                            f"expected {expected!r}, found {actual!r}"
                        ),
                    )
                )

    return findings


def validate_repo_agent_contract(repo_root: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    contract_path = repo_root / CONTRACT_REL
    schema_path = repo_root / SCHEMA_REL

    try:
        if not contract_path.is_file():
            return [
                _finding(
                    "AGENT_CONTRACT_MISSING",
                    CONTRACT_REL,
                    "canonical agent-contract.json is missing",
                )
            ]
        if not schema_path.is_file():
            return [
                _finding(
                    "AGENT_CONTRACT_SCHEMA_MISSING",
                    SCHEMA_REL,
                    "agent-contract schema is missing",
                )
            ]

        contract = load_json_strict(contract_path)
        schema = load_json_strict(schema_path)
        if not isinstance(contract, dict) or not isinstance(schema, dict):
            return [
                _finding(
                    "AGENT_CONTRACT_TYPE",
                    CONTRACT_REL,
                    "contract and schema roots must be objects",
                )
            ]

        schema_findings = validate_instance(contract, schema)
        for item in schema_findings:
            findings.append(
                _finding(
                    "AGENT_CONTRACT_SCHEMA",
                    item.get("path", "$"),
                    item.get("message", "schema violation"),
                )
            )

        findings.extend(validate_semantic_invariants(repo_root, contract))
        findings.extend(validate_projection_parity(repo_root, contract))
    except (
        OSError,
        json.JSONDecodeError,
        DuplicateKeyError,
        UnsupportedSchemaError,
        ValueError,
    ) as exc:
        findings.append(
            _finding(
                "AGENT_CONTRACT_CHECK_ERROR",
                CONTRACT_REL,
                str(exc),
            )
        )

    unique: dict[tuple[str, str, str], dict[str, str]] = {}
    for finding in findings:
        key = (finding["code"], finding["path"], finding["message"])
        unique[key] = finding
    return [unique[key] for key in sorted(unique)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate the canonical repository agent contract"
    )
    parser.add_argument(
        "--repo-root",
        default=str(REPO_ROOT),
        help="Repository root (default: detected repo root)",
    )
    args = parser.parse_args(argv)
    findings = validate_repo_agent_contract(Path(args.repo_root))
    payload = {
        "status": "valid" if not findings else "invalid",
        "contract": CONTRACT_REL,
        "schema": SCHEMA_REL,
        "findings_count": len(findings),
        "findings": findings,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
