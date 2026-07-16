#!/usr/bin/env python3
"""Read-only adapter from a Weltgewebe profile to Assessment Request v1."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
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
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


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
    _assert_object_keys(profile, PROFILE_KEYS, "profile")
    _assert_no_forbidden_keys(profile, "profile")
    _assert_const(profile["schema_version"], SCHEMA_VERSION, "schema_version")
    _assert_pattern(profile["profile_id"], ID_RE, "profile_id")
    _assert_const(profile["protocol_head"], PROTOCOL_HEAD, "protocol_head")
    _assert_const(profile["adapter"], ADAPTER_NAME, "adapter")
    _validate_evidence_mode(profile["evidence_mode"], profile["request"])
    _validate_intent(profile["intent"])
    _validate_request(profile["request"])


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
    if not isinstance(request, dict):
        raise ConvergenceAdapterError("request must be an object")
    missing = REQUEST_REQUIRED_KEYS - set(request)
    if missing:
        raise ConvergenceAdapterError(
            f"request missing required keys {', '.join(sorted(missing))}"
        )
    unknown = set(request) - REQUEST_ALLOWED_KEYS
    if unknown:
        raise ConvergenceAdapterError(
            f"request has unexpected keys {', '.join(sorted(unknown))}"
        )
    if request["schema_version"] != REQUEST_SCHEMA_VERSION:
        raise ConvergenceAdapterError("request.schema_version must be 1")
    if request["risk_level"] not in {"R0", "R1", "R2", "R3"}:
        raise ConvergenceAdapterError("request.risk_level must be R0, R1, R2 or R3")

    observation = request["observation"]
    if not isinstance(observation, dict):
        raise ConvergenceAdapterError("request.observation must be an object")
    source_refs = observation.get("source_refs")
    if not isinstance(source_refs, list):
        raise ConvergenceAdapterError("request.observation.source_refs must be an array")
    _require_source_ref_kinds(
        source_refs,
        {"bureau_task", "chronik_event", "grabowski_live_receipt"},
    )
    if not any(_is_exact_revision_ref(item) for item in source_refs):
        raise ConvergenceAdapterError(
            "request.observation.source_refs must include an exact Weltgewebe commit or deploy receipt"
        )

    effects = _assert_receipt_list(request["effects"], "request.effects")
    verifications = _assert_receipt_list(
        request["verifications"],
        "request.verifications",
    )
    if request["risk_level"] == "R2":
        _require_receipt_kind(effects, "merge", "request.effects")
        _require_receipt_kind(effects, "deployment", "request.effects")
    _require_pass_verification(verifications, "negative_control")
    _require_pass_verification(verifications, "recovery")

    closure = request.get("closure")
    if not isinstance(closure, dict):
        raise ConvergenceAdapterError("request.closure must be present for rollback evidence")
    for key in ("bureau_task_ref", "chronik_event_ref", "cleanup_evidence", "residual_risks"):
        if not closure.get(key):
            raise ConvergenceAdapterError(f"request.closure.{key} must be present")


def _require_source_ref_kinds(source_refs: list[Any], required: set[str]) -> None:
    kinds: set[str] = set()
    for index, item in enumerate(source_refs):
        if not isinstance(item, dict):
            raise ConvergenceAdapterError(f"request.observation.source_refs[{index}] must be an object")
        for key in ("kind", "ref", "subject_sha256"):
            if key not in item:
                raise ConvergenceAdapterError(
                    f"request.observation.source_refs[{index}] missing {key}"
                )
        _assert_string(item["kind"], f"request.observation.source_refs[{index}].kind")
        _assert_string(item["ref"], f"request.observation.source_refs[{index}].ref")
        _assert_pattern(
            item["subject_sha256"],
            SHA256_RE,
            f"request.observation.source_refs[{index}].subject_sha256",
        )
        kinds.add(item["kind"])
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


def _assert_receipt_list(value: Any, path: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ConvergenceAdapterError(f"{path} must be an array")
    receipts: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ConvergenceAdapterError(f"{path}[{index}] must be an object")
        for key in ("schema_version", "kind", "evidence_ref", "subject_sha256"):
            if key not in item:
                raise ConvergenceAdapterError(f"{path}[{index}] missing {key}")
        if item["schema_version"] != REQUEST_SCHEMA_VERSION:
            raise ConvergenceAdapterError(f"{path}[{index}].schema_version must be 1")
        _assert_string(item["kind"], f"{path}[{index}].kind")
        _assert_string(item["evidence_ref"], f"{path}[{index}].evidence_ref")
        _assert_pattern(item["subject_sha256"], SHA256_RE, f"{path}[{index}].subject_sha256")
        receipts.append(item)
    return receipts


def _require_receipt_kind(receipts: list[dict[str, Any]], kind: str, path: str) -> None:
    if not any(item["kind"] == kind for item in receipts):
        raise ConvergenceAdapterError(f"{path} missing {kind}")


def _require_pass_verification(verifications: list[dict[str, Any]], kind: str) -> None:
    for item in verifications:
        if item["kind"] == kind and item.get("result") == "pass":
            return
    raise ConvergenceAdapterError(f"request.verifications missing passing {kind}")


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
