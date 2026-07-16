#!/usr/bin/env python3
"""Read-only adapter from a Weltgewebe profile to Assessment Request v1."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO, Iterator

SCHEMA_VERSION = "1.0.0"
REQUEST_SCHEMA_VERSION = 1
PROTOCOL_HEAD_FILE = Path(__file__).resolve().parents[2] / "contracts" / "convergence" / "v1.0.0" / "PINNED_PROTOCOL_HEAD"
PROTOCOL_HEAD = PROTOCOL_HEAD_FILE.read_text(encoding="utf-8").strip()
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
CLOSURE_PROTOCOL_REQUIRED_KEYS = {
    "schema_version",
    "closure_id",
    "status",
    "residual_risks",
}
R2_REQUIRED_EFFECT_KINDS = {"merge", "deployment"}
R2_REQUIRED_VERIFICATION_KINDS = {
    "tests",
    "review",
    "ci",
    "deployment_identity",
    "runtime_identity",
    "service_health",
    "smoke_test",
    "negative_control",
}
R2_REQUIRED_CLOSURE_FIELDS = {
    "bureau_task_ref",
    "chronik_event_ref",
    "cleanup_evidence",
}
ADAPTER_REQUIRED_VERIFICATION_KINDS = {"recovery"}
CLOSURE_REQUIRED_KEYS = CLOSURE_PROTOCOL_REQUIRED_KEYS | R2_REQUIRED_CLOSURE_FIELDS
CLOSURE_ALLOWED_KEYS = CLOSURE_REQUIRED_KEYS
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
GIT_REFERENCE_MARKER_RE = re.compile(
    r"(?:^|:)git(?:[-_][a-z0-9]+)*:", re.IGNORECASE
)
GIT_HOST_RE = re.compile(
    r"(?:github\.com|gitlab\.com|bitbucket\.org|raw\.githubusercontent\.com|codeload\.github\.com)",
    re.IGNORECASE,
)
GIT_REVISION_PATH_RE = re.compile(
    r"(?:github\.com|gitlab\.com|bitbucket\.org)/[^/\s]+/[^/\s]+/"
    r"(?:-/(?:tree|blob|raw|commit|commits|archive)|tree|blob|raw|commit|commits|src|releases/tag|tags)/"
    r"(?P<revision>[^/?#\s]+)",
    re.IGNORECASE,
)
GITLAB_REVISION_PATH_RE = re.compile(
    r"gitlab\.com/(?:[^/\s]+/)+[^/\s]+/-/"
    r"(?:tree|blob|raw|commit|commits|archive|tags|releases)/"
    r"(?P<revision>[^/?#\s]+)",
    re.IGNORECASE,
)
RAW_GITHUB_REVISION_RE = re.compile(
    r"raw\.githubusercontent\.com/[^/\s]+/[^/\s]+/(?P<revision>[^/?#\s]+)",
    re.IGNORECASE,
)
CODELOAD_GITHUB_REVISION_RE = re.compile(
    r"codeload\.github\.com/[^/\s]+/[^/\s]+/(?:zip|tar\.gz)/"
    r"(?P<revision>[^/?#\s]+)",
    re.IGNORECASE,
)
GITHUB_ARCHIVE_REVISION_RE = re.compile(
    r"github\.com/[^/\s]+/[^/\s]+/archive/"
    r"(?P<revision>[^/?#\s]+?)(?:\.zip|\.tar\.gz)?(?:$|[?#])",
    re.IGNORECASE,
)
GIT_COMPARE_RE = re.compile(
    r"(?:github\.com|gitlab\.com|bitbucket\.org)/[^/\s]+/[^/\s]+/compare/"
    r"(?P<left>[^/?#\s]+?)\.{2,3}(?P<right>[^/?#\s]+)",
    re.IGNORECASE,
)
GITLAB_COMPARE_RE = re.compile(
    r"gitlab\.com/(?:[^/\s]+/)+[^/\s]+/-/compare/"
    r"(?P<left>[^/?#\s]+?)\.{2,3}(?P<right>[^/?#\s]+)",
    re.IGNORECASE,
)
GIT_QUERY_REVISION_RE = re.compile(
    r"[?&](?:ref|at)=(?P<revision>[^&#\s]+)", re.IGNORECASE
)
GIT_FRAGMENT_REVISION_RE = re.compile(
    r"\.git#(?P<revision>[^#\s]+)", re.IGNORECASE
)
EXPLICIT_SYMBOLIC_GIT_REF_RE = re.compile(
    r"(?:^|[/:])refs/(?:heads|tags)/", re.IGNORECASE
)
RFC3339_DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})$"
)
GITHUB_PR_RE = re.compile(
    r"github\.com/[^/\s]+/[^/\s]+/pull/\d+$", re.IGNORECASE
)
GITLAB_MR_RE = re.compile(
    r"gitlab\.com/(?:[^/\s]+/)+[^/\s]+/-/merge_requests/\d+$", re.IGNORECASE
)


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
    if path.is_symlink():
        # Rejecting symlinks reduces local path confusion; it is not a general host filesystem security mechanism.
        raise ConvergenceAdapterError(f"profile path {path} must not be a symlink")
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ConvergenceAdapterError(f"profile {path} is not valid UTF-8: {exc}") from exc
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
    profile_json = canonical_json(profile)
    # Return value should be isolated from the input profile
    request = copy.deepcopy(profile["request"])
    request_json = canonical_json(request)
    profile_sha256 = sha256_hex(profile_json)
    request_sha256 = sha256_hex(request_json)
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


def _iter_evidence_refs(request: Any) -> Iterator[str]:
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
        _assert_string(intent[key], f"intent.{key}", min_length=8, max_length=500)


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
        _require_receipt_kinds(effects, R2_REQUIRED_EFFECT_KINDS, "request.effects")
        _require_pass_verifications(verifications, R2_REQUIRED_VERIFICATION_KINDS)
    _require_pass_verifications(verifications, ADAPTER_REQUIRED_VERIFICATION_KINDS)

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
        _reject_symbolic_git_reference(item["ref"], path, kind=item["kind"])
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


def _reject_symbolic_git_reference(
    ref: str, path: str, *, kind: str = ""
) -> None:
    if "github.com" in ref.casefold() and "/pull/" in ref.casefold():
        if GITHUB_PR_RE.search(ref) is None:
            raise ConvergenceAdapterError(f"{path} must be an exact GitHub PR URL without subpaths")
        return

    if "gitlab.com" in ref.casefold() and "/-/merge_requests/" in ref.casefold():
        if GITLAB_MR_RE.search(ref) is None:
            raise ConvergenceAdapterError(f"{path} must be an exact GitLab MR URL without subpaths")
        return

    if EXPLICIT_SYMBOLIC_GIT_REF_RE.search(ref) is not None:
        raise ConvergenceAdapterError(
            f"{path} must not contain refs/heads or refs/tags references"
        )

    revision_match = GIT_REVISION_PATH_RE.search(ref)
    if revision_match is not None:
        _assert_exact_git_revision(revision_match.group("revision"), path)

    gitlab_revision_match = GITLAB_REVISION_PATH_RE.search(ref)
    if gitlab_revision_match is not None:
        _assert_exact_git_revision(gitlab_revision_match.group("revision"), path)

    raw_match = RAW_GITHUB_REVISION_RE.search(ref)
    if raw_match is not None:
        _assert_exact_git_revision(raw_match.group("revision"), path)

    codeload_match = CODELOAD_GITHUB_REVISION_RE.search(ref)
    if codeload_match is not None:
        _assert_exact_git_revision(codeload_match.group("revision"), path)

    archive_match = GITHUB_ARCHIVE_REVISION_RE.search(ref)
    if archive_match is not None:
        _assert_exact_git_revision(archive_match.group("revision"), path)

    compare_match = GIT_COMPARE_RE.search(ref)
    if compare_match is not None:
        _assert_exact_git_revision(compare_match.group("left"), path)
        _assert_exact_git_revision(compare_match.group("right"), path)

    gitlab_compare_match = GITLAB_COMPARE_RE.search(ref)
    if gitlab_compare_match is not None:
        _assert_exact_git_revision(gitlab_compare_match.group("left"), path)
        _assert_exact_git_revision(gitlab_compare_match.group("right"), path)

    if GIT_HOST_RE.search(ref) is not None or ".git" in ref.casefold():
        query_match = GIT_QUERY_REVISION_RE.search(ref)
        if query_match is not None:
            _assert_exact_git_revision(query_match.group("revision"), path)

    fragment_match = GIT_FRAGMENT_REVISION_RE.search(ref)
    if fragment_match is not None:
        _assert_exact_git_revision(fragment_match.group("revision"), path)

    normalized_kind = kind.casefold()
    shorthand_git_ref = (
        normalized_kind.startswith("git")
        or GIT_REFERENCE_MARKER_RE.search(ref) is not None
    )
    url_revision_bound = any(
        match is not None
        for match in (
            revision_match,
            gitlab_revision_match,
            raw_match,
            codeload_match,
            archive_match,
            compare_match,
            gitlab_compare_match,
        )
    )
    if (
        shorthand_git_ref
        and EXACT_COMMIT_REF_RE.search(ref) is None
        and not url_revision_bound
    ):
        raise ConvergenceAdapterError(
            f"{path} must bind a git reference to an exact 40-character commit"
        )


def _assert_exact_git_revision(revision: str, path: str) -> None:
    if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise ConvergenceAdapterError(
            f"{path} must bind a git URL or query to an exact 40-character commit"
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
        _reject_symbolic_git_reference(item["evidence_ref"], f"{path}.evidence_ref")
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
        _reject_symbolic_git_reference(item["evidence_ref"], f"{path}.evidence_ref")
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
        path = f"request.closure.{key}"
        _assert_string(closure[key], path, max_length=500)
        _reject_symbolic_git_reference(closure[key], path)
    _assert_string_list(
        closure["cleanup_evidence"],
        "request.closure.cleanup_evidence",
        min_items=1,
        max_items=64,
        max_length=2048,
        unique=True,
    )
    _reject_symbolic_git_reference_list(
        closure["cleanup_evidence"], "request.closure.cleanup_evidence"
    )
    _assert_string_list(
        closure["residual_risks"],
        "request.closure.residual_risks",
        min_items=1,
        max_items=64,
        max_length=500,
        unique=True,
    )
    _reject_symbolic_git_reference_list(
        closure["residual_risks"], "request.closure.residual_risks"
    )


def _reject_symbolic_git_reference_list(values: list[str], path: str) -> None:
    for index, value in enumerate(values):
        _reject_symbolic_git_reference(value, f"{path}[{index}]")


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
        or (kind == "git_commit" and EXACT_COMMIT_REF_RE.search(ref) is not None)
    )


def _require_receipt_kinds(
    receipts: list[dict[str, Any]], required_kinds: set[str], path: str
) -> None:
    present = {item["kind"] for item in receipts}
    missing = required_kinds - present
    if missing:
        raise ConvergenceAdapterError(
            f"{path} missing required kinds {', '.join(sorted(missing))}"
        )


def _require_pass_verifications(
    verifications: list[dict[str, Any]], required_kinds: set[str]
) -> None:
    passing = {item["kind"] for item in verifications if item["result"] == "pass"}
    missing = required_kinds - passing
    if missing:
        raise ConvergenceAdapterError(
            "request.verifications missing passing " + ", ".join(sorted(missing))
        )


def _assert_required_allowed_keys(
    value: Any, required: set[str], allowed: set[str], path: str
) -> None:
    if not isinstance(value, dict):
        raise ConvergenceAdapterError(f"{path} must be an object")
    _assert_string_keys(value, path)
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
    # The regex provides strict shape validation, while fromisoformat provides semantic validation
    if RFC3339_DATETIME_RE.fullmatch(value) is None:
        raise ConvergenceAdapterError(f"{path} must be an RFC 3339 date-time")
    normalized = value.replace("t", "T")
    if normalized.endswith(("Z", "z")):
        normalized = normalized[:-1] + "+00:00"
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
    _assert_string_keys(value, path)
    missing = allowed - set(value)
    if missing:
        raise ConvergenceAdapterError(f"{path} missing required keys {', '.join(sorted(missing))}")
    unknown = set(value) - allowed
    if unknown:
        raise ConvergenceAdapterError(f"{path} has unexpected keys {', '.join(sorted(unknown))}")


def _assert_string_keys(value: dict[Any, Any], path: str) -> None:
    non_string = [key for key in value if not isinstance(key, str)]
    if non_string:
        raise ConvergenceAdapterError(f"{path} object keys must be strings")


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
    if "\n" in value or "\r" in value or "\t" in value:
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
        "intent_sha256": sha256_hex(canonical_json(profile["intent"])),
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
        help=(
            "Output the default adapter envelope, only the public request JSON, or only the hash. "
            "Example envelope (abbreviated): {'schema_version': '1.0.0', 'adapter': '...', "
            "'profile_id': '...', 'request': {...}}"
        ),
    )
    args = parser.parse_args(argv)
    try:
        request, request_sha256, profile_sha256 = build_request_from_path(Path(args.profile))
        profile = load_profile(Path(args.profile))
        stdout.write(render_output(profile, request, request_sha256, profile_sha256, args.output))
        stdout.write("\n")
        return 0
    except ConvergenceAdapterError as exc:
        stderr.write(f"convergence adapter error: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
