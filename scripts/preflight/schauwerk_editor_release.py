#!/usr/bin/env python3
"""Fail-closed verifier for the separately provisioned Schauwerk editor release."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

MANIFEST_SCHEMA = "schauwerk-standalone-editor-manifest.v1"
EDITOR_ORIGIN = "https://embed.diagrams.net"
EXPECTED_ASSETS = {"app.js", "canvas-import.js", "index.html", "styles.css"}
EXPECTED_RELEASE_ENTRIES = EXPECTED_ASSETS | {"manifest.json"}


class ReleaseContractError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_release(root: Path) -> dict[str, str]:
    root = root.expanduser()
    if not root.is_absolute():
        raise ReleaseContractError("editor release root must be absolute")
    if root.is_symlink() or not root.is_dir():
        raise ReleaseContractError(f"editor release root is missing or unsafe: {root}")

    releases = root / "releases"
    current = root / "current"
    if releases.is_symlink() or not releases.is_dir():
        raise ReleaseContractError(f"editor releases directory is missing or unsafe: {releases}")
    if not current.is_symlink():
        raise ReleaseContractError(f"editor current pointer must be a symlink: {current}")

    try:
        current_target = current.readlink()
    except OSError as exc:
        raise ReleaseContractError("editor current pointer is unreadable") from exc
    if (
        current_target.is_absolute()
        or len(current_target.parts) != 2
        or current_target.parts[0] != "releases"
        or current_target.parts[1] in {".", "..", ""}
    ):
        raise ReleaseContractError(
            "editor current pointer must use a relative releases/<release> target"
        )

    release_path = releases / current_target.parts[1]
    if release_path.is_symlink() or not release_path.is_dir():
        raise ReleaseContractError(
            f"editor release directory is missing or unsafe: {release_path}"
        )

    try:
        release = release_path.resolve(strict=True)
        releases_resolved = releases.resolve(strict=True)
    except OSError as exc:
        raise ReleaseContractError("editor current pointer is broken") from exc
    if release.parent != releases_resolved or not release.is_dir():
        raise ReleaseContractError("editor current pointer must resolve to one direct releases child")

    try:
        release_entries = {entry.name: entry for entry in release.iterdir()}
    except OSError as exc:
        raise ReleaseContractError("editor release directory is unreadable") from exc
    if set(release_entries) != EXPECTED_RELEASE_ENTRIES:
        raise ReleaseContractError("editor release directory entry set mismatch")
    for name, entry in release_entries.items():
        if entry.is_symlink() or not entry.is_file():
            raise ReleaseContractError(
                f"editor release entry is not a regular file: {name}"
            )

    manifest_path = release / "manifest.json"
    if manifest_path.stat().st_size == 0:
        raise ReleaseContractError("editor manifest is empty")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReleaseContractError("editor manifest is unreadable or invalid JSON") from exc
    if not isinstance(manifest, dict):
        raise ReleaseContractError("editor manifest must be an object")
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise ReleaseContractError("editor manifest schema mismatch")
    if manifest.get("editor_origin") != EDITOR_ORIGIN:
        raise ReleaseContractError("editor manifest origin mismatch")

    files = manifest.get("files")
    if not isinstance(files, list):
        raise ReleaseContractError("editor manifest files must be a list")
    listed: dict[str, str] = {}
    for item in files:
        if not isinstance(item, dict):
            raise ReleaseContractError("editor manifest file entry must be an object")
        name = item.get("path")
        digest = item.get("sha256")
        if (
            not isinstance(name, str)
            or name not in EXPECTED_ASSETS
            or name in listed
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(ch not in "0123456789abcdef" for ch in digest)
        ):
            raise ReleaseContractError("editor manifest contains an invalid file binding")
        listed[name] = digest
    if set(listed) != EXPECTED_ASSETS:
        raise ReleaseContractError("editor manifest asset set mismatch")

    for name, expected in listed.items():
        asset = release_entries[name]
        if asset.stat().st_size == 0:
            raise ReleaseContractError(f"editor asset is empty: {name}")
        if _sha256(asset) != expected:
            raise ReleaseContractError(f"editor asset digest mismatch: {name}")

    return {
        "release": release.name,
        "editor_origin": EDITOR_ORIGIN,
        "manifest_sha256": _sha256(manifest_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = verify_release(args.root)
    except ReleaseContractError as exc:
        print(f"ERROR: Schauwerk editor release preflight failed: {exc}", file=__import__("sys").stderr)
        return 1
    print(
        "schauwerk_editor_release_preflight=pass "
        f"release={result['release']} manifest_sha256={result['manifest_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
