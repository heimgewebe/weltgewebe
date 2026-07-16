#!/usr/bin/env python3
"""Read-only adapter from a Weltgewebe profile to Assessment Request v1."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO

SCHEMA_VERSION = "1.0.0"
REQUEST_SCHEMA_VERSION = 1
PROTOCOL_HEAD = "83ed435bf9eb490e81a6ff2103b6c1397440d40b"
ADAPTER_NAME = "weltgewebe-os-convergence-adapter"
ADAPTER_VERSION = "1.0.0"

PROFILE_KEYS = {
    "schema_version",
    "profile_id",
    "protocol_head",
    "adapter",
    "evidence_mode",
    "intent",
    "request",
}
INTENT_KEYS = {
    "objective",
    "desired_state",
    "observed_state",
    "deviation",
    "decision",
    "rollback",
}
REQUEST_REQUIRED_KEYS = {
    "schema_version",
    "assessment_id",
    "risk_level",
    "observation",
    "classification",
    "effects",
    "verifications",
}
REQUEST_ALLOWED_KEYS = REQUEST_REQUIRED_KEYS | {"closure"}
OBSERVATION_KEYS = {
    "schema_version",
    "observation_id",
    "observed_at",
    "source_state",
    "source_refs",
    "claims",
    "does_not_establish",
}
SOURCE_REF_KEYS = {"kind", "ref", "subject_sha256"}
CLASSIFICATION_KEYS = {"schema_version", "change_class", "semantic_change", "blocked_by"}
EFFECT_KEYS = {"schema_version", "kind", "evidence_ref", "subject_sha256"}
VERIFICATION_KEYS = EFFECT_KEYS | {"result"}
CLOSURE_REQUIRED_KEYS = {"schema_version", "closure_id", "status", "residual_risks"}
CLOSURE_ALLOWED_KEYS = CLOSURE_REQUIRED_KEYS | {
    "bureau_task_ref",
    "chronik_event_ref",
    "cleanup_evidence",
}
CHANGE_CLASSES = {
    "documentation",
    "contract",
    "application",
    "runtime",
    "infrastructure",
    "security",
    "data",
    "lifecycle",
    "product_outcome",
}
SEMANTIC_CHANGES = {"none", "possible", "material", "unknown"}
EFFECT_KINDS = {
    "commit",
    "pull_request",
    "merge",
    "artifact",
    "deployment",
    "configuration_change",
}
VERIFICATION_KINDS = {
    "deterministic_regeneration",
    "tests",
    "review",
    "independent_review",
    "ci",
    "deployment_identity",
    "runtime_identity",
    "service_health",
    "smoke_test",
    "negative_control",
    "consumer_compatibility",
    "recovery",
    "product_outcome",
}
VERIFICATION_RESULTS = {"pass", "fail", "unknown"}
FORBIDDEN_PAYLOAD_KEYS = {
    "account",
    "bureau_task_payload",
    "chronik_history",
    "conversation",
    "domain_object",
    "domain_payload",
    "edge",
    "faden",
    "garnrolle",
    "history",
    "knoten",
    "message",
    "node",
    "payload",
    "role",
}

ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
EXACT_COMMIT_REF_RE = re.compile(r"@[0-9a-f]{40}$")


class ConvergenceAdapterError(ValueError):
    """Raised when an input profile cannot be safely converted."""


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ConvergenceAdapterError(f"duplicate JSON key {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ConvergenceAdapterError(f"unsupported JSON constant {value}")


def load_profile(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConvergenceAdapterError(f"cannot read profile {path}: {exc}") from exc
    try:
        data = json.loads(
            text,
            object_pairs_hook=_no_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except json.JSONDecodeError as exc:
        raise ConvergenceAdapterError(
            f"invalid JSON in profile {path}: {exc.msg} at line {exc.lineno} column {exc.colno}"
        ) from exc
    _assert_no_non_finite(data, "profile")
    if not isinstance(data, dict):
        raise ConvergenceAdapterError("profile root must be an object")
    return data


def canonical_json(data: Any) -> str:
    return json.dumps(
        data, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False
    )


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_request_from_path(path: Path) -> tuple[dict[str, Any], str, str]:
    return build_request(load_profile(path))


def build_request(profile: dict[str, Any]) -> tuple[dict[str, Any], str, str]:
    validate_profile(profile)
    profile_sha256 = sha256_hex(canonical_json(profile))
    request = json.loads(canonical_json(profile["request"]))
    request_sha256 = sha256_hex(canonical_json(request))
    return request, request_sha256, profile_sha256


def validate_profile(profile: dict[str, Any]) -> None:
    _assert_no_non_finite(profile, "profile")
    _assert_object_keys(profile, PROFILE_KEYS, "profile")
    _assert_no_forbidden_keys(profile, "profile")
    _assert_const(profile["schema_version"], SCHEMA_VERSION, "schema_version")
    _assert_pattern(profile["profile_id"], ID_RE, "profile_id")
    _assert_const(profile["protocol_head"], PROTOCOL_HEAD, "protocol_head")
    _assert_const(profile["adapter"], ADAPTER_NAME, "adapter")
    _validate_intent(profile["intent"])
    _validate_request(profile["request"])
    _validate_evidence_mode(profile["evidence_mode"], profile["request"])


def _validate_evidence_mode(mode: Any, request: Any) -> None:
    if mode not in {"synthetic_fixture", "live"}:
        raise ConvergenceAdapterError("evidence_mode must be synthetic_fixture or live")
    refs = list(_iter_evidence_refs(request))
    if not refs:
        raise ConvergenceAdapterError("request must contain evidence references")
    fixture_refs = [ref for ref in refs if ref.startswith("fixture:")]
    if mode == "synthetic_fixture" and len(fixture_refs) != len(refs):
        raise ConvergenceAdapterError(
            "synthetic_fixture profiles require every evidence reference to start with fixture:"
        )
    if mode == "live" and fixture_refs:
        raise ConvergenceAdapterError("live profiles must not contain fixture evidence references")


def _iter_evidence_refs(request: Any):
    if not isinstance(request, dict):
        return
    observation = request.get("observation")
    if isinstance(observation, dict):
        source_refs = observation.get("source_refs")
        if isinstance(source_refs, list):
            for item in source_refs:
                if isinstance(item, dict) and isinstance(item.get("ref"), str):
                    yield item["ref"]
    for key in ("effects", "verifications"):
        receipts = request.get(key)
        if isinstance(receipts, list):
            for item in receipts:
                if isinstance(item, dict) and isinstance(item.get("evidence_ref"), str):
                    yield item["evidence_ref"]
    closure = request.get("closure")
    if isinstance(closure, dict):
        for key in ("bureau_task_ref", "chronik_event_ref"):
            value = closure.get(key)
            if isinstance(value, str):
                yield value
        for key in ("cleanup_evidence", "residual_risks"):
            values = closure.get(key)
            if isinstance(values, list):
                for value in values:
                    if isinstance(value, str):
                        yield value


def _validate_intent(intent: Any) -> None:
    _assert_object_keys(intent, INTENT_KEYS, "intent")
    for key in sorted(INTENT_KEYS):
        _assert_string(intent[key], f"intent.{key}", min_length=16, max_length=500)


def _validate_request(request: Any) -> None:
    _assert_required_allowed_keys(
        request, REQUEST_REQUIRED_KEYS, REQUEST_ALLOWED_KEYS, "request"
    )
    _assert_schema_version_one(request["schema_version"], "request.schema_version")
    _assert_string(request["assessment_id"], "request.assessment_id", max_length=200)
    if request["risk_level"] not in {"R0", "R1", "R2", "R3"}:
        raise ConvergenceAdapterError("request.risk_level must be R0, R1, R2 or R3")

    source_refs = _validate_observation(request["observation"])
    _validate_classification(request["classification"])
    effects = _validate_effects(request["effects"])
    verifications = _validate_verifications(request["verifications"])

    _require_source_ref_kinds(
        source_refs, {"bureau_task", "chronik_event", "grabowski_live_receipt"}
    )
    if not any(_is_exact_revision_ref(item) for item in source_refs):
        raise ConvergenceAdapterError(
            "request.observation.source_refs must include an exact Weltgewebe commit or deploy receipt"
        )
    if request["risk_level"] == "R2":
        _require_receipt_kind(effects, "merge", "request.effects")
        _require_receipt_kind(effects, "deployment", "request.effects")
    _require_pass_verification(verifications, "negative_control")
    _require_pass_verification(verifications, "recovery")

    closure = request.get("closure")
    if closure is None:
        raise ConvergenceAdapterError("request.closure must be present for rollback evidence")
    _validate_closure(closure)


def _validate_observation(observation: Any) -> list[dict[str, Any]]:
    _assert_object_keys(observation, OBSERVATION_KEYS, "request.observation")
    _assert_schema_version_one(
        observation["schema_version"], "request.observation.schema_version"
    )
    _assert_string(
        observation["observation_id"], "request.observation.observation_id", max_length=200
    )
    _assert_datetime(observation["observed_at"], "request.observation.observed_at")
    if observation["source_state"] not in {"current", "stale", "unknown"}:
        raise ConvergenceAdapterError(
            "request.observation.source_state must be current, stale or unknown"
        )

    raw_refs = observation["source_refs"]
    if not isinstance(raw_refs, list):
        raise ConvergenceAdapterError("request.observation.source_refs must be an array")
    if not 1 <= len(raw_refs) <= 32:
        raise ConvergenceAdapterError(
            "request.observation.source_refs must contain between 1 and 32 items"
        )
    source_refs: list[dict[str, Any]] = []
    for index, item in enumerate(raw_refs):
        path = f"request.observation.source_refs[{index}]"
        _assert_object_keys(item, SOURCE_REF_KEYS, path)
        _assert_string(item["kind"], f"{path}.kind", max_length=80)
        _assert_string(item["ref"], f"{path}.ref", max_length=2048)
        _assert_pattern(item["subject_sha256"], SHA256_RE, f"{path}.subject_sha256")
        _reject_symbolic_git_reference(item["kind"], item["ref"], path)
        source_refs.append(item)

    _assert_string_list(
        observation["claims"],
        "request.observation.claims",
        min_items=1,
        max_items=64,
        max_length=500,
    )
    _assert_string_list(
        observation["does_not_establish"],
        "request.observation.does_not_establish",
        min_items=0,
        max_items=64,
        max_length=200,
        unique=True,
    )
    return source_refs


def _reject_symbolic_git_reference(kind: str, ref: str, path: str) -> None:
    normalized_kind = kind.casefold()
    git_shaped = normalized_kind.startswith("git") or "git:" in ref.casefold()
    if git_shaped and EXACT_COMMIT_REF_RE.search(ref) is None:
        raise ConvergenceAdapterError(
            f"{path}.ref must bind a git reference to an exact 40-character commit"
        )


def _validate_classification(classification: Any) -> None:
    _assert_object_keys(classification, CLASSIFICATION_KEYS, "request.classification")
    _assert_schema_version_one(
        classification["schema_version"], "request.classification.schema_version"
    )
    if classification["change_class"] not in CHANGE_CLASSES:
        raise ConvergenceAdapterError("request.classification.change_class is invalid")
    if classification["semantic_change"] not in SEMANTIC_CHANGES:
        raise ConvergenceAdapterError("request.classification.semantic_change is invalid")
    _assert_string_list(
        classification["blocked_by"],
        "request.classification.blocked_by",
        min_items=0,
        max_items=64,
        max_length=300,
        unique=True,
    )


def _validate_effects(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ConvergenceAdapterError("request.effects must be an array")
    if len(value) > 64:
        raise ConvergenceAdapterError("request.effects must contain at most 64 items")
    receipts: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        path = f"request.effects[{index}]"
        _assert_object_keys(item, EFFECT_KEYS, path)
        _assert_schema_version_one(item["schema_version"], f"{path}.schema_version")
        if item["kind"] not in EFFECT_KINDS:
            raise ConvergenceAdapterError(f"{path}.kind is invalid")
        _assert_string(item["evidence_ref"], f"{path}.evidence_ref", max_length=2048)
        _assert_pattern(item["subject_sha256"], SHA256_RE, f"{path}.subject_sha256")
        receipts.append(item)
    return receipts


def _validate_verifications(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ConvergenceAdapterError("request.verifications must be an array")
    if len(value) > 128:
        raise ConvergenceAdapterError("request.verifications must contain at most 128 items")
    receipts: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        path = f"request.verifications[{index}]"
        _assert_object_keys(item, VERIFICATION_KEYS, path)
        _assert_schema_version_one(item["schema_version"], f"{path}.schema_version")
        if item["kind"] not in VERIFICATION_KINDS:
            raise ConvergenceAdapterError(f"{path}.kind is invalid")
        _assert_string(item["evidence_ref"], f"{path}.evidence_ref", max_length=2048)
        _assert_pattern(item["subject_sha256"], SHA256_RE, f"{path}.subject_sha256")
        if item["result"] not in VERIFICATION_RESULTS:
            raise ConvergenceAdapterError(f"{path}.result is invalid")
        receipts.append(item)
    return receipts


def _validate_closure(closure: Any) -> None:
    _assert_required_allowed_keys(
        closure, CLOSURE_REQUIRED_KEYS, CLOSURE_ALLOWED_KEYS, "request.closure"
    )
    _assert_schema_version_one(closure["schema_version"], "request.closure.schema_version")
    _assert_string(closure["closure_id"], "request.closure.closure_id", max_length=200)
    if closure["status"] not in {"proposed", "closed"}:
        raise ConvergenceAdapterError("request.closure.status must be proposed or closed")
    for key in ("bureau_task_ref", "chronik_event_ref"):
        if key not in closure:
            raise ConvergenceAdapterError(f"request.closure.{key} must be present")
        _assert_string(closure[key], f"request.closure.{key}", max_length=500)
    if "cleanup_evidence" not in closure:
        raise ConvergenceAdapterError("request.closure.cleanup_evidence must be present")
    _assert_string_list(
        closure["cleanup_evidence"],
        "request.closure.cleanup_evidence",
        min_items=1,
        max_items=64,
        max_length=2048,
        unique=True,
    )
    _assert_string_list(
        closure["residual_risks"],
        "request.closure.residual_risks",
        min_items=1,
        max_items=64,
        max_length=500,
        unique=True,
    )


def _require_source_ref_kinds(
    source_refs: list[dict[str, Any]], required: set[str]
) -> None:
    kinds = {item["kind"] for item in source_refs}
    missing = required - kinds
    if missing:
        raise ConvergenceAdapterError(
            f"request.observation.source_refs missing {', '.join(sorted(missing))}"
        )


def _is_exact_revision_ref(source_ref: Any) -> bool:
    if not isinstance(source_ref, dict):
        return False
    kind = source_ref.get("kind")
    ref = source_ref.get("ref")
    if not isinstance(ref, str):
        return False
    return (
        kind == "weltgewebe_deploy_receipt"
        or kind == "git_commit"
        and EXACT_COMMIT_REF_RE.search(ref) is not None
    )


def _require_receipt_kind(receipts: list[dict[str, Any]], kind: str, path: str) -> None:
    if not any(item["kind"] == kind for item in receipts):
        raise ConvergenceAdapterError(f"{path} missing {kind}")


def _require_pass_verification(verifications: list[dict[str, Any]], kind: str) -> None:
    for item in verifications:
        if item["kind"] == kind and item["result"] == "pass":
            return
    raise ConvergenceAdapterError(f"request.verifications missing passing {kind}")


def _assert_required_allowed_keys(
    value: Any, required: set[str], allowed: set[str], path: str
) -> None:
    if not isinstance(value, dict):
        raise ConvergenceAdapterError(f"{path} must be an object")
    missing = required - set(value)
    if missing:
        raise ConvergenceAdapterError(f"{path} missing required keys {', '.join(sorted(missing))}")
    unknown = set(value) - allowed
    if unknown:
        raise ConvergenceAdapterError(f"{path} has unexpected keys {', '.join(sorted(unknown))}")


def _assert_schema_version_one(value: Any, path: str) -> None:
    if type(value) is not int or value != REQUEST_SCHEMA_VERSION:
        raise ConvergenceAdapterError(f"{path} must be integer 1")


def _assert_datetime(value: Any, path: str) -> None:
    _assert_string(value, path, max_length=64)
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ConvergenceAdapterError(f"{path} must be an RFC 3339 date-time") from exc
    if parsed.tzinfo is None:
        raise ConvergenceAdapterError(f"{path} must include a timezone")


def _assert_string_list(
    value: Any,
    path: str,
    *,
    min_items: int,
    max_items: int,
    max_length: int,
    unique: bool = False,
) -> None:
    if not isinstance(value, list):
        raise ConvergenceAdapterError(f"{path} must be an array")
    if not min_items <= len(value) <= max_items:
        raise ConvergenceAdapterError(
            f"{path} must contain between {min_items} and {max_items} items"
        )
    for index, item in enumerate(value):
        _assert_string(item, f"{path}[{index}]", max_length=max_length)
    if unique and len(set(value)) != len(value):
        raise ConvergenceAdapterError(f"{path} must contain unique items")


def _assert_object_keys(value: Any, allowed: set[str], path: str) -> None:
    if not isinstance(value, dict):
        raise ConvergenceAdapterError(f"{path} must be an object")
    missing = allowed - set(value)
    if missing:
        raise ConvergenceAdapterError(f"{path} missing required keys {', '.join(sorted(missing))}")
    unknown = set(value) - allowed
    if unknown:
        raise ConvergenceAdapterError(f"{path} has unexpected keys {', '.join(sorted(unknown))}")


def _assert_const(value: Any, expected: str, path: str) -> None:
    if value != expected:
        raise ConvergenceAdapterError(f"{path} must be {expected}")


def _assert_pattern(value: Any, pattern: re.Pattern[str], path: str) -> None:
    _assert_string(value, path)
    if not pattern.fullmatch(value):
        raise ConvergenceAdapterError(f"{path} has invalid format")


def _assert_string(
    value: Any,
    path: str,
    *,
    min_length: int = 1,
    max_length: int = 2048,
) -> None:
    if not isinstance(value, str):
        raise ConvergenceAdapterError(f"{path} must be a string")
    if len(value) < min_length or len(value) > max_length:
        raise ConvergenceAdapterError(
            f"{path} length must be between {min_length} and {max_length}"
        )
    if any(char in value for char in ("\r", "\n", "\t")):
        raise ConvergenceAdapterError(f"{path} must be a single-line string")


def _assert_no_forbidden_keys(value: Any, path: str) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_PAYLOAD_KEYS:
                raise ConvergenceAdapterError(f"{path}.{key} is forbidden")
            _assert_no_forbidden_keys(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_forbidden_keys(child, f"{path}[{index}]")


def _assert_no_non_finite(value: Any, path: str) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ConvergenceAdapterError(f"{path} contains a non-finite number")
    if isinstance(value, dict):
        for key, child in value.items():
            _assert_no_non_finite(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_non_finite(child, f"{path}[{index}]")


def render_output(
    profile: dict[str, Any],
    request: dict[str, Any],
    request_sha256: str,
    profile_sha256: str,
    output: str,
) -> str:
    if output == "request":
        return canonical_json(request)
    if output == "hash":
        return request_sha256
    envelope = {
        "schema_version": SCHEMA_VERSION,
        "adapter": ADAPTER_NAME,
        "adapter_version": ADAPTER_VERSION,
        "profile_id": profile["profile_id"],
        "evidence_mode": profile["evidence_mode"],
        "profile_sha256": profile_sha256,
        "protocol_head": PROTOCOL_HEAD,
        "request": request,
        "request_sha256": request_sha256,
    }
    return canonical_json(envelope)


def main(
    argv: list[str] | None = None,
    *,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    parser = argparse.ArgumentParser(
        description="Build a public Assessment Request v1 from a Weltgewebe profile."
    )
    parser.add_argument("profile", help="Path to a convergence assessment profile JSON file")
    parser.add_argument(
        "--output",
        choices=("envelope", "request", "hash"),
        default="envelope",
        help="Output the default adapter envelope, only the public request JSON, or only the hash.",
    )
    args = parser.parse_args(argv)
    try:
        profile = load_profile(Path(args.profile))
        request, request_sha256, profile_sha256 = build_request(profile)
        stdout.write(render_output(profile, request, request_sha256, profile_sha256, args.output))
        stdout.write("\n")
        return 0
    except ConvergenceAdapterError as exc:
        stderr.write(f"convergence adapter error: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
