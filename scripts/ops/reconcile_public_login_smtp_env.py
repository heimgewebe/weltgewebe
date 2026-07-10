#!/usr/bin/env python3
"""Safely reconcile public-login and SMTP settings into the canonical VPS env.

The command is fail-closed and value-redacting:

* only an explicit allowlist of keys is copied;
* source values are canonicalized to the exact runtime vocabulary;
* dry-run is the default and performs the same trust checks as apply;
* apply requires the exact plan hash emitted by dry-run;
* source, destination, lock and backup paths are opened without following symlinks;
* output contains key names and file metadata, never values.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
import secrets
import stat
import sys
import time
from typing import Mapping, Protocol, Sequence


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
TLS_PORTS = {465, 587, 2525}
RECONCILE_MARKER = (
    "# Reconciled public-login and SMTP keys from the approved legacy runtime source."
)
PLAN_DOMAIN = b"weltgewebe-public-login-smtp-env-plan-v1\0"
PLAN_SHA256_RE = re.compile(r"[0-9a-f]{64}")
ASCII_PORT_RE = re.compile(r"[0-9]{1,5}")
INVALID_LINE_CHARS = frozenset("\r\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029")
TEMP_PREFIX_TEMPLATE = ".{name}.reconcile-"
LOCK_TIMEOUT_SECONDS = 15.0
LOCK_RETRY_SECONDS = 0.05


class ReconcileError(RuntimeError):
    """Raised for a safe, value-redacted reconciliation failure."""


@dataclass(frozen=True)
class EnvDocument:
    lines: tuple[str, ...]
    values: Mapping[str, str]


@dataclass(frozen=True)
class OpenedEnv:
    raw_bytes: bytes
    text: str
    file_stat: os.stat_result


class DigestWriter(Protocol):
    def update(self, data: bytes) -> None:
        """Add bytes to the digest state."""


def _key_from_line(raw: str) -> str | None:
    stripped = raw.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    left = stripped.split("=", 1)[0].strip()
    if left.startswith("export "):
        left = left[7:].strip()
    return left or None


def parse_env(text: str, *, label: str) -> EnvDocument:
    if any(character in text for character in INVALID_LINE_CHARS):
        raise ReconcileError(f"{label} contains an unsupported line separator")
    lines = tuple(text.split("\n"))
    values: dict[str, str] = {}
    for raw in lines:
        key = _key_from_line(raw)
        if key is None:
            continue
        if key in values:
            raise ReconcileError(f"duplicate key in {label}: {key}")
        values[key] = raw.strip().split("=", 1)[1].strip()
    return EnvDocument(lines=lines, values=values)


def _logical_scalar(raw: str, *, key: str) -> str:
    value = raw.strip()
    if not value:
        return ""
    first = value[0]
    last = value[-1]
    if first in {"'", '"'}:
        if len(value) < 2 or last != first:
            raise ReconcileError(f"malformed quoted value for key: {key}")
        return value[1:-1].strip()
    if last in {"'", '"'}:
        raise ReconcileError(f"malformed quoted value for key: {key}")
    return value


def validate_source(values: Mapping[str, str]) -> dict[str, str]:
    missing = [key for key in REQUIRED_SOURCE_KEYS if key not in values]
    if missing:
        raise ReconcileError(
            "required approved source keys missing: " + ", ".join(missing)
        )

    selected: dict[str, str] = {}

    public_login = _logical_scalar(values["AUTH_PUBLIC_LOGIN"], key="AUTH_PUBLIC_LOGIN")
    if public_login == "1" or public_login.lower() == "true":
        selected["AUTH_PUBLIC_LOGIN"] = "1"
    else:
        raise ReconcileError("AUTH_PUBLIC_LOGIN is not enabled in the source")

    raw_magic_log = values.get("AUTH_LOG_MAGIC_TOKEN", "0")
    magic_log = _logical_scalar(raw_magic_log, key="AUTH_LOG_MAGIC_TOKEN")
    if magic_log == "0" or magic_log.lower() == "false":
        selected["AUTH_LOG_MAGIC_TOKEN"] = "0"
    else:
        raise ReconcileError("AUTH_LOG_MAGIC_TOKEN is not disabled in the source")

    smtp_auth = _logical_scalar(values["SMTP_AUTH"], key="SMTP_AUTH")
    if smtp_auth.lower() != "on":
        raise ReconcileError("SMTP_AUTH must be exactly 'on' in the source")
    selected["SMTP_AUTH"] = "on"

    port_text = _logical_scalar(values["SMTP_PORT"], key="SMTP_PORT")
    if not ASCII_PORT_RE.fullmatch(port_text):
        raise ReconcileError("SMTP_PORT must contain ASCII digits only")
    smtp_port = int(port_text)
    if smtp_port not in TLS_PORTS:
        raise ReconcileError("SMTP_PORT is not an approved TLS submission port")
    selected["SMTP_PORT"] = str(smtp_port)

    for key in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS", "SMTP_FROM"):
        raw_value = values[key].strip()
        if not _logical_scalar(raw_value, key=key):
            raise ReconcileError(f"{key} is empty in the source")
        selected[key] = raw_value

    return {key: selected[key] for key in APPROVED_KEYS}


def changed_keys(destination: EnvDocument, selected: Mapping[str, str]) -> list[str]:
    return [
        key for key in APPROVED_KEYS if destination.values.get(key) != selected[key]
    ]


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
    kept.extend(("", RECONCILE_MARKER))
    kept.extend(f"{key}={selected[key]}" for key in APPROVED_KEYS)
    return "\n".join(kept) + "\n"


def _update_plan_field(digest: DigestWriter, label: str, value: bytes) -> None:
    label_bytes = label.encode("utf-8")
    digest.update(len(label_bytes).to_bytes(4, "big"))
    digest.update(label_bytes)
    digest.update(len(value).to_bytes(8, "big"))
    digest.update(value)


def _stat_plan_fields(
    prefix: str, file_stat: os.stat_result
) -> tuple[tuple[str, bytes], ...]:
    return tuple(
        (f"{prefix}_{name}", str(value).encode("ascii"))
        for name, value in (
            ("device", file_stat.st_dev),
            ("inode", file_stat.st_ino),
            ("uid", file_stat.st_uid),
            ("gid", file_stat.st_gid),
            ("mode", stat.S_IMODE(file_stat.st_mode)),
        )
    )


def plan_sha256(
    *,
    source_path: Path,
    destination_path: Path,
    backup_dir: Path,
    source_stat: os.stat_result,
    destination_stat: os.stat_result,
    backup_dir_stat: os.stat_result,
    source_text: str,
    destination_text: str,
    planned_content: str,
) -> str:
    digest = hashlib.sha256()
    digest.update(PLAN_DOMAIN)
    fields: list[tuple[str, bytes]] = [
        ("source_path", os.fsencode(source_path)),
        ("destination_path", os.fsencode(destination_path)),
        ("backup_dir", os.fsencode(backup_dir)),
        ("source_text", source_text.encode("utf-8")),
        ("destination_text", destination_text.encode("utf-8")),
        ("planned_content", planned_content.encode("utf-8")),
    ]
    fields.extend(_stat_plan_fields("source", source_stat))
    fields.extend(_stat_plan_fields("destination", destination_stat))
    fields.extend(_stat_plan_fields("backup_dir", backup_dir_stat))
    for label, value in fields:
        _update_plan_field(digest, label, value)
    return digest.hexdigest()


def _normalize_absolute_path(path: Path, *, label: str) -> Path:
    if not path.is_absolute():
        raise ReconcileError(f"{label} path must be absolute")
    if any(part in {".", ".."} for part in path.parts[1:]):
        raise ReconcileError(f"{label} path must be normalized")
    return path


def _directory_open_flags() -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    return flags


def _file_open_flags() -> int:
    flags = os.O_RDONLY | os.O_NOFOLLOW
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    return flags


def _validate_root_owned_stat(file_stat: os.stat_result, *, label: str) -> None:
    if file_stat.st_uid != 0:
        raise ReconcileError(f"{label} must be root-owned")
    if stat.S_IMODE(file_stat.st_mode) & (stat.S_IWGRP | stat.S_IWOTH):
        raise ReconcileError(f"{label} must not be writable by group or others")


def _open_trusted_directory(
    path: Path,
    *,
    label: str,
    require_root: bool,
    exact_mode: int | None = None,
) -> int:
    normalized = _normalize_absolute_path(path, label=label)
    current_fd = os.open("/", _directory_open_flags())
    try:
        root_stat = os.fstat(current_fd)
        if not stat.S_ISDIR(root_stat.st_mode):
            raise ReconcileError("filesystem root is not a directory")
        if require_root:
            _validate_root_owned_stat(root_stat, label="filesystem root")
        for part in normalized.parts[1:]:
            try:
                next_fd = os.open(part, _directory_open_flags(), dir_fd=current_fd)
            except OSError as exc:
                raise ReconcileError(f"unable to open {label} safely: {path}") from exc
            os.close(current_fd)
            current_fd = next_fd
            current_stat = os.fstat(current_fd)
            if not stat.S_ISDIR(current_stat.st_mode):
                raise ReconcileError(f"{label} is not a directory: {path}")
            if require_root:
                _validate_root_owned_stat(current_stat, label=label)

        final_stat = os.fstat(current_fd)
        if exact_mode is not None and stat.S_IMODE(final_stat.st_mode) != exact_mode:
            raise ReconcileError(f"{label} must have mode {exact_mode:04o}")
        return current_fd
    except Exception:
        os.close(current_fd)
        raise


def _read_regular_at(
    parent_fd: int,
    name: str,
    *,
    label: str,
    require_root: bool,
) -> OpenedEnv:
    if not name or "/" in name or name in {".", ".."}:
        raise ReconcileError(f"invalid {label} filename")
    try:
        fd = os.open(name, _file_open_flags(), dir_fd=parent_fd)
    except OSError as exc:
        raise ReconcileError(f"unable to open {label} safely") from exc
    try:
        file_stat = os.fstat(fd)
        if not stat.S_ISREG(file_stat.st_mode):
            raise ReconcileError(f"{label} is not a regular file")
        if require_root:
            _validate_root_owned_stat(file_stat, label=label)
        with os.fdopen(fd, "rb", closefd=False) as handle:
            raw_bytes = handle.read()
        text = raw_bytes.decode("utf-8", errors="strict")
        return OpenedEnv(raw_bytes=raw_bytes, text=text, file_stat=file_stat)
    except UnicodeDecodeError as exc:
        raise ReconcileError(f"{label} is not valid UTF-8") from exc
    finally:
        os.close(fd)


def _same_file(left: os.stat_result, right: os.stat_result) -> bool:
    return left.st_dev == right.st_dev and left.st_ino == right.st_ino


def _write_file_exclusive_at(
    directory_fd: int,
    name: str,
    content: bytes,
    *,
    uid: int,
    gid: int,
) -> os.stat_result:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    fd = os.open(name, flags, 0o600, dir_fd=directory_fd)
    try:
        with os.fdopen(fd, "wb", closefd=False) as handle:
            handle.write(content)
            handle.flush()
            os.fchown(fd, uid, gid)
            os.fchmod(fd, 0o600)
            os.fsync(fd)
        return os.fstat(fd)
    except BaseException:
        try:
            os.unlink(name, dir_fd=directory_fd)
            os.fsync(directory_fd)
        except FileNotFoundError:
            # The entry was already absent, so no partial secret file remains.
            pass
        raise
    finally:
        os.close(fd)


def _cleanup_orphan_temps(
    directory_fd: int,
    *,
    prefix: str,
    expected_uid: int,
    expected_gid: int,
) -> None:
    for name in os.listdir(directory_fd):
        if not name.startswith(prefix):
            continue
        try:
            fd = os.open(name, _file_open_flags(), dir_fd=directory_fd)
        except OSError:
            continue
        try:
            file_stat = os.fstat(fd)
            safe = (
                stat.S_ISREG(file_stat.st_mode)
                and file_stat.st_uid == expected_uid
                and file_stat.st_gid == expected_gid
                and stat.S_IMODE(file_stat.st_mode) == 0o600
            )
        finally:
            os.close(fd)
        if safe:
            # The name can only be swapped by a writer to the already validated
            # trusted directory; production directories are root-owned and not
            # writable by group or others, and cleanup runs while holding the lock.
            os.unlink(name, dir_fd=directory_fd)
    os.fsync(directory_fd)


def _acquire_exclusive_lock(lock_fd: int) -> None:
    deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
    while True:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError as exc:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ReconcileError(
                    "timed out waiting for reconciliation lock"
                ) from exc
            time.sleep(min(LOCK_RETRY_SECONDS, remaining))


def _validate_expected_plan(expected_plan_sha256: str | None) -> str:
    if expected_plan_sha256 is None:
        raise ReconcileError("--apply requires --expected-plan-sha256 from dry-run")
    normalized = expected_plan_sha256.strip().lower()
    if not PLAN_SHA256_RE.fullmatch(normalized):
        raise ReconcileError("expected plan SHA-256 is invalid")
    return normalized


def reconcile(
    *,
    source_path: Path,
    destination_path: Path,
    backup_dir: Path,
    apply: bool,
    expected_plan_sha256: str | None = None,
    require_root: bool = True,
) -> dict[str, object]:
    source = _normalize_absolute_path(source_path, label="source")
    destination = _normalize_absolute_path(destination_path, label="destination")
    backup = _normalize_absolute_path(backup_dir, label="backup directory")

    if source.name == "" or destination.name == "":
        raise ReconcileError("source and destination must name regular files")
    if require_root and os.geteuid() != 0:
        raise ReconcileError("dry-run and apply require root")

    source_dir_fd: int | None = None
    destination_dir_fd: int | None = None
    backup_dir_fd: int | None = None
    lock_fd: int | None = None
    try:
        source_dir_fd = _open_trusted_directory(
            source.parent, label="source parent directory", require_root=require_root
        )
        destination_dir_fd = _open_trusted_directory(
            destination.parent,
            label="destination parent directory",
            require_root=require_root,
        )
        initial_source = _read_regular_at(
            source_dir_fd, source.name, label="source", require_root=require_root
        )
        initial_destination = _read_regular_at(
            destination_dir_fd,
            destination.name,
            label="destination",
            require_root=require_root,
        )
        if _same_file(initial_source.file_stat, initial_destination.file_stat):
            raise ReconcileError("source and destination must be different files")

        backup_dir_fd = _open_trusted_directory(
            backup,
            label="backup directory",
            require_root=require_root,
            exact_mode=0o700,
        )
        backup_dir_stat = os.fstat(backup_dir_fd)

        selected = validate_source(
            parse_env(initial_source.text, label="source").values
        )
        destination_document = parse_env(initial_destination.text, label="destination")
        planned_content = build_reconciled_content(initial_destination.text, selected)
        current_plan_sha256 = plan_sha256(
            source_path=source,
            destination_path=destination,
            backup_dir=backup,
            source_stat=initial_source.file_stat,
            destination_stat=initial_destination.file_stat,
            backup_dir_stat=backup_dir_stat,
            source_text=initial_source.text,
            destination_text=initial_destination.text,
            planned_content=planned_content,
        )
        initial_changed_keys = changed_keys(destination_document, selected)

        if apply:
            expected = _validate_expected_plan(expected_plan_sha256)
            if expected != current_plan_sha256:
                raise ReconcileError(
                    "expected plan SHA-256 does not match current inputs"
                )

        base_result: dict[str, object] = {
            "destination": str(destination),
            "updated_keys": initial_changed_keys,
            "values_redacted": True,
            "plan_sha256": current_plan_sha256,
        }
        if planned_content == initial_destination.text:
            return {**base_result, "status": "already_reconciled", "applied": False}

        if not apply:
            return {**base_result, "status": "planned", "applied": False}

        lock_name = f".{destination.name}.reconcile.lock"
        lock_flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW
        if hasattr(os, "O_CLOEXEC"):
            lock_flags |= os.O_CLOEXEC
        lock_fd = os.open(lock_name, lock_flags, 0o600, dir_fd=destination_dir_fd)
        lock_stat = os.fstat(lock_fd)
        if not stat.S_ISREG(lock_stat.st_mode):
            raise ReconcileError("reconciliation lock is not a regular file")
        if require_root:
            _validate_root_owned_stat(lock_stat, label="reconciliation lock")
        _acquire_exclusive_lock(lock_fd)

        current_source = _read_regular_at(
            source_dir_fd, source.name, label="source", require_root=require_root
        )
        current_destination = _read_regular_at(
            destination_dir_fd,
            destination.name,
            label="destination",
            require_root=require_root,
        )
        if not _same_file(initial_source.file_stat, current_source.file_stat):
            raise ReconcileError("source file identity changed during reconciliation")
        if not _same_file(initial_destination.file_stat, current_destination.file_stat):
            raise ReconcileError(
                "destination file identity changed during reconciliation"
            )
        if _same_file(current_source.file_stat, current_destination.file_stat):
            raise ReconcileError("source and destination must be different files")
        if initial_source.text != current_source.text:
            raise ReconcileError("source content changed during reconciliation")
        if initial_destination.text != current_destination.text:
            raise ReconcileError("destination content changed during reconciliation")

        selected = validate_source(
            parse_env(current_source.text, label="source").values
        )
        current_destination_document = parse_env(
            current_destination.text, label="destination"
        )
        current_content = build_reconciled_content(current_destination.text, selected)
        locked_plan_sha256 = plan_sha256(
            source_path=source,
            destination_path=destination,
            backup_dir=backup,
            source_stat=current_source.file_stat,
            destination_stat=current_destination.file_stat,
            backup_dir_stat=os.fstat(backup_dir_fd),
            source_text=current_source.text,
            destination_text=current_destination.text,
            planned_content=current_content,
        )
        if locked_plan_sha256 != current_plan_sha256:
            raise ReconcileError("reconciliation plan changed after lock")
        if expected != locked_plan_sha256:
            raise ReconcileError("expected plan SHA-256 changed after lock")

        updated_keys = changed_keys(current_destination_document, selected)
        destination_stat = current_destination.file_stat
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        backup_name = f"{destination.name}.bak-{timestamp}-{os.getpid()}"
        _write_file_exclusive_at(
            backup_dir_fd,
            backup_name,
            current_destination.raw_bytes,
            uid=destination_stat.st_uid,
            gid=destination_stat.st_gid,
        )
        os.fsync(backup_dir_fd)
        try:
            verified_backup = _read_regular_at(
                backup_dir_fd,
                backup_name,
                label="backup",
                require_root=require_root,
            )
            backup_mode = stat.S_IMODE(verified_backup.file_stat.st_mode)
            if (
                verified_backup.raw_bytes != current_destination.raw_bytes
                or verified_backup.file_stat.st_uid != destination_stat.st_uid
                or verified_backup.file_stat.st_gid != destination_stat.st_gid
                or backup_mode != 0o600
            ):
                raise ReconcileError(
                    "backup verification failed before destination replace"
                )
        except BaseException:
            try:
                os.unlink(backup_name, dir_fd=backup_dir_fd)
                os.fsync(backup_dir_fd)
            except FileNotFoundError:
                # The backup is already absent, so rollback cleanup is complete.
                pass
            raise

        temp_prefix = TEMP_PREFIX_TEMPLATE.format(name=destination.name)
        _cleanup_orphan_temps(
            destination_dir_fd,
            prefix=temp_prefix,
            expected_uid=destination_stat.st_uid,
            expected_gid=destination_stat.st_gid,
        )
        temp_name = f"{temp_prefix}{secrets.token_hex(12)}"
        temp_created = False
        try:
            _write_file_exclusive_at(
                destination_dir_fd,
                temp_name,
                current_content.encode("utf-8"),
                uid=destination_stat.st_uid,
                gid=destination_stat.st_gid,
            )
            temp_created = True
            os.replace(
                temp_name,
                destination.name,
                src_dir_fd=destination_dir_fd,
                dst_dir_fd=destination_dir_fd,
            )
            temp_created = False
            os.fsync(destination_dir_fd)
        finally:
            if temp_created:
                os.unlink(temp_name, dir_fd=destination_dir_fd)

        final_destination = _read_regular_at(
            destination_dir_fd,
            destination.name,
            label="destination",
            require_root=require_root,
        )
        if final_destination.text != current_content:
            raise ReconcileError("destination verification failed after atomic replace")
        final_stat = final_destination.file_stat
        return {
            "destination": str(destination),
            "updated_keys": updated_keys,
            "values_redacted": True,
            "plan_sha256": locked_plan_sha256,
            "status": "reconciled",
            "applied": True,
            "backup": str(backup / backup_name),
            "mode": f"{stat.S_IMODE(final_stat.st_mode):04o}",
            "owner_uid": final_stat.st_uid,
            "owner_gid": final_stat.st_gid,
        }
    finally:
        if lock_fd is not None:
            os.close(lock_fd)
        if backup_dir_fd is not None:
            os.close(backup_dir_fd)
        if destination_dir_fd is not None:
            os.close(destination_dir_fd)
        if source_dir_fd is not None:
            os.close(source_dir_fd)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--backup-dir", type=Path, required=True)
    parser.add_argument(
        "--apply", action="store_true", help="write after a matching dry-run plan"
    )
    parser.add_argument(
        "--expected-plan-sha256",
        help="plan_sha256 from the immediately preceding dry-run; required with --apply",
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
            expected_plan_sha256=args.expected_plan_sha256,
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
        print(f"Plan SHA-256: {result['plan_sha256']}")
        if result.get("backup"):
            print(f"Backup: {result['backup']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
