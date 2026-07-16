#!/usr/bin/env python3
"""Verify that public Weltgewebe frontend and API serve one exact Git commit."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

DEFAULT_FRONTEND_URL = "https://weltgewebe.net/_app/version.json"
DEFAULT_API_URL = "https://weltgewebe.net/api/version"


@dataclass(frozen=True)
class EndpointResult:
    url: str
    status: int
    commit: str | None
    version: str | None
    headers: dict[str, str]
    error: str | None = None


@dataclass(frozen=True)
class VerificationResult:
    schema_version: int
    expected_commit: str
    verified_at: str
    pass_: bool
    reasons: list[str]
    frontend: EndpointResult
    api: EndpointResult

    def as_json(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["pass"] = payload.pop("pass_")
        return payload


def validate_commit(value: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) != 40 or any(char not in "0123456789abcdef" for char in normalized):
        raise ValueError("expected commit must be a full 40-character lowercase hexadecimal SHA")
    return normalized


def _normalize_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {str(key).lower(): str(value) for key, value in headers.items()}


def fetch_endpoint(url: str, timeout: float) -> EndpointResult:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "Cache-Control": "no-cache"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(response.status)
            raw = response.read()
            headers = _normalize_headers(response.headers)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return EndpointResult(url, 0, None, None, {}, str(exc))

    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return EndpointResult(url, status, None, None, headers, f"invalid JSON: {exc}")

    if not isinstance(payload, dict):
        return EndpointResult(url, status, None, None, headers, "JSON body is not an object")

    commit = payload.get("commit")
    version = payload.get("version")
    return EndpointResult(
        url=url,
        status=status,
        commit=commit if isinstance(commit, str) else None,
        version=version if isinstance(version, str) else None,
        headers=headers,
    )


def evaluate(
    expected_commit: str,
    frontend: EndpointResult,
    api: EndpointResult,
) -> VerificationResult:
    reasons: list[str] = []
    expected_short = expected_commit[:8]

    for name, result in (("frontend", frontend), ("api", api)):
        if result.error:
            reasons.append(f"{name} readback failed: {result.error}")
        if result.status != 200:
            reasons.append(f"{name} returned HTTP {result.status}, expected 200")
        if result.commit != expected_commit:
            reasons.append(
                f"{name} commit mismatch: expected {expected_commit}, got {result.commit!r}"
            )
        if result.version != expected_short and name == "frontend":
            reasons.append(
                f"frontend version mismatch: expected {expected_short}, got {result.version!r}"
            )

    frontend_cache = frontend.headers.get("cache-control", "").lower()
    if "no-store" not in frontend_cache:
        reasons.append("frontend version readback is not served with Cache-Control: no-store")

    api_build = api.headers.get("x-weltgewebe-api-build")
    if api_build != expected_commit:
        reasons.append(
            f"API build header mismatch: expected {expected_commit}, got {api_build!r}"
        )

    edge_build = api.headers.get("x-weltgewebe-build")
    if edge_build != expected_short:
        reasons.append(
            f"edge build header mismatch: expected {expected_short}, got {edge_build!r}"
        )

    return VerificationResult(
        schema_version=1,
        expected_commit=expected_commit,
        verified_at=datetime.now(timezone.utc).isoformat(),
        pass_=not reasons,
        reasons=reasons,
        frontend=frontend,
        api=api,
    )


def write_receipt(path: Path, result: VerificationResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(result.as_json(), handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--frontend-url", default=DEFAULT_FRONTEND_URL)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--wait-seconds", type=int, default=0)
    parser.add_argument("--poll-seconds", type=int, default=15)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        expected = validate_commit(args.expected_commit)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    deadline = time.monotonic() + max(args.wait_seconds, 0)
    result: VerificationResult | None = None
    while True:
        frontend = fetch_endpoint(args.frontend_url, args.timeout)
        api = fetch_endpoint(args.api_url, args.timeout)
        result = evaluate(expected, frontend, api)
        write_receipt(args.output, result)
        if result.pass_:
            print(
                f"production_release_identity=ok commit={expected} "
                f"frontend={args.frontend_url} api={args.api_url}"
            )
            return 0
        if time.monotonic() >= deadline:
            for reason in result.reasons:
                print(f"ERROR: {reason}", file=sys.stderr)
            return 1
        time.sleep(max(args.poll_seconds, 1))


if __name__ == "__main__":
    raise SystemExit(main())
