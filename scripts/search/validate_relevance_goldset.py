"""Validate the Semantic Search v1 relevance goldset without external dependencies."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA = ROOT / "contracts/search/relevance-goldset.schema.json"
DEFAULT_DATASET = ROOT / "contracts/search/examples/relevance-goldset.example.json"
EMAIL_LIKE = re.compile(r"(?i)\b[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)+\b")
PHONE_LIKE = re.compile(r"(?<![\w-])(?:\+49|0049|0[1-9]\d{1,4})(?:[ /-]?\d){6,14}(?![\w-])")
IPV4_LIKE = re.compile(r"(?<![\d.])(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}(?![\d.])")


class ValidationError(ValueError):
    """Raised when schema or cross-field invariants are violated."""


def _join(path: str, child: str | int) -> str:
    return f"{path}[{child}]" if isinstance(child, int) else f"{path}.{child}"


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    raise ValidationError(f"unsupported schema type: {expected}")


def validate_schema_subset(instance: Any, schema: dict[str, Any], path: str = "$") -> None:
    """Validate the JSON-Schema draft-07 subset used by the checked-in contract."""

    if "const" in schema and instance != schema["const"]:
        raise ValidationError(f"{path}: expected constant {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        raise ValidationError(f"{path}: value {instance!r} is not in {schema['enum']!r}")

    expected = schema.get("type")
    if expected is not None:
        allowed = [expected] if isinstance(expected, str) else expected
        if not any(_matches_type(instance, item) for item in allowed):
            raise ValidationError(f"{path}: expected type {allowed!r}")

    if isinstance(instance, dict):
        properties = schema.get("properties", {})
        missing = [key for key in schema.get("required", []) if key not in instance]
        if missing:
            raise ValidationError(f"{path}: missing required properties {missing!r}")
        if schema.get("additionalProperties") is False:
            extra = sorted(set(instance) - set(properties))
            if extra:
                raise ValidationError(f"{path}: unexpected properties {extra!r}")
        for key, value in instance.items():
            child_schema = properties.get(key)
            if child_schema is not None:
                validate_schema_subset(value, child_schema, _join(path, key))

    if isinstance(instance, list):
        minimum = schema.get("minItems")
        maximum = schema.get("maxItems")
        if minimum is not None and len(instance) < minimum:
            raise ValidationError(f"{path}: requires at least {minimum} items")
        if maximum is not None and len(instance) > maximum:
            raise ValidationError(f"{path}: permits at most {maximum} items")
        if schema.get("uniqueItems"):
            values = [_canonical(item) for item in instance]
            if len(values) != len(set(values)):
                raise ValidationError(f"{path}: duplicate array items are forbidden")
        item_schema = schema.get("items")
        if item_schema is not None:
            for index, value in enumerate(instance):
                validate_schema_subset(value, item_schema, _join(path, index))

    if isinstance(instance, str):
        minimum = schema.get("minLength")
        maximum = schema.get("maxLength")
        if minimum is not None and len(instance) < minimum:
            raise ValidationError(f"{path}: requires at least {minimum} characters")
        if maximum is not None and len(instance) > maximum:
            raise ValidationError(f"{path}: permits at most {maximum} characters")
        pattern = schema.get("pattern")
        if pattern is not None and re.fullmatch(pattern, instance) is None:
            raise ValidationError(f"{path}: does not match pattern {pattern!r}")


def _walk_strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _walk_strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _walk_strings(item)


def _matches_filters(node: dict[str, Any], filters: dict[str, list[str]]) -> bool:
    kinds = set(filters["kinds"])
    tags = set(filters["tags"])
    languages = set(filters["languages"])
    return (
        (not kinds or node["kind"] in kinds)
        and (not tags or bool(tags.intersection(node["tags"])))
        and (not languages or node["language"] in languages)
    )


def validate_goldset(dataset: dict[str, Any], schema: dict[str, Any]) -> None:
    """Apply schema, referential, visibility and privacy invariants."""

    validate_schema_subset(dataset, schema)
    node_by_id: dict[str, dict[str, Any]] = {}
    for index, node in enumerate(dataset["nodes"]):
        node_id = node["id"]
        if node_id in node_by_id:
            raise ValidationError(f"$.nodes[{index}].id: duplicate node id {node_id!r}")
        node_by_id[node_id] = node

    case_ids: set[str] = set()
    natural_case_count = 0
    expected_rank_classes: set[str] = set()
    for index, case in enumerate(dataset["cases"]):
        case_path = f"$.cases[{index}]"
        case_id = case["id"]
        if case_id in case_ids:
            raise ValidationError(f"{case_path}.id: duplicate case id {case_id!r}")
        case_ids.add(case_id)
        natural_case_count += int(case["natural_language"])
        expected_rank_classes.add(case["expected_rank_class"])

        context = case["visibility_context"]
        visible = set(context["visible_node_ids"])
        relevant = set(case["relevant_node_ids"])
        excluded = set(case["excluded_node_ids"])
        referenced = visible | relevant | excluded
        unknown = sorted(referenced - set(node_by_id))
        if unknown:
            raise ValidationError(f"{case_path}: references unknown nodes: {unknown!r}")

        missing = sorted(relevant - visible)
        if missing:
            raise ValidationError(f"{case_path}.relevant_node_ids: relevant nodes are not visible: {missing!r}")
        visible_excluded = sorted(excluded & visible)
        if visible_excluded:
            raise ValidationError(f"{case_path}.excluded_node_ids: excluded nodes are visible: {visible_excluded!r}")
        overlap = sorted(relevant & excluded)
        if overlap:
            raise ValidationError(f"{case_path}: nodes cannot be both relevant and excluded: {overlap!r}")

        for node_id in sorted(visible):
            node = node_by_id[node_id]
            if node["status"] != "active":
                raise ValidationError(f"{case_path}: visible node {node_id!r} is not active")
            if context["viewer_scope"] not in node["visibility_scopes"]:
                raise ValidationError(f"{case_path}: visible node {node_id!r} is outside viewer scope")
            if not _matches_filters(node, context["active_filters"]):
                raise ValidationError(f"{case_path}: visible node {node_id!r} violates active filters")

    if natural_case_count == 0:
        raise ValidationError("goldset requires at least one natural-language case")
    required_rank_classes = {"exact_title", "exact_tag", "title_prefix", "typo", "full_text", "semantic"}
    missing_rank_classes = sorted(required_rank_classes - expected_rank_classes)
    if missing_rank_classes:
        raise ValidationError(f"goldset is missing required rank classes: {missing_rank_classes!r}")

    for text in _walk_strings(dataset):
        if EMAIL_LIKE.search(text):
            raise ValidationError("goldset contains an email-like value")
        if PHONE_LIKE.search(text):
            raise ValidationError("goldset contains a phone-like value")
        if IPV4_LIKE.search(text):
            raise ValidationError("goldset contains an IPv4-like value")


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValidationError(f"{path}: cannot load JSON: {error}") from error
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: top-level JSON value must be an object")
    return value


def validate_files(schema_path: Path, dataset_path: Path) -> None:
    schema = load_json_object(schema_path)
    if schema.get("$schema") != "http://json-schema.org/draft-07/schema#":
        raise ValidationError(f"{schema_path}: expected JSON Schema draft-07")
    validate_goldset(load_json_object(dataset_path), schema)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate a Weltgewebe Semantic Search relevance goldset.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        validate_files(args.schema, args.dataset)
    except ValidationError as error:
        print(f"semantic-search goldset invalid: {error}", file=sys.stderr)
        return 1
    print(f"semantic-search goldset valid: schema={args.schema} dataset={args.dataset}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
