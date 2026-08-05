#!/usr/bin/env python3
"""Provision the production Web Push VAPID identity without exposing it."""

from __future__ import annotations

import argparse
import base64
import binascii
import ipaddress
import os
import re
import secrets
import stat
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

MAX_ENV_BYTES = 1_048_576
P256_ORDER = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
PRIVATE_KEY_NAME = "WEB_PUSH_VAPID_PRIVATE_KEY"
CONTACT_NAME = "WEB_PUSH_VAPID_CONTACT"
ALLOWED_HOSTS_NAME = "WEB_PUSH_ALLOWED_HOST_SUFFIXES"
BOOTSTRAP_MODE_NAME = "WEB_PUSH_VAPID_BOOTSTRAP_MODE"
TARGET_NAMES = (PRIVATE_KEY_NAME, CONTACT_NAME, ALLOWED_HOSTS_NAME)
TRACKED_NAMES = TARGET_NAMES + (BOOTSTRAP_MODE_NAME,)
DEFAULT_CONTACT = "mailto:kontakt@weltweberei.org"
DEFAULT_ALLOWED_HOST_SUFFIXES = (
    "fcm.googleapis.com,push.services.mozilla.com,web.push.apple.com"
)
BASE64URL_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class WebPushEnvError(RuntimeError):
    """A fail-closed Web Push runtime-environment error."""


def _plain_env_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value.strip()


def _parse_target_values(lines: list[str]) -> tuple[dict[str, str | None], dict[str, int]]:
    values: dict[str, str | None] = {name: None for name in TRACKED_NAMES}
    positions: dict[str, int] = {}
    for index, raw_line in enumerate(lines):
        logical = raw_line.rstrip("\r\n")
        stripped = logical.lstrip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw_value = stripped.split("=", 1)
        key = key.strip()
        if key not in values:
            continue
        if key in positions:
            raise WebPushEnvError(f"duplicate Web Push runtime key: {key}")
        positions[key] = index
        values[key] = _plain_env_value(raw_value)
    return values, positions


def _decode_private_key(value: str) -> bytes:
    if "=" in value or not BASE64URL_PATTERN.fullmatch(value):
        raise WebPushEnvError(f"{PRIVATE_KEY_NAME} must be unpadded base64url")
    padding = "=" * ((4 - len(value) % 4) % 4)
    try:
        decoded = base64.b64decode(value + padding, altchars=b"-_", validate=True)
    except (binascii.Error, ValueError) as error:
        raise WebPushEnvError(f"{PRIVATE_KEY_NAME} must be unpadded base64url") from error
    if len(decoded) != 32:
        raise WebPushEnvError(f"{PRIVATE_KEY_NAME} must decode to exactly 32 bytes")
    scalar = int.from_bytes(decoded, "big")
    if not 1 <= scalar < P256_ORDER:
        raise WebPushEnvError(f"{PRIVATE_KEY_NAME} is not a valid P-256 private scalar")
    return decoded


def _validate_contact(value: str) -> None:
    parsed = urlsplit(value)
    if parsed.scheme == "mailto" and parsed.path.strip():
        return
    if parsed.scheme == "https" and parsed.hostname:
        return
    raise WebPushEnvError(f"{CONTACT_NAME} must be a mailto: or HTTPS contact URL")


def _normalize_host_suffix(value: str) -> str:
    normalized = value.strip().lstrip(".").rstrip(".").lower()
    try:
        ipaddress.ip_address(normalized)
    except ValueError:
        is_ip_address = False
    else:
        is_ip_address = True
    if (
        not normalized
        or "." not in normalized
        or "*" in normalized
        or "/" in normalized
        or ":" in normalized
        or is_ip_address
    ):
        raise WebPushEnvError(f"{ALLOWED_HOSTS_NAME} contains an invalid DNS suffix")
    labels = normalized.split(".")
    for label in labels:
        if (
            not label
            or label.startswith("-")
            or label.endswith("-")
            or any(
                not (
                    character.isascii()
                    and (character.isalnum() or character == "-")
                )
                for character in label
            )
        ):
            raise WebPushEnvError(f"{ALLOWED_HOSTS_NAME} contains an invalid DNS label")
    return normalized


def _validate_allowed_hosts(value: str) -> tuple[str, ...]:
    hosts = tuple(_normalize_host_suffix(item) for item in value.split(","))
    if not hosts:
        raise WebPushEnvError(f"{ALLOWED_HOSTS_NAME} must contain at least one DNS suffix")
    return hosts


def _validate_complete(values: dict[str, str | None]) -> None:
    private_key = values[PRIVATE_KEY_NAME]
    contact = values[CONTACT_NAME]
    allowed_hosts = values[ALLOWED_HOSTS_NAME]
    assert private_key is not None
    assert contact is not None
    assert allowed_hosts is not None
    _decode_private_key(private_key)
    _validate_contact(contact)
    _validate_allowed_hosts(allowed_hosts)


def _generate_private_key() -> str:
    scalar = secrets.randbelow(P256_ORDER - 1) + 1
    encoded = base64.urlsafe_b64encode(scalar.to_bytes(32, "big")).decode("ascii")
    return encoded.rstrip("=")


def _require_safe_file(path: Path) -> os.stat_result:
    if not path.is_absolute():
        raise WebPushEnvError("runtime env path must be absolute")
    try:
        parent_metadata = path.parent.lstat()
        metadata = path.lstat()
    except OSError as error:
        raise WebPushEnvError(f"runtime env is unavailable: {path}") from error
    if not stat.S_ISDIR(parent_metadata.st_mode) or path.parent.is_symlink():
        raise WebPushEnvError("runtime env parent is not a safe directory")
    if not stat.S_ISREG(metadata.st_mode) or path.is_symlink():
        raise WebPushEnvError("runtime env is not a safe regular file")
    current_uid = os.geteuid()
    if parent_metadata.st_uid != current_uid or metadata.st_uid != current_uid:
        raise WebPushEnvError("runtime env and parent must be owned by the caller")
    if stat.S_IMODE(parent_metadata.st_mode) & 0o022:
        raise WebPushEnvError("runtime env parent is group- or world-writable")
    if stat.S_IMODE(metadata.st_mode) & 0o022:
        raise WebPushEnvError("runtime env is group- or world-writable")
    if metadata.st_nlink != 1:
        raise WebPushEnvError("runtime env must have exactly one hard link")
    if metadata.st_size > MAX_ENV_BYTES:
        raise WebPushEnvError("runtime env exceeds the accepted byte limit")
    return metadata


def _create_backup(path: Path, content: bytes, metadata: os.stat_result) -> None:
    backup = path.with_name(path.name + ".pre-web-push-v1")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(backup, flags, stat.S_IMODE(metadata.st_mode))
    except FileExistsError:
        existing = backup.lstat()
        if (
            not stat.S_ISREG(existing.st_mode)
            or backup.is_symlink()
            or existing.st_uid != metadata.st_uid
            or existing.st_gid != metadata.st_gid
            or stat.S_IMODE(existing.st_mode) & 0o022
            or existing.st_nlink != 1
        ):
            raise WebPushEnvError("existing Web Push backup is unsafe")
        return
    try:
        os.fchmod(descriptor, stat.S_IMODE(metadata.st_mode))
        if hasattr(os, "fchown"):
            os.fchown(descriptor, metadata.st_uid, metadata.st_gid)
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)


def _atomic_replace(path: Path, content: bytes, metadata: os.stat_result) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, stat.S_IMODE(metadata.st_mode))
        if hasattr(os, "fchown"):
            os.fchown(descriptor, metadata.st_uid, metadata.st_gid)
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.close(descriptor)
        descriptor = -1
        os.replace(temporary, path)
        directory_descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def ensure_web_push_env(
    path: Path,
    *,
    contact: str = DEFAULT_CONTACT,
    allowed_host_suffixes: str = DEFAULT_ALLOWED_HOST_SUFFIXES,
) -> str:
    """Create a missing complete VAPID triple or preserve a valid complete one."""

    metadata = _require_safe_file(path)
    try:
        original = path.read_bytes()
    except OSError as error:
        raise WebPushEnvError(f"runtime env cannot be read: {path}") from error
    if len(original) > MAX_ENV_BYTES:
        raise WebPushEnvError("runtime env exceeds the accepted byte limit")
    try:
        text = original.decode("utf-8")
    except UnicodeDecodeError as error:
        raise WebPushEnvError("runtime env must be UTF-8") from error

    lines = text.splitlines(keepends=True)
    values, positions = _parse_target_values(lines)
    configured = {name: bool(values[name]) for name in TARGET_NAMES}
    bootstrap_mode = (values[BOOTSTRAP_MODE_NAME] or "ensure").strip().lower()
    if bootstrap_mode not in {"ensure", "disabled"}:
        raise WebPushEnvError(f"{BOOTSTRAP_MODE_NAME} must be ensure or disabled")

    if all(configured.values()):
        _validate_complete(values)
        return "preserved"
    if any(configured.values()):
        raise WebPushEnvError(
            "Web Push runtime configuration is partial; refusing automatic repair"
        )
    if bootstrap_mode == "disabled":
        return "disabled"

    _validate_contact(contact)
    normalized_hosts = ",".join(_validate_allowed_hosts(allowed_host_suffixes))
    generated = {
        PRIVATE_KEY_NAME: _generate_private_key(),
        CONTACT_NAME: contact.strip(),
        ALLOWED_HOSTS_NAME: normalized_hosts,
    }
    _validate_complete(generated)

    for name in TARGET_NAMES:
        replacement = f"{name}={generated[name]}\n"
        if name in positions:
            existing = lines[positions[name]]
            if existing.endswith("\r\n"):
                replacement = replacement[:-1] + "\r\n"
            lines[positions[name]] = replacement
        else:
            if lines and not lines[-1].endswith(("\n", "\r")):
                lines[-1] += "\n"
            lines.append(replacement)

    updated = "".join(lines).encode("utf-8")
    _create_backup(path, original, metadata)
    _atomic_replace(path, updated, metadata)

    final_metadata = _require_safe_file(path)
    if final_metadata.st_uid != metadata.st_uid or final_metadata.st_gid != metadata.st_gid:
        raise WebPushEnvError("runtime env ownership changed during replacement")
    final_values, _ = _parse_target_values(
        path.read_text(encoding="utf-8").splitlines(keepends=True)
    )
    _validate_complete(final_values)
    return "created"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Provision the production Web Push VAPID runtime identity."
    )
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--contact", default=DEFAULT_CONTACT)
    parser.add_argument(
        "--allowed-host-suffixes", default=DEFAULT_ALLOWED_HOST_SUFFIXES
    )
    return parser.parse_args()


def main() -> int:
    arguments = _parse_args()
    try:
        result = ensure_web_push_env(
            arguments.env_file,
            contact=arguments.contact,
            allowed_host_suffixes=arguments.allowed_host_suffixes,
        )
    except WebPushEnvError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"web_push_vapid_env={result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
