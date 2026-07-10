#!/usr/bin/env python3
"""Safely reconcile public-login and SMTP settings into the canonical VPS env.

The command is fail-closed and value-redacting:

* only an explicit allowlist of keys is copied;
* source values are validated before any write;
* dry-run is the default;
* applying requires root, an exclusive lock, and a durable backup;
* output contains key names and file metadata, never values.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import stat
import sys
import tempfile
from typing import Mapping, Sequence


APPROVED_KEYS: tuple[str, ...] = (
    "AUTH_PUBLIC_LOGIN",
    "AUTH_LOG_MAGIC_TOKEN",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_AUTH",
    "SMTP_USER",
    "SMTP_PASS",
    "SMTP_FROM",
)
REQUIRED_SOURCE_KEYS: tuple[str, ...] = (
    "AUTH_PUBLIC_LOGIN",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_AUTH",
    "SMTP_USER",
    "SMTP_PASS",
    "SMTP_FROM",
)
FALSE_VALUES = {"0", "false", "no", "off"}
TRUE_VALUES = {"1", "true", "yes", "on"}
TLS_PORTS = {465, 587, 2525}
RECONCILE_MARKER = (
    "# Reconciled public-login and SMTP keys from the approved legacy runtime source."
)


class ReconcileError(RuntimeError):
    """Raised for a safe, value-redacted reconciliation failure."""


@dataclass(frozen=True)
class EnvDocument:
    lines: tuple[str, ...]
    values: Mapping[str, str]


def _key_from_line(raw: str) -> str | None:
    stripped = raw.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    left = stripped.split("=", 1)[0].strip()
    if left.startswith("export "):
        left = left[7:].strip()
    return left or None


def parse_env(text: str, *, label: str) -> EnvDocument:
    lines = tuple(text.splitlines())
    values: dict[str, str] = {}
    for raw in lines:
        key = _key_from_line(raw)
        if key is None:
            continue
        if key in values:
            raise ReconcileError(f"duplicate key in {label}: {key}")
        values[key] = raw.strip().split("=", 1)[1].strip()
    return EnvDocument(lines=lines, values=values)


def _normalized(value: str) -> str:
    return value.strip().strip('"').strip("'").strip().lower()


def validate_source(values: Mapping[str, str]) -> dict[str, str]:
    missing = [key for key in REQUIRED_SOURCE_KEYS if not values.get(key)]
    if missing:
        raise ReconcileError(
            "required approved source keys missing: " + ", ".join(missing)
        )

    selected = {key: values[key] for key in APPROVED_KEYS if values.get(key)}
    selected.setdefault("AUTH_LOG_MAGIC_TOKEN", "0")

    if _normalized(selected["AUTH_PUBLIC_LOGIN"]) not in TRUE_VALUES:
        raise ReconcileError("AUTH_PUBLIC_LOGIN is not enabled in the source")
    if _normalized(selected["AUTH_LOG_MAGIC_TOKEN"]) not in FALSE_VALUES:
        raise ReconcileError("AUTH_LOG_MAGIC_TOKEN is not disabled in the source")
    if _normalized(selected["SMTP_AUTH"]) not in TRUE_VALUES:
        raise ReconcileError("SMTP_AUTH is not enabled in the source")

    try:
        smtp_port = int(_normalized(selected["SMTP_PORT"]))
    except ValueError as exc:
        raise ReconcileError("SMTP_PORT is not numeric in the source") from exc
    if smtp_port not in TLS_PORTS:
        raise ReconcileError("SMTP_PORT is not an approved TLS submission port")

    for key in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS", "SMTP_FROM"):
        if not _normalized(selected[key]):
            raise ReconcileError(f"{key} is empty in the source")

    return {key: selected[key] for key in APPROVED_KEYS}


def build_reconciled_content(destination_text: str, selected: Mapping[str, str]) -> str:
    destination = parse_env(destination_text, label="destination")
    selected_keys = set(selected)
    kept = [
        line
        for line in destination.lines
        if _key_from_line(line) not in selected_keys
        and line.strip() != RECONCILE_MARKER
    ]
    while kept and kept[-1] == "":
        kept.pop()
    kept.extend(
        (
            "",
            RECONCILE_MARKER,
        )
    )
    kept.extend(f"{key}={selected[key]}" for key in APPROVED_KEYS)
    return "\n".join(kept) + "\n"


def _checked_regular_absolute(path: Path, *, label: str) -> Path:
    if not path.is_absolute():
        raise ReconcileError(f"{label} path must be absolute")
    if path.is_symlink():
        raise ReconcileError(f"{label} must not be a symlink")
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ReconcileError(f"{label} does not exist: {path}") from exc
    if not resolved.is_file():
        raise ReconcileError(f"{label} is not a regular file: {path}")
    return resolved


def _validate_root_owned_runtime_file(path: Path, *, label: str) -> None:
    path_stat = path.stat()
    if path_stat.st_uid != 0:
        raise ReconcileError(f"{label} must be root-owned for --apply")
    if stat.S_IMODE(path_stat.st_mode) & (stat.S_IWGRP | stat.S_IWOTH):
        raise ReconcileError(
            f"{label} must not be writable by group or others for --apply"
        )


def _write_file_exclusive(path: Path, content: bytes, *, uid: int, gid: int) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb", closefd=False) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.fchown(fd, uid, gid)
        os.fchmod(fd, 0o600)
        os.fsync(fd)
    finally:
        os.close(fd)


def reconcile(
    *,
    source_path: Path,
    destination_path: Path,
    backup_dir: Path,
    apply: bool,
    require_root: bool = True,
) -> dict[str, object]:
    source = _checked_regular_absolute(source_path, label="source")
    destination = _checked_regular_absolute(destination_path, label="destination")
    if os.path.samefile(source, destination):
        raise ReconcileError("source and destination must be different files")
    if not backup_dir.is_absolute():
        raise ReconcileError("backup directory path must be absolute")

    source_text = source.read_text(encoding="utf-8")
    destination_text = destination.read_text(encoding="utf-8")
    selected = validate_source(parse_env(source_text, label="source").values)
    planned_content = build_reconciled_content(destination_text, selected)

    base_result: dict[str, object] = {
        "destination": str(destination),
        "updated_keys": list(APPROVED_KEYS),
        "values_redacted": True,
    }
    if planned_content == destination_text:
        return {**base_result, "status": "already_reconciled", "applied": False}
    if not apply:
        return {**base_result, "status": "planned", "applied": False}
    if require_root and os.geteuid() != 0:
        raise ReconcileError("--apply requires root")
    if require_root:
        _validate_root_owned_runtime_file(source, label="source")
        _validate_root_owned_runtime_file(destination, label="destination")

    if backup_dir.is_symlink():
        raise ReconcileError("backup directory must not be a symlink")
    backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    if backup_dir.is_symlink() or not backup_dir.is_dir():
        raise ReconcileError("backup directory is not a regular directory")
    backup_dir_stat = backup_dir.stat()
    if require_root and backup_dir_stat.st_uid != 0:
        raise ReconcileError("backup directory must be root-owned")
    os.chmod(backup_dir, 0o700)

    lock_path = destination.parent / f".{destination.name}.reconcile.lock"
    lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)

        # Re-resolve and re-read both files after acquiring the lock. This keeps
        # an apply operation from using stale source values or silently replacing
        # a destination path that another root operator changed after dry-run.
        current_source = _checked_regular_absolute(source_path, label="source")
        current_destination = _checked_regular_absolute(
            destination_path, label="destination"
        )
        if current_source != source:
            raise ReconcileError("source path changed during reconciliation")
        if current_destination != destination:
            raise ReconcileError("destination path changed during reconciliation")
        if os.path.samefile(current_source, current_destination):
            raise ReconcileError("source and destination must be different files")

        current_source_text = current_source.read_text(encoding="utf-8")
        selected = validate_source(
            parse_env(current_source_text, label="source").values
        )
        current_text = current_destination.read_text(encoding="utf-8")
        current_content = build_reconciled_content(current_text, selected)
        if current_content == current_text:
            return {**base_result, "status": "already_reconciled", "applied": False}

        destination_stat = destination.stat()
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        backup = backup_dir / f"{destination.name}.bak-{timestamp}-{os.getpid()}"
        _write_file_exclusive(
            backup,
            current_text.encode("utf-8"),
            uid=destination_stat.st_uid,
            gid=destination_stat.st_gid,
        )
        backup_dir_fd = os.open(backup_dir, os.O_DIRECTORY)
        try:
            os.fsync(backup_dir_fd)
        finally:
            os.close(backup_dir_fd)

        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{destination.name}.", dir=destination.parent
        )
        tmp = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(current_content)
                handle.flush()
                os.fchown(
                    handle.fileno(), destination_stat.st_uid, destination_stat.st_gid
                )
                os.fchmod(handle.fileno(), 0o600)
                os.fsync(handle.fileno())
            os.replace(tmp, destination)
            dir_fd = os.open(destination.parent, os.O_DIRECTORY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        finally:
            if tmp.exists():
                tmp.unlink()

        final_stat = destination.stat()
        return {
            **base_result,
            "status": "reconciled",
            "applied": True,
            "backup": str(backup),
            "mode": f"{stat.S_IMODE(final_stat.st_mode):04o}",
            "owner_uid": final_stat.st_uid,
            "owner_gid": final_stat.st_gid,
        }
    finally:
        os.close(lock_fd)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--backup-dir", type=Path, required=True)
    parser.add_argument(
        "--apply", action="store_true", help="write after validation; otherwise dry-run"
    )
    parser.add_argument(
        "--json", action="store_true", help="emit a value-redacted JSON receipt"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = reconcile(
            source_path=args.source,
            destination_path=args.destination,
            backup_dir=args.backup_dir,
            apply=args.apply,
        )
    except (OSError, ReconcileError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(f"Status: {result['status']}")
        print(f"Destination: {result['destination']}")
        print("Updated keys: " + ", ".join(result["updated_keys"]))
        if result.get("backup"):
            print(f"Backup: {result['backup']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
