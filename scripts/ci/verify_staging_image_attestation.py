#!/usr/bin/env python3
"""Fail-closed structural verification for T084 staging image promotion."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
EXPECTED_PLATFORMS = ("linux/amd64", "linux/arm64")
SLSA_V1_BUILD_TYPE = (
    "https://github.com/moby/buildkit/blob/master/docs/attestations/"
    "slsa-definitions.md"
)


class VerificationError(ValueError):
    """Promotion evidence does not satisfy the fail-closed contract."""


def _load_json(path: str | Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"invalid JSON evidence: {path}: {exc}") from exc


def verify_commit(commit: str) -> None:
    if not COMMIT_RE.fullmatch(commit):
        raise VerificationError("source commit must be a 40-character lowercase SHA")


def verify_digest(digest: str) -> None:
    if not DIGEST_RE.fullmatch(digest):
        raise VerificationError("digest must be sha256:<64 lowercase hex>")


def verify_slsa_v1(payload: Any, *, expected_commit: str) -> None:
    verify_commit(expected_commit)
    if not isinstance(payload, dict):
        raise VerificationError("SLSA evidence must be a JSON object")
    definition = payload.get("buildDefinition")
    if not isinstance(definition, dict):
        raise VerificationError("SLSA v1 buildDefinition is missing")
    if definition.get("buildType") != SLSA_V1_BUILD_TYPE:
        raise VerificationError("unexpected SLSA v1 buildType")
    external = definition.get("externalParameters")
    if not isinstance(external, dict):
        raise VerificationError("SLSA v1 externalParameters are missing")
    request = external.get("request")
    if not isinstance(request, dict):
        raise VerificationError("SLSA v1 request is missing")
    args = request.get("args")
    if not isinstance(args, dict):
        raise VerificationError("SLSA v1 request args are missing")
    if args.get("build-arg:GIT_COMMIT_SHA") != expected_commit:
        raise VerificationError("SLSA v1 commit build argument does not match")
    run_details = payload.get("runDetails")
    if not isinstance(run_details, dict):
        raise VerificationError("SLSA v1 runDetails are missing")
    metadata = run_details.get("metadata")
    if not isinstance(metadata, dict):
        raise VerificationError("SLSA v1 metadata are missing")
    completeness = metadata.get("buildkit_completeness")
    if not isinstance(completeness, dict) or completeness.get("request") is not True:
        raise VerificationError("SLSA v1 request completeness is not true")


def verify_image(
    payload: Any,
    *,
    expected_commit: str,
    expected_source: str,
    expected_platform: str,
) -> None:
    verify_commit(expected_commit)
    if expected_platform not in EXPECTED_PLATFORMS:
        raise VerificationError(f"unexpected platform: {expected_platform}")
    if not isinstance(payload, dict):
        raise VerificationError("image evidence must be a JSON object")
    observed_platform = f"{payload.get('os')}/{payload.get('architecture')}"
    if observed_platform != expected_platform:
        raise VerificationError(
            f"image platform mismatch: {observed_platform} != {expected_platform}"
        )
    config = payload.get("config")
    if not isinstance(config, dict):
        raise VerificationError("image config is missing")
    labels = config.get("Labels")
    if not isinstance(labels, dict):
        raise VerificationError("image labels are missing")
    if labels.get("org.opencontainers.image.revision") != expected_commit:
        raise VerificationError("OCI revision label does not match source commit")
    if labels.get("org.opencontainers.image.source") != expected_source:
        raise VerificationError("OCI source label does not match repository")


def verify_sbom(payload: Any) -> None:
    if not isinstance(payload, dict) or not payload:
        raise VerificationError("SBOM evidence must be a non-empty JSON object")
    spdx = payload.get("SPDX")
    if not isinstance(spdx, dict) or not spdx:
        raise VerificationError("SBOM SPDX document is missing")
    if spdx.get("SPDXID") != "SPDXRef-DOCUMENT":
        raise VerificationError("SBOM SPDX document identity is invalid")


def verify_attestation(
    slsa: Any,
    image: Any,
    sbom: Any,
    *,
    expected_commit: str,
    expected_source: str,
    expected_platform: str,
) -> None:
    verify_slsa_v1(slsa, expected_commit=expected_commit)
    verify_image(
        image,
        expected_commit=expected_commit,
        expected_source=expected_source,
        expected_platform=expected_platform,
    )
    verify_sbom(sbom)


def verify_index(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise VerificationError("OCI index must be a JSON object")
    if payload.get("schemaVersion") != 2:
        raise VerificationError("OCI index schemaVersion must be 2")
    manifests = payload.get("manifests")
    if not isinstance(manifests, list) or not manifests:
        raise VerificationError("OCI index manifests are missing")
    observed: list[str] = []
    for manifest in manifests:
        if not isinstance(manifest, dict):
            raise VerificationError("OCI index manifest entry must be an object")
        platform = manifest.get("platform")
        if not isinstance(platform, dict):
            raise VerificationError("OCI index manifest platform is missing")
        os_name = platform.get("os")
        architecture = platform.get("architecture")
        if os_name == "unknown" and architecture == "unknown":
            annotations = manifest.get("annotations")
            if (
                not isinstance(annotations, dict)
                or annotations.get("vnd.docker.reference.type")
                != "attestation-manifest"
            ):
                raise VerificationError(
                    "unknown-platform manifest is not a BuildKit attestation"
                )
            continue
        name = f"{os_name}/{architecture}"
        if name not in EXPECTED_PLATFORMS:
            raise VerificationError(f"unexpected promoted platform: {name}")
        observed.append(name)
    if sorted(observed) != sorted(EXPECTED_PLATFORMS):
        raise VerificationError(
            f"promoted platforms must be exactly {list(EXPECTED_PLATFORMS)}"
        )


def manifest_digest_from_bytes(data: bytes) -> str:
    if not data:
        raise VerificationError("dry-run manifest output is empty")
    raw = data[:-1] if data.endswith(b"\n") else data
    if not raw:
        raise VerificationError("dry-run manifest output is empty")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise VerificationError(f"dry-run manifest output is invalid JSON: {exc}") from exc
    verify_index(payload)
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def tag_decision(expected_digest: str, existing_digest: str | None) -> str:
    verify_digest(expected_digest)
    if existing_digest is None:
        return "create"
    verify_digest(existing_digest)
    if existing_digest == expected_digest:
        return "reuse"
    raise VerificationError(
        "immutable sha tag already exists with a different digest"
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    attestation = subparsers.add_parser("attestation")
    attestation.add_argument("--slsa-file", required=True)
    attestation.add_argument("--image-file", required=True)
    attestation.add_argument("--sbom-file", required=True)
    attestation.add_argument("--commit", required=True)
    attestation.add_argument("--source", required=True)
    attestation.add_argument("--platform", required=True, choices=EXPECTED_PLATFORMS)

    index = subparsers.add_parser("index")
    index.add_argument("--index-file", required=True)

    manifest_digest = subparsers.add_parser("manifest-digest")
    manifest_digest.add_argument("--manifest-file", required=True)

    tag = subparsers.add_parser("tag")
    tag.add_argument("--expected-digest", required=True)
    tag.add_argument("--existing-digest")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "attestation":
            verify_attestation(
                _load_json(args.slsa_file),
                _load_json(args.image_file),
                _load_json(args.sbom_file),
                expected_commit=args.commit,
                expected_source=args.source,
                expected_platform=args.platform,
            )
        elif args.command == "index":
            verify_index(_load_json(args.index_file))
        elif args.command == "manifest-digest":
            data = Path(args.manifest_file).read_bytes()
            print(manifest_digest_from_bytes(data))
        elif args.command == "tag":
            print(tag_decision(args.expected_digest, args.existing_digest))
        else:
            raise AssertionError(f"unhandled command: {args.command}")
    except (OSError, VerificationError) as exc:
        print(f"staging image verification failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
