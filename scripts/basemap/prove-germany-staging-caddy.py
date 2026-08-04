#!/usr/bin/env python3
"""Prove one private staging Caddy PMTiles delivery contract."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import ipaddress
import json
import os
import stat
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


class ProofError(ValueError):
    pass


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        request: urllib.request.Request,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> None:
        del request, file_pointer, code, message, headers, new_url
        return None


def fail(message: str) -> None:
    raise ProofError(message)


def reject_symlink_components(path: Path, label: str) -> Path:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        if current.is_symlink():
            fail(f"{label} must not traverse a symlink: {current}")
    return absolute


def regular_file(path: Path, label: str) -> Path:
    absolute = reject_symlink_components(path, label)
    if not absolute.is_file():
        fail(f"{label} must be a non-symlink regular file: {absolute}")
    return absolute


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_staging_origin(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"}:
        fail("origin must use HTTP or HTTPS")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        fail("origin must not contain credentials, query or fragment")
    if parsed.path not in {"", "/"}:
        fail("origin must not contain a path")
    host = parsed.hostname
    if not host:
        fail("origin must contain a host")
    try:
        parsed.port
    except ValueError as exc:
        fail(f"origin contains an invalid port: {exc}")
    if host == "localhost":
        return value.rstrip("/")
    try:
        address = ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError as exc:
        fail(f"origin must use localhost or a literal private IP address: {exc}")
    if not (address.is_loopback or address.is_private or address.is_link_local):
        fail(f"origin must remain private staging; public address observed: {address}")
    return value.rstrip("/")


def normalized_content_type(headers: Any) -> str:
    return str(headers.get("Content-Type", "")).split(";", 1)[0].strip().lower()


def integer_header(headers: Any, name: str) -> int:
    raw = headers.get(name)
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        fail(f"{name} must be an integer header: {exc}")
    if value < 0:
        fail(f"{name} must not be negative")
    return value


def open_get(url: str, *, timeout: int, headers: dict[str, str] | None = None):
    request = urllib.request.Request(url, headers=headers or {}, method="GET")
    opener = urllib.request.build_opener(NoRedirectHandler())
    try:
        response = opener.open(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        if 300 <= exc.code < 400:
            fail(f"staging proof must not follow redirects: HTTP {exc.code}")
        fail(f"HTTP GET failed for {url}: HTTP {exc.code}")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        fail(f"HTTP GET failed for {url}: {exc}")
    if response.geturl() != url:
        response.close()
        fail(f"staging proof must not follow redirects: {response.geturl()}")
    return response


def prove(args: argparse.Namespace, now: dt.datetime | None = None) -> dict[str, Any]:
    artifact = regular_file(Path(args.artifact), "artifact")
    origin = validate_staging_origin(args.origin)
    if args.timeout_seconds <= 0:
        fail("timeout-seconds must be positive")
    artifact_size = artifact.stat().st_size
    if artifact_size <= 0:
        fail("artifact must not be empty")
    artifact_sha256 = sha256_file(artifact)
    endpoint = f"{origin}/local-basemap/basemap-germany.pmtiles"

    with open_get(endpoint, timeout=args.timeout_seconds) as response:
        full_status = response.status
        full_content_type = normalized_content_type(response.headers)
        full_content_length = integer_header(response.headers, "Content-Length")
        full_accept_ranges = str(response.headers.get("Accept-Ranges", ""))
        digest = hashlib.sha256()
        bytes_received = 0
        for chunk in iter(lambda: response.read(1024 * 1024), b""):
            digest.update(chunk)
            bytes_received += len(chunk)
        full_sha256 = digest.hexdigest()
    if full_status != 200:
        fail(f"full GET returned HTTP {full_status}, expected 200")
    if full_content_type != "application/octet-stream":
        fail(f"full GET Content-Type mismatch: {full_content_type!r}")
    if "bytes" not in full_accept_ranges.lower():
        fail("full GET lacks Accept-Ranges: bytes")
    if full_content_length != artifact_size or bytes_received != artifact_size:
        fail("full GET byte length does not match the local artifact")
    if full_sha256 != artifact_sha256:
        fail("full GET SHA256 does not match the local artifact")

    with open_get(
        endpoint,
        timeout=args.timeout_seconds,
        headers={"Range": "bytes=0-126", "Accept-Encoding": "identity"},
    ) as response:
        range_status = response.status
        range_content_type = normalized_content_type(response.headers)
        range_content_length = integer_header(response.headers, "Content-Length")
        range_content_range = str(response.headers.get("Content-Range", ""))
        range_accept_ranges = str(response.headers.get("Accept-Ranges", ""))
        payload = response.read(128)
        extra = response.read(1)
    if range_status != 206:
        fail(f"range GET returned HTTP {range_status}, expected 206")
    if range_content_type != "application/octet-stream":
        fail(f"range GET Content-Type mismatch: {range_content_type!r}")
    if range_content_range != f"bytes 0-126/{artifact_size}":
        fail(f"range GET Content-Range mismatch: {range_content_range!r}")
    if "bytes" not in range_accept_ranges.lower():
        fail("range GET lacks Accept-Ranges: bytes")
    if range_content_length != 127 or len(payload) != 127 or extra:
        fail("range GET payload length mismatch")
    if payload[:7] != b"PMTiles":
        fail("range GET PMTiles signature mismatch")

    proofed_at = (now or dt.datetime.now(dt.timezone.utc)).astimezone(
        dt.timezone.utc
    ).isoformat().replace("+00:00", "Z")
    return {
        "schema_version": 1,
        "verdict": "PROVEN",
        "contract": "germany-basemap-staging-caddy-v1",
        "proofed_at": proofed_at,
        "scope": "private-staging",
        "staging_origin": origin,
        "endpoint": endpoint,
        "artifact": {
            "name": artifact.name,
            "sha256": artifact_sha256,
            "size_bytes": artifact_size,
        },
        "full_get": {
            "status": full_status,
            "content_type": full_content_type,
            "content_length": full_content_length,
            "accept_ranges": full_accept_ranges,
            "bytes_received": bytes_received,
            "sha256": full_sha256,
        },
        "range_get": {
            "status": range_status,
            "content_type": range_content_type,
            "content_range": range_content_range,
            "content_length": range_content_length,
            "accept_ranges": range_accept_ranges,
            "payload_size_bytes": len(payload),
            "signature": payload[:7].decode("ascii"),
        },
    }


def write_atomic(path: Path, payload: dict[str, Any]) -> None:
    absolute = Path(os.path.abspath(path))
    absolute.parent.mkdir(parents=True, exist_ok=True)
    reject_symlink_components(absolute.parent, "output parent")
    if absolute.exists() and (absolute.is_symlink() or not absolute.is_file()):
        fail(f"output must be absent or a regular file: {absolute}")
    fd, temporary = tempfile.mkstemp(prefix=f".{absolute.name}.", dir=absolute.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, stat.S_IRUSR | stat.S_IWUSR)
        os.replace(temporary, absolute)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--origin", required=True)
    result.add_argument("--artifact", required=True)
    result.add_argument("--output", required=True)
    result.add_argument("--timeout-seconds", type=int, default=900)
    return result


def main() -> int:
    try:
        args = parser().parse_args()
        payload = prove(args)
        output = Path(args.output)
        write_atomic(output, payload)
        print(json.dumps({"output": output.as_posix(), **payload}, sort_keys=True))
        return 0
    except ProofError as exc:
        print(f"NOT_PROVEN: {exc}", file=os.sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
