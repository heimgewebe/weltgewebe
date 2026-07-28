#!/usr/bin/env python3
"""Canonical secure JSON receipt I/O for Weltgewebe production tooling."""

from __future__ import annotations

import json
import os
import secrets
import stat
from pathlib import Path
from typing import Any

DEFAULT_MAX_BYTES = 1024 * 1024


class SecureReceiptError(ValueError):
    """Base class for fail-closed receipt errors."""


class SecureMetadataError(SecureReceiptError):
    """The path metadata cannot establish a safe receipt boundary."""


class SecurePayloadError(SecureReceiptError):
    """The path is safe, but its payload is invalid."""


def _required_flag(name: str) -> int:
    value = getattr(os, name, None)
    if not isinstance(value, int):
        raise SecureMetadataError(f"required open flag is unavailable: {name}")
    return value


def _open_secure_directory(
    path: Path,
    *,
    expected_uid: int,
    forbidden_mode_bits: int,
) -> int:
    flags = (
        os.O_RDONLY
        | _required_flag("O_DIRECTORY")
        | _required_flag("O_CLOEXEC")
        | _required_flag("O_NOFOLLOW")
    )
    try:
        directory_fd = os.open(path, flags)
    except OSError as exc:
        raise SecureMetadataError(f"receipt directory cannot be opened safely: {path}: {exc}") from exc
    metadata = os.fstat(directory_fd)
    if not stat.S_ISDIR(metadata.st_mode):
        os.close(directory_fd)
        raise SecureMetadataError(f"receipt directory is not a directory: {path}")
    if metadata.st_uid != expected_uid:
        os.close(directory_fd)
        raise SecureMetadataError(f"receipt directory has unexpected owner: {path}")
    if metadata.st_mode & forbidden_mode_bits:
        os.close(directory_fd)
        raise SecureMetadataError(f"receipt directory has unsafe mode: {path}")
    return directory_fd


def validate_secure_directory(
    path: Path | str,
    *,
    expected_uid: int = 0,
    forbidden_mode_bits: int = 0o022,
) -> None:
    """Validate one directory without following its final symlink."""

    directory_fd = _open_secure_directory(
        Path(path),
        expected_uid=expected_uid,
        forbidden_mode_bits=forbidden_mode_bits,
    )
    os.close(directory_fd)


def read_secure_json(
    path: Path | str,
    *,
    expected_uid: int = 0,
    forbidden_mode_bits: int = 0o022,
    max_bytes: int = DEFAULT_MAX_BYTES,
    missing_ok: bool = False,
    require_object: bool = True,
) -> Any:
    """Read bounded JSON through directory- and descriptor-bound checks."""

    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    receipt_path = Path(path)
    directory_fd = _open_secure_directory(
        receipt_path.parent,
        expected_uid=expected_uid,
        forbidden_mode_bits=forbidden_mode_bits,
    )
    try:
        flags = os.O_RDONLY | _required_flag("O_CLOEXEC") | _required_flag("O_NOFOLLOW")
        try:
            file_fd = os.open(receipt_path.name, flags, dir_fd=directory_fd)
        except FileNotFoundError:
            if missing_ok:
                return None
            raise
        except OSError as exc:
            raise SecureMetadataError(f"receipt cannot be opened safely: {receipt_path}: {exc}") from exc
        try:
            metadata = os.fstat(file_fd)
            if not stat.S_ISREG(metadata.st_mode):
                raise SecureMetadataError(f"receipt is not a regular file: {receipt_path}")
            if metadata.st_uid != expected_uid:
                raise SecureMetadataError(f"receipt has unexpected owner: {receipt_path}")
            if metadata.st_mode & forbidden_mode_bits:
                raise SecureMetadataError(f"receipt has unsafe mode: {receipt_path}")
            if metadata.st_nlink != 1:
                raise SecureMetadataError(f"receipt has unexpected link count: {receipt_path}")
            if metadata.st_size > max_bytes:
                raise SecureMetadataError(f"receipt exceeds the byte limit: {receipt_path}")

            chunks: list[bytes] = []
            remaining = max_bytes + 1
            while remaining > 0:
                chunk = os.read(file_fd, min(65536, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            raw = b"".join(chunks)
            if len(raw) > max_bytes:
                raise SecureMetadataError(f"receipt exceeds the byte limit: {receipt_path}")
        finally:
            os.close(file_fd)
    finally:
        os.close(directory_fd)

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SecurePayloadError(f"receipt payload is invalid: {receipt_path}: {exc}") from exc
    if require_object and not isinstance(payload, dict):
        raise SecurePayloadError(f"receipt payload is not an object: {receipt_path}")
    return payload


def write_secure_json(
    path: Path | str,
    payload: Any,
    *,
    expected_uid: int = 0,
    forbidden_directory_mode_bits: int = 0o022,
    mode: int = 0o600,
    max_bytes: int = DEFAULT_MAX_BYTES,
    ensure_ascii: bool = True,
) -> None:
    """Atomically replace one JSON receipt through a secure directory descriptor."""

    if mode != 0o600:
        raise ValueError("secure receipts require mode 0600")
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    receipt_path = Path(path)
    try:
        encoded = (
            json.dumps(
                payload,
                ensure_ascii=ensure_ascii,
                sort_keys=True,
                indent=2,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise SecurePayloadError(f"receipt payload is not serializable: {exc}") from exc
    if len(encoded) > max_bytes:
        raise SecurePayloadError("receipt payload exceeds the byte limit")

    directory_fd = _open_secure_directory(
        receipt_path.parent,
        expected_uid=expected_uid,
        forbidden_mode_bits=forbidden_directory_mode_bits,
    )
    temporary_name = f".{receipt_path.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp"
    temporary_created = False
    try:
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | _required_flag("O_CLOEXEC")
            | _required_flag("O_NOFOLLOW")
        )
        file_fd = os.open(temporary_name, flags, mode, dir_fd=directory_fd)
        temporary_created = True
        try:
            os.fchmod(file_fd, mode)
            offset = 0
            while offset < len(encoded):
                written = os.write(file_fd, encoded[offset:])
                if written <= 0:
                    raise OSError("short write while storing receipt")
                offset += written
            os.fsync(file_fd)
            metadata = os.fstat(file_fd)
            if not stat.S_ISREG(metadata.st_mode):
                raise SecureMetadataError("temporary receipt is not a regular file")
            if metadata.st_uid != expected_uid:
                raise SecureMetadataError("temporary receipt has unexpected owner")
            if metadata.st_nlink != 1:
                raise SecureMetadataError("temporary receipt has unexpected link count")
            if metadata.st_mode & 0o777 != mode:
                raise SecureMetadataError("temporary receipt has unexpected mode")
        finally:
            os.close(file_fd)

        os.replace(
            temporary_name,
            receipt_path.name,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
        )
        temporary_created = False
        os.fsync(directory_fd)
    finally:
        if temporary_created:
            try:
                os.unlink(temporary_name, dir_fd=directory_fd)
            except FileNotFoundError:
                pass
        os.close(directory_fd)
