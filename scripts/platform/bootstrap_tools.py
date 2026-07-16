#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import stat
import tarfile
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
LOCK_PATH = ROOT / "platform/toolchain.lock.json"
DEFAULT_CACHE = ROOT / ".cache/weltgewebe-platform"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url: str, expected_sha256: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and _sha256(destination) == expected_sha256:
        return
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as tmp:
        tmp_path = Path(tmp.name)
        request = urllib.request.Request(url, headers={"User-Agent": "weltgewebe-platform-bootstrap/1"})
        with urllib.request.urlopen(request, timeout=90) as response:
            shutil.copyfileobj(response, tmp)
    actual = _sha256(tmp_path)
    if actual != expected_sha256:
        tmp_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"download hash mismatch for {url}: expected {expected_sha256}, got {actual}"
        )
    os.replace(tmp_path, destination)


def _safe_extract_tar(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as handle:
        root = destination.resolve()
        for member in handle.getmembers():
            target = (destination / member.name).resolve()
            if root not in target.parents and target != root:
                raise RuntimeError(f"unsafe archive member: {member.name}")
        handle.extractall(destination, members=handle.getmembers())


def _check_host(lock: dict[str, Any]) -> None:
    machine = platform.machine().lower()
    if platform.system() != "Linux" or machine not in {"x86_64", "amd64"}:
        raise RuntimeError(
            f"tool lock supports linux-amd64 only; observed {platform.system()}-{machine}"
        )
    if lock.get("platform") != "linux-amd64":
        raise RuntimeError("unexpected platform lock")


def install(cache: Path) -> dict[str, Any]:
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    if lock.get("schema_version") != 1:
        raise RuntimeError("unsupported toolchain lock schema")
    _check_host(lock)
    downloads = cache / "downloads"
    bin_dir = cache / "bin"
    artifact_dir = cache / "artifacts"
    bin_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    tool_paths: dict[str, str] = {}

    for name, spec in lock["tools"].items():
        filename = Path(urllib.parse.urlparse(spec["url"]).path).name
        archive = downloads / filename
        _download(spec["url"], spec["sha256"], archive)
        destination = bin_dir / spec["binary"]
        if spec["format"] == "binary":
            shutil.copy2(archive, destination)
        elif spec["format"] == "tar.gz":
            with tempfile.TemporaryDirectory(dir=cache) as tmp:
                tmp_dir = Path(tmp)
                _safe_extract_tar(archive, tmp_dir)
                candidate = next(
                    (path for path in tmp_dir.rglob(spec["binary"]) if path.is_file()),
                    None,
                )
                if candidate is None:
                    raise RuntimeError(f"binary {spec['binary']} missing from {archive}")
                shutil.copy2(candidate, destination)
        else:
            raise RuntimeError(f"unsupported format {spec['format']} for {name}")
        destination.chmod(destination.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)
        tool_paths[name] = str(destination)

    artifact_paths: dict[str, str] = {}
    for name, spec in lock["artifacts"].items():
        destination = artifact_dir / spec["filename"]
        _download(spec["url"], spec["sha256"], destination)
        artifact_paths[name] = str(destination)

    receipt = {
        "schema_version": 1,
        "lock_sha256": hashlib.sha256(LOCK_PATH.read_bytes()).hexdigest(),
        "cache": str(cache),
        "tools": tool_paths,
        "artifacts": artifact_paths,
        "kubernetes": lock["kubernetes"],
    }
    (cache / "receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    receipt = install(args.cache.resolve())
    if args.json:
        print(json.dumps(receipt, sort_keys=True))
    else:
        print(receipt["cache"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
