#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SEED_PATH = ROOT / "platform/oci-proof-mirror.seed.json"
FULL_COMMIT = re.compile(r"[0-9a-f]{40}")
FULL_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
SAFE_NAME = re.compile(r"[a-z0-9_]+")


class PublisherError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_json(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _output(argv: list[str], *, timeout: int = 300) -> str:
    print("+", " ".join(argv), file=sys.stderr, flush=True)
    return subprocess.run(
        argv,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    ).stdout.strip()


def _run(argv: list[str], *, timeout: int = 1800) -> None:
    print("+", " ".join(argv), file=sys.stderr, flush=True)
    subprocess.run(argv, cwd=ROOT, check=True, timeout=timeout)


def _load_seed() -> dict[str, Any]:
    try:
        seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PublisherError(f"mirror seed is unreadable: {error}") from error
    if seed.get("schema_version") != 1:
        raise PublisherError("unsupported mirror seed schema")
    if seed.get("owner") != "heimgewebe/weltgewebe":
        raise PublisherError("mirror seed owner mismatch")
    target = seed.get("target")
    publisher = seed.get("publisher")
    images = seed.get("images")
    if not isinstance(target, dict) or not isinstance(publisher, dict):
        raise PublisherError("mirror seed lacks target or publisher policy")
    if target.get("registry") != "ghcr.io":
        raise PublisherError("mirror target must remain ghcr.io")
    if target.get("repository") != "ghcr.io/heimgewebe/weltgewebe-proof-oci":
        raise PublisherError("mirror target repository mismatch")
    if target.get("visibility") != "private":
        raise PublisherError("mirror package must remain private")
    if target.get("max_versions") != 30:
        raise PublisherError("mirror version budget must remain 30")
    if publisher != {
        "canonical_attempts": 3,
        "require_identical_manifest_digest": True,
        "require_expected_head": True,
        "require_expected_seed_sha256": True,
    }:
        raise PublisherError("unexpected mirror publisher policy")
    if not isinstance(images, dict) or len(images) != 25:
        raise PublisherError("mirror seed must contain exactly 25 external images")
    for name, spec in images.items():
        if not SAFE_NAME.fullmatch(name) or not isinstance(spec, dict):
            raise PublisherError(f"unsafe mirror image entry: {name}")
        canonical = spec.get("canonical")
        suites = spec.get("suites")
        if not isinstance(canonical, str) or "@sha256:" not in canonical:
            raise PublisherError(f"mirror source {name} is not digest-bound")
        if not FULL_DIGEST.fullmatch(canonical.rsplit("@", 1)[1]):
            raise PublisherError(f"mirror source {name} has malformed digest")
        if not isinstance(suites, list) or not suites:
            raise PublisherError(f"mirror source {name} has no suite binding")
        if canonical.startswith("weltgewebe-") or "weltgewebe-api" in canonical or "weltgewebe-web" in canonical:
            raise PublisherError("publisher may not publish application images")
    return seed


def _git_head() -> str:
    head = _output(["git", "rev-parse", "HEAD"])
    if not FULL_COMMIT.fullmatch(head):
        raise PublisherError("checked-out head is not a full commit")
    return head


def _manifest_digest(reference: str) -> str:
    raw = _output(
        [
            "docker",
            "buildx",
            "imagetools",
            "inspect",
            reference,
            "--format",
            "{{json .Manifest.Digest}}",
        ],
        timeout=600,
    )
    try:
        digest = json.loads(raw)
    except json.JSONDecodeError as error:
        raise PublisherError(f"Docker returned malformed manifest digest for {reference}") from error
    if not isinstance(digest, str) or not FULL_DIGEST.fullmatch(digest):
        raise PublisherError(f"Docker returned no full manifest digest for {reference}")
    return digest


def _publish_one(
    target_repository: str,
    name: str,
    canonical: str,
    attempts: int,
) -> dict[str, str]:
    canonical_digest = canonical.rsplit("@", 1)[1]
    observed_canonical = _manifest_digest(canonical)
    if observed_canonical != canonical_digest:
        raise PublisherError(
            f"canonical manifest digest mismatch for {name}: "
            f"{observed_canonical} != {canonical_digest}"
        )
    target_tag = f"{target_repository}:{name}-{canonical_digest.removeprefix('sha256:')[:16]}"
    failures: list[str] = []
    for attempt in range(attempts):
        try:
            _run(
                [
                    "docker",
                    "buildx",
                    "imagetools",
                    "create",
                    "--tag",
                    target_tag,
                    canonical,
                ],
                timeout=3600,
            )
            mirror_digest = _manifest_digest(target_tag)
            if mirror_digest != canonical_digest:
                raise PublisherError(
                    f"mirror digest mismatch for {name}: "
                    f"{mirror_digest} != {canonical_digest}"
                )
            return {
                "canonical": canonical,
                "canonical_digest": canonical_digest,
                "mirror_tag": target_tag,
                "mirror": f"{target_repository}@{mirror_digest}",
                "mirror_digest": mirror_digest,
            }
        except PublisherError:
            raise
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            failures.append(f"attempt {attempt + 1}/{attempts}: {error}")
            if attempt + 1 < attempts:
                time.sleep(float(2**attempt))
    raise PublisherError(
        f"mirror publication failed for {name} after bounded retries: "
        + " | ".join(failures)
    )


def publish(expected_head: str, expected_seed_sha256: str, output: Path) -> dict[str, Any]:
    if not FULL_COMMIT.fullmatch(expected_head):
        raise PublisherError("expected head must be a full lowercase commit")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_seed_sha256):
        raise PublisherError("expected seed SHA-256 must contain 64 lowercase hex characters")
    observed_head = _git_head()
    observed_seed = _sha256(SEED_PATH)
    if observed_head != expected_head:
        raise PublisherError(f"head mismatch: {observed_head} != {expected_head}")
    if observed_seed != expected_seed_sha256:
        raise PublisherError(f"seed mismatch: {observed_seed} != {expected_seed_sha256}")
    seed = _load_seed()
    entries: dict[str, Any] = {}
    for name, spec in seed["images"].items():
        result = _publish_one(
            seed["target"]["repository"],
            name,
            spec["canonical"],
            seed["publisher"]["canonical_attempts"],
        )
        result["suites"] = spec["suites"]
        result["load_into_kind"] = spec.get("load_into_kind", True)
        entries[name] = result
    payload = {
        "schema_version": 1,
        "status": "pass",
        "owner": seed["owner"],
        "source_head": observed_head,
        "seed_sha256": observed_seed,
        "target": seed["target"],
        "image_count": len(entries),
        "images": entries,
    }
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=output.parent, prefix=f".{output.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(_canonical_json(payload))
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return payload


def validate() -> dict[str, Any]:
    seed = _load_seed()
    return {
        "schema_version": 1,
        "status": "pass",
        "owner": seed["owner"],
        "target_repository": seed["target"]["repository"],
        "visibility": seed["target"]["visibility"],
        "image_count": len(seed["images"]),
        "seed_sha256": _sha256(SEED_PATH),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    publish_parser = sub.add_parser("publish")
    publish_parser.add_argument("--expected-head", required=True)
    publish_parser.add_argument("--expected-seed-sha256", required=True)
    publish_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "validate":
            result = validate()
        else:
            result = publish(
                args.expected_head,
                args.expected_seed_sha256,
                args.output,
            )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (PublisherError, OSError, subprocess.CalledProcessError) as error:
        print(f"OCI mirror publisher failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
