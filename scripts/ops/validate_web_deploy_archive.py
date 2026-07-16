#!/usr/bin/env python3
"""Fail closed unless a tar.gz is a bounded regular-file-only web build tree."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tarfile
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath

DEFAULT_MAX_COMPRESSED_BYTES = 256 * 1024 * 1024
DEFAULT_MAX_EXPANDED_BYTES = 512 * 1024 * 1024
DEFAULT_MAX_FILE_BYTES = 64 * 1024 * 1024
DEFAULT_MAX_MEMBERS = 5_000
DEFAULT_MAX_PATH_BYTES = 1024
DEFAULT_MAX_COMPONENT_BYTES = 255
DEFAULT_MAX_DEPTH = 32
REQUIRED_REGULAR_FILES = frozenset({"build/index.html", "build/_app/version.json"})
UNSAFE_UNICODE_CATEGORIES = frozenset({"Cc", "Cf", "Cs"})


class ArchiveValidationError(ValueError):
    """Raised when an archive violates the deployment boundary."""


@dataclass(frozen=True)
class ArchiveSummary:
    schema_version: int
    archive: str
    compressed_bytes: int
    expanded_bytes: int
    member_count: int
    largest_file_bytes: int


def _canonical_member_name(member: tarfile.TarInfo) -> str:
    name = member.name
    if not isinstance(name, str) or not name:
        raise ArchiveValidationError("archive member has an empty name")
    if "\\" in name or any(
        unicodedata.category(character) in UNSAFE_UNICODE_CATEGORIES
        for character in name
    ):
        raise ArchiveValidationError(f"unsafe archive path characters: {name!r}")

    path_bytes = name.encode("utf-8")
    if len(path_bytes) > DEFAULT_MAX_PATH_BYTES:
        raise ArchiveValidationError(f"archive path is too long: {name!r}")

    candidate = name[:-1] if member.isdir() and name.endswith("/") else name
    if not candidate or candidate.startswith("/"):
        raise ArchiveValidationError(f"unexpected archive path: {name}")
    if "//" in candidate or candidate.startswith("./") or "/./" in candidate:
        raise ArchiveValidationError(f"non-canonical archive path: {name}")

    member_path = PurePosixPath(candidate)
    canonical = str(member_path)
    if canonical != candidate:
        raise ArchiveValidationError(f"non-canonical archive path: {name}")
    if not member_path.parts or member_path.parts[0] != "build":
        raise ArchiveValidationError(f"unexpected archive path: {name}")
    if len(member_path.parts) > DEFAULT_MAX_DEPTH:
        raise ArchiveValidationError(f"archive path is too deep: {name}")
    if any(part in {"", ".", ".."} for part in member_path.parts):
        raise ArchiveValidationError(f"unsafe archive path: {name}")
    if any(
        len(part.encode("utf-8")) > DEFAULT_MAX_COMPONENT_BYTES
        for part in member_path.parts
    ):
        raise ArchiveValidationError(f"archive path component is too long: {name}")
    return canonical


def validate_archive(
    path: Path,
    *,
    max_compressed_bytes: int = DEFAULT_MAX_COMPRESSED_BYTES,
    max_expanded_bytes: int = DEFAULT_MAX_EXPANDED_BYTES,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    max_members: int = DEFAULT_MAX_MEMBERS,
) -> ArchiveSummary:
    for name, value in (
        ("max_compressed_bytes", max_compressed_bytes),
        ("max_expanded_bytes", max_expanded_bytes),
        ("max_file_bytes", max_file_bytes),
        ("max_members", max_members),
    ):
        if value <= 0:
            raise ValueError(f"{name} must be positive")

    if path.is_symlink() or not path.is_file():
        raise ArchiveValidationError("archive must be a non-symlink regular file")

    compressed_bytes = path.stat().st_size
    if compressed_bytes <= 0:
        raise ArchiveValidationError("archive is empty")
    if compressed_bytes > max_compressed_bytes:
        raise ArchiveValidationError(
            f"archive exceeds compressed limit: {compressed_bytes} > {max_compressed_bytes}"
        )

    seen: set[str] = set()
    regular_files: set[str] = set()
    expanded_bytes = 0
    largest_file_bytes = 0
    member_count = 0
    try:
        with tarfile.open(path, mode="r:gz") as bundle:
            if bundle.pax_headers:
                raise ArchiveValidationError("archive has unsupported global pax headers")
            for member in bundle:
                member_count += 1
                if member_count > max_members:
                    raise ArchiveValidationError("archive has too many members")

                canonical = _canonical_member_name(member)
                if member.pax_headers:
                    raise ArchiveValidationError(
                        f"archive member has unsupported pax headers: {canonical}"
                    )
                if canonical in seen:
                    raise ArchiveValidationError(f"duplicate archive path: {canonical}")
                seen.add(canonical)

                if not (member.isdir() or member.isreg()):
                    raise ArchiveValidationError(
                        f"unsupported archive member type: {canonical}"
                    )
                if member.mode & 0o7022:
                    raise ArchiveValidationError(
                        f"elevated or writable permission bits in archive: {canonical}"
                    )
                if member.isdir() and member.size != 0:
                    raise ArchiveValidationError(
                        f"directory member has non-zero size: {canonical}"
                    )
                if member.isreg():
                    if member.size < 0:
                        raise ArchiveValidationError(
                            f"archive member has negative size: {canonical}"
                        )
                    if member.size > max_file_bytes:
                        raise ArchiveValidationError(
                            f"archive member exceeds per-file limit: {canonical}"
                        )
                    regular_files.add(canonical)
                    largest_file_bytes = max(largest_file_bytes, member.size)
                    expanded_bytes += member.size
                    if expanded_bytes > max_expanded_bytes:
                        raise ArchiveValidationError("archive exceeds expanded limit")
    except (tarfile.TarError, OSError) as exc:
        raise ArchiveValidationError(f"archive cannot be read: {exc}") from exc

    if member_count == 0:
        raise ArchiveValidationError("archive has no members")
    missing = sorted(REQUIRED_REGULAR_FILES - regular_files)
    if missing:
        raise ArchiveValidationError(
            "archive is missing required regular files: " + ", ".join(missing)
        )

    return ArchiveSummary(
        schema_version=2,
        archive=str(path),
        compressed_bytes=compressed_bytes,
        expanded_bytes=expanded_bytes,
        member_count=member_count,
        largest_file_bytes=largest_file_bytes,
    )


def write_summary(path: Path, summary: ArchiveSummary) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(asdict(summary), handle, sort_keys=True, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--max-compressed-bytes", type=int, default=DEFAULT_MAX_COMPRESSED_BYTES
    )
    parser.add_argument(
        "--max-expanded-bytes", type=int, default=DEFAULT_MAX_EXPANDED_BYTES
    )
    parser.add_argument("--max-file-bytes", type=int, default=DEFAULT_MAX_FILE_BYTES)
    parser.add_argument("--max-members", type=int, default=DEFAULT_MAX_MEMBERS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        summary = validate_archive(
            args.archive,
            max_compressed_bytes=args.max_compressed_bytes,
            max_expanded_bytes=args.max_expanded_bytes,
            max_file_bytes=args.max_file_bytes,
            max_members=args.max_members,
        )
    except (ArchiveValidationError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.output:
        write_summary(args.output, summary)
    print(
        "web_deploy_archive=ok "
        f"members={summary.member_count} "
        f"compressed_bytes={summary.compressed_bytes} "
        f"expanded_bytes={summary.expanded_bytes} "
        f"largest_file_bytes={summary.largest_file_bytes}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
