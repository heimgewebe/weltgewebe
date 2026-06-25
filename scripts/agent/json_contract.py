#!/usr/bin/env python3
"""Strict JSON loading and deterministic validation for agent contracts.

Only the Draft-07 assertion keywords used by repository-owned agent schemas are
implemented. Unknown keywords fail closed. AJV in contract CI independently
compiles the schemas and checks the repository fixtures.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class DuplicateKeyError(ValueError):
    """Raised when a JSON object contains the same key more than once."""


class UnsupportedSchemaError(RuntimeError):
    """Raised when a contract uses an unsupported schema construct."""


ANNOTATION_KEYS = {"$schema", "$id", "title", "description", "default", "examples"}
ASSERTION_KEYS = {
    "$ref",
    "allOf",
    "type",
    "required",
    "additionalProperties",
    "properties",
    "definitions",
    "enum",
    "minLength",
    "maxLength",
    "pattern",
    "minItems",
    "uniqueItems",
    "items",
}
SUPPORTED_KEYS = ANNOTATION_KEYS | ASSERTION_KEYS
SUPPORTED_TYPES = {"object", "array", "string", "boolean", "null"}


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise json.JSONDecodeError(
        f"non-standard JSON constant: {value}",
        value,
        0,
    )


def loads_json_strict(raw: str) -> Any:
    return json.loads(
        raw,
        object_pairs_hook=_strict_object,
        parse_constant=_reject_constant,
    )


def load_json_strict(path: Path) -> Any:
    return loads_json_strict(path.read_text(encoding="utf-8"))


def _pointer(root: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise UnsupportedSchemaError(f"only local JSON pointers are supported: {ref}")
    current: Any = root
    for token in ref[2:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or token not in current:
            raise UnsupportedSchemaError(f"unresolvable schema reference: {ref}")
        current = current[token]
    if not isinstance(current, dict):
        raise UnsupportedSchemaError(
            f"schema reference does not resolve to an object: {ref}"
        )
    return current


def ensure_supported_schema(schema: Any, *, path: str = "$") -> None:
    if not isinstance(schema, dict):
        raise UnsupportedSchemaError(f"{path}: schema node must be an object")

    unknown = sorted(set(schema) - SUPPORTED_KEYS)
    if unknown:
        raise UnsupportedSchemaError(
            f"{path}: unsupported schema keyword(s): {', '.join(unknown)}"
        )

    ref = schema.get("$ref")
    if ref is not None and not isinstance(ref, str):
        raise UnsupportedSchemaError(f"{path}.$ref must be a string")

    expected_type = schema.get("type")
    if expected_type is not None and expected_type not in SUPPORTED_TYPES:
        raise UnsupportedSchemaError(f"{path}.type is unsupported: {expected_type}")

    required = schema.get("required")
    if required is not None and (
        not isinstance(required, list)
        or any(not isinstance(item, str) for item in required)
    ):
        raise UnsupportedSchemaError(f"{path}.required must be an array of strings")

    additional = schema.get("additionalProperties")
    if additional is not None and not isinstance(additional, bool):
        raise UnsupportedSchemaError(f"{path}.additionalProperties must be boolean")

    enum = schema.get("enum")
    if enum is not None and not isinstance(enum, list):
        raise UnsupportedSchemaError(f"{path}.enum must be an array")

    for keyword in ("minLength", "maxLength", "minItems"):
        value = schema.get(keyword)
        if value is not None and (
            not isinstance(value, int) or isinstance(value, bool) or value < 0
        ):
            raise UnsupportedSchemaError(
                f"{path}.{keyword} must be a non-negative integer"
            )

    pattern = schema.get("pattern")
    if pattern is not None:
        if not isinstance(pattern, str):
            raise UnsupportedSchemaError(f"{path}.pattern must be a string")
        try:
            re.compile(pattern)
        except re.error as exc:
            raise UnsupportedSchemaError(f"{path}.pattern is invalid: {exc}") from exc

    unique_items = schema.get("uniqueItems")
    if unique_items is not None and not isinstance(unique_items, bool):
        raise UnsupportedSchemaError(f"{path}.uniqueItems must be boolean")

    properties = schema.get("properties")
    if properties is not None:
        if not isinstance(properties, dict):
            raise UnsupportedSchemaError(f"{path}.properties must be an object")
        for name, child in properties.items():
            ensure_supported_schema(child, path=f"{path}.properties.{name}")

    definitions = schema.get("definitions")
    if definitions is not None:
        if not isinstance(definitions, dict):
            raise UnsupportedSchemaError(f"{path}.definitions must be an object")
        for name, child in definitions.items():
            ensure_supported_schema(child, path=f"{path}.definitions.{name}")

    items = schema.get("items")
    if items is not None:
        ensure_supported_schema(items, path=f"{path}.items")

    all_of = schema.get("allOf")
    if all_of is not None:
        if not isinstance(all_of, list):
            raise UnsupportedSchemaError(f"{path}.allOf must be an array")
        for index, child in enumerate(all_of):
            ensure_supported_schema(child, path=f"{path}.allOf[{index}]")


def _type_matches(instance: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(instance, dict)
    if expected == "array":
        return isinstance(instance, list)
    if expected == "string":
        return isinstance(instance, str)
    if expected == "boolean":
        return isinstance(instance, bool)
    if expected == "null":
        return instance is None
    raise UnsupportedSchemaError(f"unsupported schema type: {expected}")


def _canonical_item(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def validate_instance(
    instance: Any,
    schema: dict[str, Any],
    *,
    root_schema: dict[str, Any] | None = None,
    path: str = "$",
) -> list[dict[str, str]]:
    """Validate one instance and return deterministic path/message violations."""

    root = root_schema or schema
    ensure_supported_schema(schema, path=path)
    findings: list[dict[str, str]] = []

    ref = schema.get("$ref")
    if ref is not None:
        findings.extend(
            validate_instance(instance, _pointer(root, ref), root_schema=root, path=path)
        )

    for child in schema.get("allOf", []):
        findings.extend(validate_instance(instance, child, root_schema=root, path=path))

    expected_type = schema.get("type")
    if expected_type is not None and not _type_matches(instance, expected_type):
        return [{"path": path, "message": f"expected {expected_type}"}]

    enum = schema.get("enum")
    if enum is not None and instance not in enum:
        findings.append({"path": path, "message": f"value must be one of {enum}"})

    if isinstance(instance, dict):
        required = schema.get("required", [])
        for field in sorted(required):
            if field not in instance:
                findings.append(
                    {"path": f"{path}.{field}", "message": "required field is missing"}
                )

        properties = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        for key in sorted(instance):
            if key in properties:
                findings.extend(
                    validate_instance(
                        instance[key],
                        properties[key],
                        root_schema=root,
                        path=f"{path}.{key}",
                    )
                )
            elif not additional:
                findings.append({"path": f"{path}.{key}", "message": "unexpected field"})

    if isinstance(instance, list):
        min_items = schema.get("minItems")
        if min_items is not None and len(instance) < min_items:
            findings.append(
                {"path": path, "message": f"must contain at least {min_items} item(s)"}
            )

        if schema.get("uniqueItems") is True:
            seen: set[str] = set()
            for index, value in enumerate(instance):
                canonical = _canonical_item(value)
                if canonical in seen:
                    findings.append(
                        {"path": f"{path}[{index}]", "message": "duplicate array item"}
                    )
                seen.add(canonical)

        items = schema.get("items")
        if items is not None:
            for index, value in enumerate(instance):
                findings.extend(
                    validate_instance(
                        value,
                        items,
                        root_schema=root,
                        path=f"{path}[{index}]",
                    )
                )

    if isinstance(instance, str):
        min_length = schema.get("minLength")
        if min_length is not None and len(instance) < min_length:
            findings.append(
                {"path": path, "message": f"length must be at least {min_length}"}
            )

        max_length = schema.get("maxLength")
        if max_length is not None and len(instance) > max_length:
            findings.append(
                {"path": path, "message": f"length must be at most {max_length}"}
            )

        pattern = schema.get("pattern")
        if pattern is not None and re.search(pattern, instance) is None:
            findings.append(
                {"path": path, "message": f"value does not match pattern {pattern}"}
            )

    unique: dict[tuple[str, str], dict[str, str]] = {}
    for finding in findings:
        unique[(finding["path"], finding["message"])] = finding
    return [unique[key] for key in sorted(unique)]
