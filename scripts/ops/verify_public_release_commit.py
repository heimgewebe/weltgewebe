#!/usr/bin/env python3
"""Verify the public Weltgewebe release identity and declared artifact evidence."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from weltgewebe_secure_receipt_io import write_secure_json

DEFAULT_FRONTEND_URL = "https://commonthing.net/_app/version.json"
DEFAULT_API_URL = "https://commonthing.net/api/version"
DEFAULT_MAX_RESPONSE_BYTES = 1024 * 1024
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_SAFE_INTEGER = (1 << 53) - 1
UNATTESTED_PROVENANCE = "unattested"
LIMITED_PASS_STATUS = "consistency_pass_unattested"
LIMITED_PASS_SCOPE = "identity_and_declared_artifact_consistency"
ARTIFACT_TREE_KEYS = frozenset(
    {"schema_version", "sha256", "file_count", "compile_revision", "provenance"}
)


class StrictJsonError(ValueError):
    """Raised when a JSON response is syntactically valid but contract-ambiguous."""


def _strict_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StrictJsonError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_nonfinite_constant(value: str) -> None:
    raise StrictJsonError(f"non-finite JSON number: {value}")


@dataclass(frozen=True)
class ArtifactTreeResult:
    schema_version: int | None
    sha256: str | None
    file_count: int | None
    compile_revision: str | None
    provenance: str | None
    error: str | None = None


@dataclass(frozen=True)
class EndpointResult:
    url: str
    status: int
    commit: str | None
    version: str | None
    headers: dict[str, str]
    error: str | None = None
    artifact_tree: ArtifactTreeResult | None = None


@dataclass(frozen=True)
class VerificationResult:
    schema_version: int
    expected_commit: str
    verified_at: str
    pass_: bool
    status: str
    pass_scope: str
    identity_verified: bool
    artifact_tree_declaration_verified: bool
    attestation_verified: bool
    provenance_status: str
    reasons: list[str]
    limitations: list[str]
    frontend: EndpointResult
    api: EndpointResult

    def as_json(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["pass"] = payload.pop("pass_")
        return payload


def validate_commit(value: str) -> str:
    candidate = value.strip()
    if not COMMIT_RE.fullmatch(candidate):
        raise ValueError(
            "expected commit must be a full 40-character lowercase hexadecimal SHA"
        )
    return candidate


def _normalize_headers(headers: Mapping[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    raw_items = getattr(headers, "raw_items", headers.items)
    for key, value in raw_items():
        normalized_key = str(key).lower()
        normalized_value = str(value)
        existing = normalized.get(normalized_key)
        normalized[normalized_key] = (
            f"{existing}, {normalized_value}" if existing else normalized_value
        )
    return normalized


def _read_bounded(response: Any, max_response_bytes: int) -> bytes:
    content_length = response.headers.get("Content-Length")
    if content_length is not None:
        try:
            declared = int(content_length)
        except ValueError as exc:
            raise ValueError("invalid Content-Length header") from exc
        if declared < 0 or declared > max_response_bytes:
            raise ValueError(
                f"response exceeds byte limit: {declared} > {max_response_bytes}"
            )
    raw = response.read(max_response_bytes + 1)
    if len(raw) > max_response_bytes:
        raise ValueError(
            f"response exceeds byte limit: more than {max_response_bytes} bytes"
        )
    return raw


def _parse_artifact_tree(payload: Mapping[str, Any]) -> ArtifactTreeResult | None:
    if "artifact_tree" not in payload:
        return None

    raw = payload.get("artifact_tree")
    if not isinstance(raw, dict):
        return ArtifactTreeResult(
            schema_version=None,
            sha256=None,
            file_count=None,
            compile_revision=None,
            provenance=None,
            error="artifact_tree is not an object",
        )

    raw_schema_version = raw.get("schema_version")
    raw_sha256 = raw.get("sha256")
    raw_file_count = raw.get("file_count")
    raw_compile_revision = raw.get("compile_revision")
    raw_provenance = raw.get("provenance")
    errors: list[str] = []
    missing_keys = sorted(ARTIFACT_TREE_KEYS - set(raw))
    unknown_keys = sorted(set(raw) - ARTIFACT_TREE_KEYS)
    if missing_keys:
        errors.append(f"missing fields: {', '.join(missing_keys)}")
    if unknown_keys:
        errors.append(f"unknown fields: {', '.join(unknown_keys)}")

    schema_version = (
        raw_schema_version
        if isinstance(raw_schema_version, int)
        and not isinstance(raw_schema_version, bool)
        else None
    )
    if schema_version != 1:
        errors.append("schema_version must equal 1")

    sha256 = raw_sha256 if isinstance(raw_sha256, str) else None
    if sha256 is None or not SHA256_RE.fullmatch(sha256):
        errors.append("sha256 must be a full lowercase SHA-256 digest")

    file_count = (
        raw_file_count
        if isinstance(raw_file_count, int) and not isinstance(raw_file_count, bool)
        else None
    )
    if file_count is None or not 1 <= file_count <= MAX_SAFE_INTEGER:
        errors.append("file_count must be a positive safe integer")

    compile_revision = (
        raw_compile_revision if isinstance(raw_compile_revision, str) else None
    )
    if compile_revision is None or not COMMIT_RE.fullmatch(compile_revision):
        errors.append("compile_revision must be a full lowercase Git commit SHA")

    provenance = raw_provenance if isinstance(raw_provenance, str) else None
    if provenance is None or not provenance:
        errors.append("provenance must be a non-empty string")

    return ArtifactTreeResult(
        schema_version=schema_version,
        sha256=sha256,
        file_count=file_count,
        compile_revision=compile_revision,
        provenance=provenance,
        error="; ".join(errors) if errors else None,
    )


def fetch_endpoint(
    url: str,
    timeout: float,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
) -> EndpointResult:
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    if max_response_bytes <= 0:
        raise ValueError("max_response_bytes must be positive")

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Cache-Control": "no-cache",
            "User-Agent": "weltgewebe-production-live-contract/2",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(response.status)
            headers = _normalize_headers(response.headers)
            final_url = response.geturl()
            if final_url != url:
                return EndpointResult(
                    url,
                    status,
                    None,
                    None,
                    headers,
                    f"unexpected redirect target: {final_url}",
                )
            try:
                raw = _read_bounded(response, max_response_bytes)
            except ValueError as exc:
                return EndpointResult(url, status, None, None, headers, str(exc))
    except urllib.error.HTTPError as exc:
        headers = _normalize_headers(exc.headers or {})
        return EndpointResult(url, int(exc.code), None, None, headers, str(exc.reason))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return EndpointResult(url, 0, None, None, {}, str(exc))

    try:
        payload = json.loads(
            raw,
            object_pairs_hook=_strict_object_pairs,
            parse_constant=_reject_nonfinite_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, StrictJsonError) as exc:
        return EndpointResult(url, status, None, None, headers, f"invalid JSON: {exc}")

    if not isinstance(payload, dict):
        return EndpointResult(
            url, status, None, None, headers, "JSON body is not an object"
        )

    commit = payload.get("commit")
    version = payload.get("version")
    return EndpointResult(
        url=url,
        status=status,
        commit=commit if isinstance(commit, str) else None,
        version=version if isinstance(version, str) else None,
        headers=headers,
        artifact_tree=_parse_artifact_tree(payload),
    )


def evaluate(
    expected_commit: str,
    frontend: EndpointResult,
    api: EndpointResult,
) -> VerificationResult:
    identity_reasons: list[str] = []
    artifact_reasons: list[str] = []
    expected_short = expected_commit[:8]

    for name, result in (("frontend", frontend), ("api", api)):
        if result.error:
            identity_reasons.append(f"{name} readback failed: {result.error}")
        if result.status != 200:
            identity_reasons.append(
                f"{name} returned HTTP {result.status}, expected 200"
            )
        if result.commit != expected_commit:
            identity_reasons.append(
                f"{name} commit mismatch: expected {expected_commit}, got {result.commit!r}"
            )
        if result.version != expected_short and name == "frontend":
            identity_reasons.append(
                f"frontend version mismatch: expected {expected_short}, got {result.version!r}"
            )

    frontend_cache = frontend.headers.get("cache-control", "").lower()
    if "no-store" not in frontend_cache:
        identity_reasons.append(
            "frontend version readback is not served with Cache-Control: no-store"
        )

    api_build = api.headers.get("x-weltgewebe-api-build")
    if api_build != expected_commit:
        identity_reasons.append(
            f"API build header mismatch: expected {expected_commit}, got {api_build!r}"
        )

    edge_build = api.headers.get("x-weltgewebe-build")
    if edge_build != expected_short:
        identity_reasons.append(
            f"edge build header mismatch: expected {expected_short}, got {edge_build!r}"
        )

    artifact_tree = frontend.artifact_tree
    if artifact_tree is None:
        artifact_reasons.append("frontend artifact_tree declaration is missing")
        provenance_status = "missing"
    elif artifact_tree.error:
        artifact_reasons.append(
            f"frontend artifact_tree declaration is invalid: {artifact_tree.error}"
        )
        provenance_status = artifact_tree.provenance or "invalid"
    else:
        provenance_status = artifact_tree.provenance or "missing"
        if artifact_tree.compile_revision != expected_commit:
            artifact_reasons.append(
                "frontend artifact_tree compile_revision mismatch: "
                f"expected {expected_commit}, got {artifact_tree.compile_revision!r}"
            )
        if artifact_tree.provenance != UNATTESTED_PROVENANCE:
            artifact_reasons.append(
                "frontend artifact_tree provenance is unsupported: "
                f"expected {UNATTESTED_PROVENANCE!r} until an attestation verifier "
                f"is implemented, got {artifact_tree.provenance!r}"
            )

    identity_verified = not identity_reasons
    artifact_tree_declaration_verified = not artifact_reasons
    reasons = identity_reasons + artifact_reasons
    pass_ = not reasons
    limitations = (
        [
            "the public verifier does not reconstruct the deployed artifact tree",
            "artifact provenance is explicitly unattested",
        ]
        if pass_
        else []
    )

    return VerificationResult(
        schema_version=3,
        expected_commit=expected_commit,
        verified_at=datetime.now(timezone.utc).isoformat(),
        pass_=pass_,
        status=LIMITED_PASS_STATUS if pass_ else "failed",
        pass_scope=LIMITED_PASS_SCOPE if pass_ else "none",
        identity_verified=identity_verified,
        artifact_tree_declaration_verified=artifact_tree_declaration_verified,
        attestation_verified=False,
        provenance_status=provenance_status,
        reasons=reasons,
        limitations=limitations,
        frontend=frontend,
        api=api,
    )


def write_receipt(path: Path, result: VerificationResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    write_secure_json(
        path,
        result.as_json(),
        expected_uid=os.geteuid(),
        ensure_ascii=False,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--frontend-url", default=DEFAULT_FRONTEND_URL)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--wait-seconds", type=int, default=0)
    parser.add_argument("--poll-seconds", type=int, default=15)
    parser.add_argument(
        "--max-response-bytes", type=int, default=DEFAULT_MAX_RESPONSE_BYTES
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        expected = validate_commit(args.expected_commit)
        if args.timeout <= 0:
            raise ValueError("timeout must be positive")
        if args.wait_seconds < 0:
            raise ValueError("wait-seconds must not be negative")
        if args.poll_seconds < 1:
            raise ValueError("poll-seconds must be at least one")
        if args.max_response_bytes < 1:
            raise ValueError("max-response-bytes must be at least one")
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    deadline = time.monotonic() + args.wait_seconds
    while True:
        frontend = fetch_endpoint(
            args.frontend_url, args.timeout, args.max_response_bytes
        )
        api = fetch_endpoint(args.api_url, args.timeout, args.max_response_bytes)
        result = evaluate(expected, frontend, api)
        write_receipt(args.output, result)
        if result.pass_:
            artifact_tree = result.frontend.artifact_tree
            artifact_sha256 = artifact_tree.sha256 if artifact_tree else "missing"
            print(
                "production_release_identity=ok "
                "production_release_consistency=limited "
                f"status={result.status} commit={expected} "
                f"artifact_tree_sha256={artifact_sha256} "
                f"provenance={result.provenance_status} "
                f"attestation_verified={str(result.attestation_verified).lower()} "
                f"frontend={args.frontend_url} api={args.api_url}"
            )
            return 0
        if time.monotonic() >= deadline:
            for reason in result.reasons:
                print(f"ERROR: {reason}", file=sys.stderr)
            return 1
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
