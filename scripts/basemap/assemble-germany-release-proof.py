#!/usr/bin/env python3
"""Assemble the fail-closed Germany basemap release-proof envelope."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import ipaddress
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

REGIONS = {"hamburg", "berlin", "cologne", "dresden", "munich"}
REQUIRED_PROOFS = [
    "desktop-maplibre",
    "ipad-maplibre",
    "five-region-visual",
    "no-external-map-requests",
    "staging-caddy-range",
]
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


class ProofError(ValueError):
    pass


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


def load_json(path: Path, label: str) -> dict[str, Any]:
    path = regular_file(path, label)
    if path.stat().st_size > 5 * 1024 * 1024:
        fail(f"{label} exceeds the 5 MiB evidence limit")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        fail(f"{label} is unreadable JSON: {exc}")
    if not isinstance(value, dict):
        fail(f"{label} must contain a JSON object")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_time(value: Any, label: str, now: dt.datetime) -> dt.datetime:
    try:
        normalized = value[:-1] + "+00:00" if isinstance(value, str) and value.endswith("Z") else value
        parsed = dt.datetime.fromisoformat(normalized)
    except (TypeError, ValueError) as exc:
        fail(f"{label} must be an ISO-8601 timestamp: {exc}")
    if parsed.tzinfo is None:
        fail(f"{label} must include a timezone")
    parsed = parsed.astimezone(dt.timezone.utc)
    if parsed > now + dt.timedelta(minutes=2):
        fail(f"{label} lies in the future")
    if now - parsed > dt.timedelta(hours=24):
        fail(f"{label} is older than 24 hours")
    return parsed


def require_empty_list(value: Any, label: str) -> None:
    if value != []:
        fail(f"{label} must be an empty list")


def validate_regions(regions: Any, label: str, evidence_dir: Path) -> None:
    if not isinstance(regions, list):
        fail(f"{label} must be a list")
    ids: list[str] = []
    expected_parent = Path(os.path.abspath(evidence_dir))
    for index, region in enumerate(regions):
        item_label = f"{label}[{index}]"
        if not isinstance(region, dict):
            fail(f"{item_label} must be an object")
        region_id = region.get("id")
        if not isinstance(region_id, str):
            fail(f"{item_label}.id must be a string")
        ids.append(region_id)
        if region.get("source_loaded") is not True:
            fail(f"{item_label} does not prove a loaded source")
        for field in ("rendered_from_expected_source", "decoded_source_feature_count"):
            value = region.get(field)
            if type(value) is not int or value <= 0:
                fail(f"{item_label}.{field} must be a positive integer")

        screenshot_value = region.get("screenshot")
        if not isinstance(screenshot_value, str) or not screenshot_value:
            fail(f"{item_label}.screenshot must be a path")
        screenshot = regular_file(Path(screenshot_value), f"{item_label}.screenshot")
        if screenshot.parent != expected_parent:
            fail(f"{item_label}.screenshot must be next to its proof JSON")
        screenshot_size = screenshot.stat().st_size
        expected_size = region.get("screenshot_size_bytes")
        if type(expected_size) is not int or expected_size <= 0:
            fail(f"{item_label}.screenshot_size_bytes must be positive")
        if screenshot_size != expected_size:
            fail(f"{item_label}.screenshot size mismatch")
        expected_sha256 = region.get("screenshot_sha256")
        if not isinstance(expected_sha256, str) or not SHA256_RE.fullmatch(expected_sha256):
            fail(f"{item_label}.screenshot_sha256 must be canonical")
        if sha256_file(screenshot) != expected_sha256:
            fail(f"{item_label}.screenshot SHA256 mismatch")
    if len(ids) != len(set(ids)):
        fail(f"{label} contains duplicate region ids")
    if set(ids) != REGIONS:
        fail(f"{label} must prove exactly {sorted(REGIONS)}")


def validate_desktop(
    value: dict[str, Any],
    *,
    proof_path: Path,
    now: dt.datetime,
    version: str,
    artifact_sha256: str,
    artifact_size: int,
    frontend_commit: str,
    style_sha256: str,
) -> dt.datetime:
    if value.get("verdict") != "PROVEN" or value.get("region") != "germany":
        fail("desktop proof is not a PROVEN Germany proof")
    expected = {
        "basemap_version": version,
        "artifact_sha256": artifact_sha256,
        "artifact_size_bytes": artifact_size,
        "frontend_commit": frontend_commit,
        "style_sha256": style_sha256,
    }
    for field, wanted in expected.items():
        if value.get(field) != wanted:
            fail(f"desktop proof {field} mismatch")
    if value.get("style_loaded") is not True or value.get("source_loaded") is not True:
        fail("desktop proof does not establish loaded style and source")
    for field in (
        "rendered_from_expected_source",
        "decoded_source_feature_count",
        "pmtiles_requests_total",
        "pmtiles_range_requests_observed",
        "pmtiles_206_responses_observed",
    ):
        observed = value.get(field)
        if type(observed) is not int or observed <= 0:
            fail(f"desktop.{field} must be a positive integer")
    canvas = value.get("canvas_dimensions")
    if not isinstance(canvas, dict):
        fail("desktop.canvas_dimensions must be an object")
    for field in ("width", "height"):
        observed = canvas.get(field)
        if type(observed) is not int or observed <= 0:
            fail(f"desktop.canvas_dimensions.{field} must be positive")
    if value.get("direct_range_status") != 206:
        fail("desktop proof does not establish HTTP 206 Range delivery")
    if "bytes" not in str(value.get("direct_range_accept_ranges", "")).lower():
        fail("desktop proof does not establish Accept-Ranges: bytes")
    if not str(value.get("direct_range_content_range", "")).lower().startswith("bytes "):
        fail("desktop proof does not establish Content-Range")
    if "application/octet-stream" not in str(value.get("direct_range_content_type", "")):
        fail("desktop proof does not establish the PMTiles content type")
    for field in (
        "remote_violations",
        "unexpected_api_requests",
        "failed_responses",
        "console_errors",
    ):
        require_empty_list(value.get(field), f"desktop.{field}")
    validate_regions(
        value.get("five_region_evidence"),
        "desktop.five_region_evidence",
        proof_path.parent,
    )
    return parse_time(value.get("timestamp"), "desktop.timestamp", now)


def validate_ipad(
    value: dict[str, Any],
    *,
    proof_path: Path,
    now: dt.datetime,
    version: str,
    artifact_sha256: str,
    artifact_size: int,
    frontend_commit: str,
    style_sha256: str,
) -> dt.datetime:
    if value.get("schema_version") != 1 or value.get("verdict") != "PROVEN":
        fail("iPad proof is not a schema-1 PROVEN proof")
    if value.get("device_class") != "physical-ipad":
        fail("iPad proof must come from a physical iPad")
    if value.get("native_webview") != "WKWebView":
        fail("iPad proof must use native WKWebView")
    expected = {
        "basemap_version": version,
        "artifact_sha256": artifact_sha256,
        "artifact_size_bytes": artifact_size,
        "frontend_commit": frontend_commit,
        "style_sha256": style_sha256,
    }
    for field, wanted in expected.items():
        if value.get(field) != wanted:
            fail(f"iPad proof {field} mismatch")
    if value.get("staging_range_status") != 206:
        fail("iPad proof does not establish staging HTTP 206")
    require_empty_list(value.get("remote_violations"), "ipad.remote_violations")
    validate_regions(value.get("regions"), "ipad.regions", proof_path.parent)
    return parse_time(value.get("proofed_at"), "ipad.proofed_at", now)



def private_staging_origin(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        fail(f"{label} must be a non-empty URL")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"}:
        fail(f"{label} must use HTTP or HTTPS")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        fail(f"{label} must not contain credentials, query or fragment")
    if parsed.path not in {"", "/"}:
        fail(f"{label} must not contain a path")
    host = parsed.hostname
    if not host:
        fail(f"{label} must contain a host")
    if host == "localhost":
        return value.rstrip("/")
    try:
        address = ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError as exc:
        fail(f"{label} must use localhost or a literal private IP address: {exc}")
    if not (address.is_loopback or address.is_private or address.is_link_local):
        fail(f"{label} must remain on a private staging address")
    return value.rstrip("/")


def validate_caddy(
    value: dict[str, Any],
    *,
    now: dt.datetime,
    artifact_name: str,
    artifact_sha256: str,
    artifact_size: int,
) -> dt.datetime:
    if value.get("schema_version") != 1 or value.get("verdict") != "PROVEN":
        fail("Caddy proof is not a schema-1 PROVEN proof")
    if value.get("contract") != "germany-basemap-staging-caddy-v1":
        fail("Caddy proof contract mismatch")
    private_staging_origin(value.get("staging_origin"), "caddy.staging_origin")
    if value.get("scope") != "private-staging":
        fail("Caddy proof must be private-staging scoped")
    expected_artifact = {
        "name": artifact_name,
        "sha256": artifact_sha256,
        "size_bytes": artifact_size,
    }
    if value.get("artifact") != expected_artifact:
        fail("Caddy proof artifact binding mismatch")

    full = value.get("full_get")
    if not isinstance(full, dict):
        fail("caddy.full_get must be an object")
    expected_full = {
        "status": 200,
        "content_type": "application/octet-stream",
        "content_length": artifact_size,
        "bytes_received": artifact_size,
        "sha256": artifact_sha256,
    }
    for field, wanted in expected_full.items():
        if full.get(field) != wanted:
            fail(f"caddy.full_get.{field} mismatch")
    if "bytes" not in str(full.get("accept_ranges", "")).lower():
        fail("caddy.full_get does not establish Accept-Ranges: bytes")

    ranged = value.get("range_get")
    if not isinstance(ranged, dict):
        fail("caddy.range_get must be an object")
    expected_range = {
        "status": 206,
        "content_type": "application/octet-stream",
        "content_range": f"bytes 0-126/{artifact_size}",
        "content_length": 127,
        "payload_size_bytes": 127,
        "signature": "PMTiles",
    }
    for field, wanted in expected_range.items():
        if ranged.get(field) != wanted:
            fail(f"caddy.range_get.{field} mismatch")
    if "bytes" not in str(ranged.get("accept_ranges", "")).lower():
        fail("caddy.range_get does not establish Accept-Ranges: bytes")
    return parse_time(value.get("proofed_at"), "caddy.proofed_at", now)


def write_atomic(path: Path, payload: dict[str, Any]) -> None:
    path = Path(os.path.abspath(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    reject_symlink_components(path.parent, "output parent")
    if path.exists() and (path.is_symlink() or not path.is_file()):
        fail(f"output must be absent or a regular file: {path}")
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, stat.S_IRUSR | stat.S_IWUSR)
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def assemble(args: argparse.Namespace, now: dt.datetime | None = None) -> dict[str, Any]:
    now = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    artifact = regular_file(Path(args.artifact), "artifact")
    style = regular_file(Path(args.style), "style")
    desktop_path = Path(args.desktop_proof)
    ipad_path = Path(args.ipad_proof)
    caddy_path = Path(args.caddy_proof)
    desktop = load_json(desktop_path, "desktop proof")
    ipad = load_json(ipad_path, "iPad proof")
    caddy = load_json(caddy_path, "Caddy proof")

    if not args.version or any(ch.isspace() for ch in args.version):
        fail("version must be non-empty and contain no whitespace")
    if not COMMIT_RE.fullmatch(args.frontend_commit):
        fail("frontend commit must be a canonical 40-character lowercase SHA")

    artifact_sha256 = sha256_file(artifact)
    artifact_size = artifact.stat().st_size
    style_sha256 = sha256_file(style)
    if not SHA256_RE.fullmatch(artifact_sha256) or artifact_size <= 0:
        fail("artifact identity is invalid")

    desktop_time = validate_desktop(
        desktop,
        proof_path=desktop_path,
        now=now,
        version=args.version,
        artifact_sha256=artifact_sha256,
        artifact_size=artifact_size,
        frontend_commit=args.frontend_commit,
        style_sha256=style_sha256,
    )
    ipad_time = validate_ipad(
        ipad,
        proof_path=ipad_path,
        now=now,
        version=args.version,
        artifact_sha256=artifact_sha256,
        artifact_size=artifact_size,
        frontend_commit=args.frontend_commit,
        style_sha256=style_sha256,
    )
    caddy_time = validate_caddy(
        caddy,
        now=now,
        artifact_name=artifact.name,
        artifact_sha256=artifact_sha256,
        artifact_size=artifact_size,
    )
    proofed_at = max(desktop_time, ipad_time, caddy_time).isoformat().replace(
        "+00:00", "Z"
    )

    return {
        "schema_version": 1,
        "verdict": "PROVEN",
        "basemap_version": args.version,
        "artifact_sha256": artifact_sha256,
        "artifact_size_bytes": artifact_size,
        "frontend_commit": args.frontend_commit,
        "style_sha256": style_sha256,
        "proofed_at": proofed_at,
        "proofs": REQUIRED_PROOFS,
        "evidence": {
            "desktop_proof_path": desktop_path.as_posix(),
            "desktop_proof_sha256": sha256_file(desktop_path),
            "ipad_proof_path": ipad_path.as_posix(),
            "ipad_proof_sha256": sha256_file(ipad_path),
            "caddy_proof_path": caddy_path.as_posix(),
            "caddy_proof_sha256": sha256_file(caddy_path),
        },
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--artifact", required=True)
    result.add_argument("--style", required=True)
    result.add_argument("--desktop-proof", required=True)
    result.add_argument("--ipad-proof", required=True)
    result.add_argument("--caddy-proof", required=True)
    result.add_argument("--version", required=True)
    result.add_argument("--frontend-commit", required=True)
    result.add_argument("--output", required=True)
    return result


def main() -> int:
    try:
        args = parser().parse_args()
        payload = assemble(args)
        output = Path(args.output)
        write_atomic(output, payload)
        print(json.dumps({"output": output.as_posix(), **payload}, sort_keys=True))
        return 0
    except ProofError as exc:
        print(f"NOT_PROVEN: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
