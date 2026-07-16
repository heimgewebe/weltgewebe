#!/usr/bin/env python3
"""Fail closed unless a tar.gz is a bounded regular-file-only web build tree."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tarfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath

DEFAULT_MAX_COMPRESSED_BYTES = 256 * 1024 * 1024
DEFAULT_MAX_EXPANDED_BYTES = 512 * 1024 * 1024
DEFAULT_MAX_MEMBERS = 20_000


class ArchiveValidationError(ValueError):
    """Raised when an archive violates the deployment boundary."""


@dataclass(frozen=True)
class ArchiveSummary:
    schema_version: int
    archive: str
    compressed_bytes: int
    expanded_bytes: int
    member_count: int


def validate_archive(
    path: Path,
    *,
    max_compressed_bytes: int = DEFAULT_MAX_COMPRESSED_BYTES,
    max_expanded_bytes: int = DEFAULT_MAX_EXPANDED_BYTES,
    max_members: int = DEFAULT_MAX_MEMBERS,
) -> ArchiveSummary:
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
    expanded_bytes = 0
    member_count = 0
    try:
        with tarfile.open(path, mode="r:gz") as bundle:
            for member in bundle:
                member_count += 1
                if member_count > max_members:
                    raise ArchiveValidationError("archive has too many members")

                name = member.name
                member_path = PurePosixPath(name)
                if (
                    member_path.is_absolute()
                    or not member_path.parts
                    or member_path.parts[0] != "build"
                ):
                    raise ArchiveValidationError(f"unexpected archive path: {name}")
                if any(part in {"", ".", ".."} for part in member_path.parts):
                    raise ArchiveValidationError(f"unsafe archive path: {name}")
                if name in seen:
                    raise ArchiveValidationError(f"duplicate archive path: {name}")
                seen.add(name)

                if not (member.isdir() or member.isreg()):
                    raise ArchiveValidationError(
                        f"unsupported archive member type: {name}"
                    )
                if member.mode & 0o6000:
                    raise ArchiveValidationError(
                        f"elevated permission bits in archive: {name}"
                    )

                expanded_bytes += member.size
                if expanded_bytes > max_expanded_bytes:
                    raise ArchiveValidationError("archive exceeds expanded limit")
    except (tarfile.TarError, OSError) as exc:
        raise ArchiveValidationError(f"archive cannot be read: {exc}") from exc

    if member_count == 0:
        raise ArchiveValidationError("archive has no members")
    if "build" not in seen and not any(name.startswith("build/") for name in seen):
        raise ArchiveValidationError("archive has no build tree")

    return ArchiveSummary(
        schema_version=1,
        archive=str(path),
        compressed_bytes=compressed_bytes,
        expanded_bytes=expanded_bytes,
        member_count=member_count,
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
    parser.add_argument("--max-members", type=int, default=DEFAULT_MAX_MEMBERS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        summary = validate_archive(
            args.archive,
            max_compressed_bytes=args.max_compressed_bytes,
            max_expanded_bytes=args.max_expanded_bytes,
            max_members=args.max_members,
        )
    except ArchiveValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.output:
        write_summary(args.output, summary)
    print(
        "web_deploy_archive=ok "
        f"members={summary.member_count} "
        f"compressed_bytes={summary.compressed_bytes} "
        f"expanded_bytes={summary.expanded_bytes}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
