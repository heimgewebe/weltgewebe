#!/usr/bin/env python3
"""Collect one runtime-read-only, value-redacted Weltgewebe production evidence envelope.

The collector reads only explicitly allowlisted, non-confidential mode switches
from the running API container. It never reads the complete container
environment. Public readiness and release identity are fetched over HTTPS.
Backup and restore evidence must be supplied as exact files; the collector does
not guess which artifact is current.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.ops.check_public_live_readiness import FetchResult, fetch_url
except ModuleNotFoundError:  # direct execution from scripts/ops
    from check_public_live_readiness import FetchResult, fetch_url

SCHEMA_VERSION = 2
EVIDENCE_KIND = "weltgewebe.production-runtime-evidence"
EXPECTED_TABLES = (
    "domain_accounts",
    "domain_nodes",
    "domain_edges",
    "sessions",
    "passkey_credentials",
    "_sqlx_migrations",
)
RUNTIME_EXPECTATIONS: Mapping[str, str] = {
    "WELTGEWEBE_DOMAIN_READ_SOURCE": "postgres",
    "WELTGEWEBE_DOMAIN_ACCOUNT_WRITE_SOURCE": "postgres",
    "WELTGEWEBE_DOMAIN_NODE_WRITE_SOURCE": "postgres",
    "WELTGEWEBE_DOMAIN_EDGE_WRITE_SOURCE": "postgres",
    "WELTGEWEBE_PASSKEY_CREDENTIAL_SOURCE": "postgres",
    "WELTGEWEBE_API_STARTUP_MIGRATIONS": "verify-applied",
}
RUNTIME_ALIASES: Mapping[str, Mapping[str, str]] = {
    "WELTGEWEBE_DOMAIN_READ_SOURCE": {
        "jsonl": "jsonl",
        "file": "jsonl",
        "files": "jsonl",
        "postgres": "postgres",
        "pg": "postgres",
        "db": "postgres",
    },
    "WELTGEWEBE_DOMAIN_ACCOUNT_WRITE_SOURCE": {
        "jsonl": "jsonl",
        "file": "jsonl",
        "files": "jsonl",
        "postgres": "postgres",
        "pg": "postgres",
        "db": "postgres",
    },
    "WELTGEWEBE_DOMAIN_NODE_WRITE_SOURCE": {
        "jsonl": "jsonl",
        "file": "jsonl",
        "files": "jsonl",
        "postgres": "postgres",
        "pg": "postgres",
        "db": "postgres",
    },
    "WELTGEWEBE_DOMAIN_EDGE_WRITE_SOURCE": {
        "jsonl": "jsonl",
        "file": "jsonl",
        "files": "jsonl",
        "postgres": "postgres",
        "pg": "postgres",
        "db": "postgres",
    },
    "WELTGEWEBE_PASSKEY_CREDENTIAL_SOURCE": {
        "in_memory": "in_memory",
        "memory": "in_memory",
        "mem": "in_memory",
        "postgres": "postgres",
        "pg": "postgres",
        "db": "postgres",
    },
    "WELTGEWEBE_API_STARTUP_MIGRATIONS": {
        "run": "run",
        "verify-applied": "verify-applied",
    },
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{7,64}$")
SAFE_PUBLIC_TEXT_RE = re.compile(r"^[A-Za-z0-9._:+-]{1,128}$")
SAFE_BACKUP_FILE_RE = re.compile(r"^[A-Za-z0-9._-]+\.sql\.gz$")
SAFE_HOST_RE = re.compile(r"^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$")
BACKUP_MANIFEST_KEYS = frozenset({"contract", "created_at", "file", "sha256", "bytes", "git_commit", "tables"})
RESTORE_PROOF_KEYS = frozenset({"contract", "created_at", "backup_file", "backup_sha256", "tables", "result"})
MAX_EVIDENCE_METADATA_BYTES = 64 * 1024


class EvidenceError(RuntimeError):
    """Raised when a bounded production evidence claim cannot be established."""


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str = ""


Runner = Callable[[Sequence[str]], CommandResult]
Fetcher = Callable[[str, Mapping[str, str] | None, float], FetchResult]


def run_command(argv: Sequence[str]) -> CommandResult:
    proc = subprocess.run(
        list(argv),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=15,
    )
    return CommandResult(proc.returncode, proc.stdout, proc.stderr)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: str, *, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EvidenceError(f"{field} is not a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise EvidenceError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def canonical_runtime_value(key: str, raw: str) -> str:
    value = raw.strip().lower()
    aliases = RUNTIME_ALIASES[key]
    if value not in aliases:
        raise EvidenceError(f"running API returned an unsupported value for {key}")
    return aliases[value]


def build_compose_prefix(
    *,
    docker_bin: str,
    project_name: str,
    env_file: Path,
    compose_files: Sequence[Path],
) -> list[str]:
    if not compose_files:
        raise EvidenceError("at least one compose file is required")
    argv = [docker_bin, "compose", "--env-file", str(env_file), "-p", project_name]
    for compose_file in compose_files:
        argv.extend(["-f", str(compose_file)])
    return argv


def collect_runtime_modes(
    *,
    compose_prefix: Sequence[str],
    service: str,
    runner: Runner = run_command,
) -> dict[str, Any]:
    observed: dict[str, str] = {}
    checks: list[dict[str, object]] = []
    for key, expected in RUNTIME_EXPECTATIONS.items():
        argv = [*compose_prefix, "exec", "-T", service, "printenv", key]
        try:
            result = runner(argv)
        except (OSError, subprocess.SubprocessError) as exc:
            raise EvidenceError(f"could not complete runtime probe for allowlisted key {key}") from exc
        if result.returncode != 0:
            raise EvidenceError(f"could not read allowlisted runtime key {key} from service {service}")
        canonical = canonical_runtime_value(key, result.stdout)
        observed[key] = canonical
        checks.append(
            {
                "key": key,
                "status": "pass" if canonical == expected else "fail",
                "observed": canonical,
                "expected": expected,
            }
        )
    ok = all(item["status"] == "pass" for item in checks)
    return {
        "status": "pass" if ok else "fail",
        "source": "running-api-container",
        "service": service,
        "read_method": "one printenv call per allowlisted key",
        "complete_environment_read": False,
        "confidential_values_read": False,
        "checks": checks,
        "observed": observed,
    }


def lower_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {str(key).lower(): str(value) for key, value in headers.items()}


def fetch_json(fetcher: Fetcher, url: str, timeout: float) -> tuple[FetchResult, dict[str, Any]]:
    try:
        result = fetcher(url, None, timeout)
    except Exception as exc:
        raise EvidenceError(f"public request failed for {url}") from exc
    try:
        payload = json.loads(result.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"public endpoint returned invalid JSON: {url}") from exc
    if not isinstance(payload, dict):
        raise EvidenceError(f"public endpoint returned a non-object JSON value: {url}")
    return result, payload


def safe_public_text(value: object) -> str:
    if isinstance(value, str) and SAFE_PUBLIC_TEXT_RE.fullmatch(value):
        return value
    return "<invalid>"


def validate_hostname(value: str, *, field: str) -> str:
    if not SAFE_HOST_RE.fullmatch(value):
        raise EvidenceError(f"{field} is not a valid hostname")
    return value


def public_commit(value: object) -> tuple[str, bool]:
    if isinstance(value, str) and COMMIT_RE.fullmatch(value):
        return value, True
    if value == "unknown":
        return "unknown", False
    return "<invalid>", False


def commit_identities_match(header: str, body: str) -> bool:
    if not COMMIT_RE.fullmatch(header) or not COMMIT_RE.fullmatch(body):
        return False
    shorter, longer = sorted((header, body), key=len)
    return len(shorter) >= 7 and longer.startswith(shorter)


def collect_public_evidence(
    *,
    domain: str,
    api_domain: str,
    timeout: float,
    fetcher: Fetcher = fetch_url,
) -> dict[str, Any]:
    domain = validate_hostname(domain, field="domain")
    api_domain = validate_hostname(api_domain, field="api_domain")
    ready_result, ready = fetch_json(fetcher, f"https://{api_domain}/health/ready", timeout)
    api_result, api_version = fetch_json(fetcher, f"https://{api_domain}/version", timeout)
    web_result, web_version = fetch_json(fetcher, f"https://{domain}/_app/version.json", timeout)

    ready_checks = ready.get("checks")
    if not isinstance(ready_checks, dict):
        ready_checks = {}
    safe_ready_checks = {
        key: ready_checks.get(key) is True for key in ("database", "nats", "policy")
    }
    ready_ok = (
        ready_result.status == 200
        and ready.get("status") == "ok"
        and all(safe_ready_checks.values())
    )

    api_commit, api_commit_valid = public_commit(api_version.get("commit"))
    web_commit, web_commit_valid = public_commit(web_version.get("commit"))
    api_header = lower_headers(api_result.headers).get("x-weltgewebe-api-build", "")
    web_header = lower_headers(web_result.headers).get("x-weltgewebe-build", "")
    api_header_matches = api_commit_valid and commit_identities_match(api_header, api_commit)
    web_header_matches = web_commit_valid and commit_identities_match(web_header, web_commit)
    api_identity_ok = api_result.status == 200 and api_header_matches
    web_identity_ok = web_result.status == 200 and web_header_matches

    checks = [
        {
            "name": "api-readiness",
            "status": "pass" if ready_ok else "fail",
            "http_status": ready_result.status,
            "checks": safe_ready_checks,
        },
        {
            "name": "api-release-identity",
            "status": "pass" if api_identity_ok else "fail",
            "http_status": api_result.status,
            "commit": api_commit,
            "commit_valid": api_commit_valid,
            "build_header_present": bool(api_header),
            "header_matches_body": api_header_matches,
            "version": safe_public_text(api_version.get("version")),
            "build_timestamp": safe_public_text(api_version.get("build_timestamp")),
        },
        {
            "name": "web-release-identity",
            "status": "pass" if web_identity_ok else "fail",
            "http_status": web_result.status,
            "commit": web_commit,
            "commit_valid": web_commit_valid,
            "build_header_present": bool(web_header),
            "header_matches_body": web_header_matches,
            "version": safe_public_text(web_version.get("version")),
        },
    ]
    ok = all(item["status"] == "pass" for item in checks)
    return {
        "status": "pass" if ok else "fail",
        "transport": "public-https",
        "checks": checks,
    }


def read_small_regular_text(path: Path) -> str:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise EvidenceError(f"could not open selected evidence metadata: {path}") from exc
    try:
        file_stat = os.fstat(fd)
        if not stat.S_ISREG(file_stat.st_mode):
            raise EvidenceError(f"selected evidence metadata is not a regular file: {path}")
        if file_stat.st_size > MAX_EVIDENCE_METADATA_BYTES:
            raise EvidenceError(f"selected evidence metadata exceeds the size limit: {path}")
        with os.fdopen(fd, "rb", closefd=False) as handle:
            raw = handle.read(MAX_EVIDENCE_METADATA_BYTES + 1)
        if len(raw) > MAX_EVIDENCE_METADATA_BYTES:
            raise EvidenceError(f"selected evidence metadata exceeds the size limit: {path}")
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise EvidenceError(f"selected evidence metadata is not UTF-8: {path}") from exc
    finally:
        os.close(fd)


def read_key_value_file(path: Path, *, allowed_keys: frozenset[str]) -> dict[str, str]:
    text = read_small_regular_text(path)
    values: dict[str, str] = {}
    for line_number, raw in enumerate(text.splitlines(), start=1):
        if not raw or raw.startswith("#"):
            continue
        if "=" not in raw:
            raise EvidenceError(f"invalid evidence line {line_number} in {path.name}")
        key, value = raw.split("=", 1)
        if not key or key in values:
            raise EvidenceError(f"duplicate or empty evidence key in {path.name}")
        if key not in allowed_keys:
            raise EvidenceError(f"unsupported evidence key in {path.name}")
        values[key] = value
    return values


def require_exact_tables(value: str, *, source: str) -> list[str]:
    observed = tuple(item for item in value.split(",") if item)
    if observed != EXPECTED_TABLES:
        raise EvidenceError(f"{source} does not cover the required table set")
    return list(observed)


def sha256_and_size(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    byte_count = 0
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise EvidenceError(f"could not open selected backup artifact: {path}") from exc
    try:
        file_stat = os.fstat(fd)
        if not stat.S_ISREG(file_stat.st_mode):
            raise EvidenceError(f"selected backup artifact is not a regular file: {path}")
        with os.fdopen(fd, "rb", closefd=False) as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
                byte_count += len(chunk)
    finally:
        os.close(fd)
    return digest.hexdigest(), byte_count


def collect_backup_evidence(
    *,
    manifest_path: Path,
    now: datetime,
    max_age: timedelta,
) -> dict[str, Any]:
    values = read_key_value_file(manifest_path, allowed_keys=BACKUP_MANIFEST_KEYS)
    if values.get("contract") != "weltgewebe-postgres-backup-v1":
        raise EvidenceError("backup manifest contract is not supported")
    created = parse_utc(values.get("created_at", ""), field="backup created_at")
    age = now.astimezone(timezone.utc) - created
    if age.total_seconds() < 0:
        raise EvidenceError("backup manifest timestamp is in the future")
    expected_sha = values.get("sha256", "")
    if not SHA256_RE.fullmatch(expected_sha):
        raise EvidenceError("backup manifest sha256 is invalid")
    filename = values.get("file", "")
    if not SAFE_BACKUP_FILE_RE.fullmatch(filename) or Path(filename).name != filename:
        raise EvidenceError("backup manifest file must be a safe .sql.gz basename")
    backup_path = manifest_path.parent / filename
    actual_sha, actual_bytes = sha256_and_size(backup_path)
    try:
        byte_count = int(values.get("bytes", ""))
    except ValueError as exc:
        raise EvidenceError("backup manifest bytes is invalid") from exc
    size_matches = actual_bytes == byte_count
    hash_matches = actual_sha == expected_sha
    fresh = age <= max_age
    git_commit = values.get("git_commit")
    if git_commit:
        git_commit_display, git_commit_valid = public_commit(git_commit)
        if not git_commit_valid:
            raise EvidenceError("backup manifest git_commit is invalid")
    else:
        git_commit_display = None
    checks_ok = hash_matches and size_matches and fresh
    return {
        "status": "pass" if checks_ok else "fail",
        "contract": values["contract"],
        "created_at": format_utc(created),
        "age_seconds": int(age.total_seconds()),
        "max_age_seconds": int(max_age.total_seconds()),
        "file": filename,
        "sha256": expected_sha,
        "bytes": byte_count,
        "hash_matches": hash_matches,
        "size_matches": size_matches,
        "fresh": fresh,
        "git_commit": git_commit_display,
        "tables": require_exact_tables(values.get("tables", ""), source="backup manifest"),
    }


def collect_restore_evidence(
    *,
    proof_path: Path,
    backup: Mapping[str, Any],
    now: datetime,
    max_age: timedelta,
) -> dict[str, Any]:
    values = read_key_value_file(proof_path, allowed_keys=RESTORE_PROOF_KEYS)
    if values.get("contract") != "weltgewebe-postgres-restore-proof-v1":
        raise EvidenceError("restore proof contract is not supported")
    created = parse_utc(values.get("created_at", ""), field="restore created_at")
    age = now.astimezone(timezone.utc) - created
    if age.total_seconds() < 0:
        raise EvidenceError("restore proof timestamp is in the future")
    fresh = age <= max_age
    backup_created = parse_utc(str(backup.get("created_at", "")), field="selected backup created_at")
    not_before_backup = created >= backup_created
    backup_matches = (
        values.get("backup_file") == backup.get("file")
        and values.get("backup_sha256") == backup.get("sha256")
    )
    result_ok = values.get("result") == "ok"
    checks_ok = fresh and not_before_backup and backup_matches and result_ok
    return {
        "status": "pass" if checks_ok else "fail",
        "contract": values["contract"],
        "created_at": format_utc(created),
        "age_seconds": int(age.total_seconds()),
        "max_age_seconds": int(max_age.total_seconds()),
        "backup_file": values.get("backup_file"),
        "backup_sha256": values.get("backup_sha256"),
        "backup_matches_manifest": backup_matches,
        "not_before_backup": not_before_backup,
        "result": values.get("result"),
        "fresh": fresh,
        "tables": require_exact_tables(values.get("tables", ""), source="restore proof"),
    }


def collect_secondary_copy_evidence(
    *,
    manifest_path: Path | None,
    backup: Mapping[str, Any],
) -> dict[str, Any]:
    if manifest_path is None:
        return {
            "status": "not-provided",
            "kind": "secondary_copy",
            "required_for_overall_pass": False,
            "proves_offhost_boundary": False,
            "detail": "no secondary-copy manifest was supplied",
        }
    values = read_key_value_file(manifest_path, allowed_keys=BACKUP_MANIFEST_KEYS)
    if values.get("contract") != "weltgewebe-postgres-backup-v1":
        raise EvidenceError("secondary-copy manifest contract is not supported")
    copy_name = values.get("file", "")
    copy_sha_expected = values.get("sha256", "")
    if not SAFE_BACKUP_FILE_RE.fullmatch(copy_name) or Path(copy_name).name != copy_name:
        raise EvidenceError("secondary-copy manifest file must be a safe .sql.gz basename")
    if not SHA256_RE.fullmatch(copy_sha_expected):
        raise EvidenceError("secondary-copy manifest sha256 is invalid")
    try:
        copy_bytes_expected = int(values.get("bytes", ""))
    except ValueError as exc:
        raise EvidenceError("secondary-copy manifest bytes is invalid") from exc
    require_exact_tables(values.get("tables", ""), source="secondary-copy manifest")
    same_artifact = (
        copy_name == backup.get("file")
        and copy_sha_expected == backup.get("sha256")
        and copy_bytes_expected == backup.get("bytes")
        and values.get("created_at") == backup.get("created_at")
    )
    try:
        copy_sha, copy_bytes = sha256_and_size(manifest_path.parent / copy_name)
    except EvidenceError:
        hash_matches = False
    else:
        hash_matches = (
            copy_sha == copy_sha_expected
            and copy_bytes == copy_bytes_expected
        )
    ok = same_artifact and hash_matches
    return {
        "status": "pass" if ok else "fail",
        "kind": "secondary_copy",
        "required_for_overall_pass": False,
        "proves_offhost_boundary": False,
        "file": copy_name,
        "sha256": copy_sha_expected,
        "bytes": copy_bytes_expected,
        "same_artifact_as_production_manifest": same_artifact,
        "copied_file_hash_matches": hash_matches,
    }


def build_evidence(
    *,
    public: Mapping[str, Any],
    runtime: Mapping[str, Any],
    backup: Mapping[str, Any],
    restore: Mapping[str, Any],
    secondary_copy: Mapping[str, Any],
    generated_at: datetime,
) -> dict[str, Any]:
    required_sections = (public, runtime, backup, restore)
    required_ok = all(section.get("status") == "pass" for section in required_sections)
    if not required_ok or secondary_copy.get("status") == "fail":
        overall_status = "fail"
    else:
        overall_status = "partial"
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": EVIDENCE_KIND,
        "status": overall_status,
        "generated_at": format_utc(generated_at),
        "runtime_collection_read_only": True,
        "runtime_mutation_performed": False,
        "report_write_is_only_mutation": True,
        "values_redacted": True,
        "public": dict(public),
        "runtime_configuration": dict(runtime),
        "backup": dict(backup),
        "restore": dict(restore),
        "secondary_copy": dict(secondary_copy),
        "evidence_boundary": {
            "proves": [
                "public API readiness at collection time",
                "public web and API release identity at collection time",
                "allowlisted persistence and migration modes in the running API container",
                "integrity and freshness of the explicitly selected local backup",
                "fresh successful restore proof bound to that backup",
                "hash-identical secondary copy when a secondary-copy manifest is supplied",
            ],
            "does_not_prove": [
                "future availability",
                "absence of latent application defects",
                "completeness or semantic correctness of every database row",
                "off-host storage or recovery boundary",
                "disaster recovery for infrastructure outside the selected PostgreSQL artifacts",
            ],
        },
    }


def open_output_directory(path: Path) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    try:
        directory_fd = os.open(path.parent, flags)
    except FileNotFoundError as exc:
        raise EvidenceError(f"output parent directory does not exist: {path.parent}") from exc
    except OSError as exc:
        raise EvidenceError(
            f"output parent must be an existing non-symlink directory: {path.parent}"
        ) from exc
    directory_stat = os.fstat(directory_fd)
    if not stat.S_ISDIR(directory_stat.st_mode):
        os.close(directory_fd)
        raise EvidenceError(
            f"output parent must be an existing non-symlink directory: {path.parent}"
        )
    return directory_fd


def validate_existing_output_target(directory_fd: int, name: str, path: Path) -> None:
    try:
        target_stat = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise EvidenceError(f"could not inspect output target: {path}") from exc
    if stat.S_ISLNK(target_stat.st_mode) or not stat.S_ISREG(target_stat.st_mode):
        raise EvidenceError(f"output target must be absent or a regular non-symlink file: {path}")


def write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    name = path.name
    if name in {"", ".", ".."}:
        raise EvidenceError("output target must have a regular filename")
    try:
        directory_fd = open_output_directory(path)
        temp_name = f".{name}.{uuid.uuid4().hex}.tmp"
        temp_fd: int | None = None
        try:
            validate_existing_output_target(directory_fd, name, path)
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            temp_fd = os.open(temp_name, flags, 0o600, dir_fd=directory_fd)
            encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
            with os.fdopen(temp_fd, "wb") as handle:
                temp_fd = None
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
            os.fsync(directory_fd)
        finally:
            if temp_fd is not None:
                os.close(temp_fd)
            try:
                os.unlink(temp_name, dir_fd=directory_fd)
            except FileNotFoundError:
                pass
            os.close(directory_fd)
    except OSError as exc:
        raise EvidenceError(f"could not atomically write output: {path}") from exc


def positive_hours(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive number") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect redacted Weltgewebe production runtime evidence.")
    parser.add_argument("--domain", default="weltgewebe.net")
    parser.add_argument("--api-domain", default="api.weltgewebe.net")
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--docker-bin", default="docker")
    parser.add_argument("--project-name", default="weltgewebe")
    parser.add_argument("--env-file", type=Path, default=Path("/etc/weltgewebe/weltgewebe.env"))
    parser.add_argument(
        "--compose-file",
        action="append",
        type=Path,
        dest="compose_files",
        default=None,
        help="repeat for each compose file in deployment order",
    )
    parser.add_argument("--service", default="api")
    parser.add_argument("--backup-manifest", type=Path, required=True)
    parser.add_argument("--restore-proof", type=Path, required=True)
    secondary_copy_group = parser.add_mutually_exclusive_group()
    secondary_copy_group.add_argument("--secondary-copy-manifest", type=Path)
    secondary_copy_group.add_argument(
        "--offhost-backup-manifest",
        dest="secondary_copy_manifest",
        type=Path,
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--backup-max-age-hours", type=positive_hours, default=26.0)
    parser.add_argument("--restore-max-age-hours", type=positive_hours, default=192.0)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    compose_files = args.compose_files or [
        Path("infra/compose/compose.prod.yml"),
        Path("infra/compose/compose.vps.override.yml"),
    ]
    now = utc_now()
    try:
        public = collect_public_evidence(
            domain=args.domain,
            api_domain=args.api_domain,
            timeout=args.timeout,
        )
        runtime = collect_runtime_modes(
            compose_prefix=build_compose_prefix(
                docker_bin=args.docker_bin,
                project_name=args.project_name,
                env_file=args.env_file,
                compose_files=compose_files,
            ),
            service=args.service,
        )
        backup = collect_backup_evidence(
            manifest_path=args.backup_manifest,
            now=now,
            max_age=timedelta(hours=args.backup_max_age_hours),
        )
        restore = collect_restore_evidence(
            proof_path=args.restore_proof,
            backup=backup,
            now=now,
            max_age=timedelta(hours=args.restore_max_age_hours),
        )
        secondary_copy = collect_secondary_copy_evidence(
            manifest_path=args.secondary_copy_manifest,
            backup=backup,
        )
        payload = build_evidence(
            public=public,
            runtime=runtime,
            backup=backup,
            restore=restore,
            secondary_copy=secondary_copy,
            generated_at=now,
        )
    except EvidenceError as exc:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "kind": EVIDENCE_KIND,
            "status": "fail",
            "generated_at": format_utc(now),
            "runtime_collection_read_only": True,
            "runtime_mutation_performed": False,
            "report_write_is_only_mutation": True,
            "values_redacted": True,
            "error": str(exc),
        }

    if args.output:
        try:
            write_json_atomic(args.output, payload)
        except EvidenceError as exc:
            print(f"runtime evidence output failed: {exc}", file=sys.stderr)
            return 1
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    if payload["status"] == "pass":
        return 0
    if payload["status"] == "partial":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
