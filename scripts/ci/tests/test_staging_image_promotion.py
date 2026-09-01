from __future__ import annotations

import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github/workflows/staging-image-promotion.yml"
CONTRACT = ROOT / "platform/image-promotion.contract.json"

CHECKOUT = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
BUILDX = "docker/setup-buildx-action@bb05f3f5519dd87d3ba754cc423b652a5edd6d2c"
UPLOAD = "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
DOWNLOAD = "actions/download-artifact@484a0b528fb4d7bd804637ccb632e47a0e638317"


def load_workflow() -> dict:
    payload = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(payload, dict)
    return payload


def test_promotion_is_manual_staging_only_and_minimally_privileged() -> None:
    workflow = load_workflow()
    assert set(workflow["on"]) == {"workflow_dispatch"}
    assert set(workflow["on"]["workflow_dispatch"]["inputs"]) == {"source_commit"}
    assert workflow["permissions"] == {"contents": "read", "packages": "write"}

    text = WORKFLOW.read_text(encoding="utf-8")
    assert "kubectl " not in text
    assert "flux " not in text
    assert "production_activation:true" not in text.replace(" ", "")
    assert "docker/setup-qemu-action@" not in text
    assert "--password-stdin" in text


def test_promotion_builds_natively_and_pushes_content_by_digest() -> None:
    workflow = load_workflow()
    build = workflow["jobs"]["build"]
    matrix = build["strategy"]["matrix"]["include"]
    observed = {(row["runner"], row["platform"], row["arch"]) for row in matrix}
    assert observed == {
        ("ubuntu-24.04", "linux/amd64", "amd64"),
        ("ubuntu-24.04-arm", "linux/arm64", "arm64"),
    }

    uses = [step.get("uses") for step in build["steps"] if isinstance(step, dict)]
    assert CHECKOUT in uses
    assert BUILDX in uses
    assert UPLOAD in uses
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "--file apps/api/Dockerfile" in text
    assert "--file apps/web/Dockerfile" in text
    assert text.count("--provenance=mode=max") == 2
    assert text.count("--sbom=true") == 2
    assert text.count("push-by-digest=true") == 2
    assert text.count("name-canonical=true") == 2
    assert text.count("--metadata-file") == 2
    assert 'GIT_COMMIT_SHA=$SOURCE_COMMIT' in text
    assert 'BUILD_TIMESTAMP=$build_timestamp' in text
    assert ':sha-$SOURCE_COMMIT-$ARCH' not in text


def test_promotion_fails_closed_on_protected_main_drift() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.count('test "$GITHUB_REF" = "refs/heads/main"') == 2
    assert text.count('test "$GITHUB_SHA" = "$SOURCE_COMMIT"') == 2
    assert text.count('repos/${GITHUB_REPOSITORY}/git/ref/heads/main') == 2
    assert text.count('test "$main_head" = "$SOURCE_COMMIT"') == 2


def test_canonical_images_are_single_truth_and_legacy_names_are_digest_aliases() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert contract["schema_version"] == 2
    assert contract["status"] == "blocked"
    assert contract["workflow_status"] == "ready"
    assert contract["production_activation"] is False
    assert contract["required_images"] == [
        "ghcr.io/heimgewebe/commonthing-api",
        "ghcr.io/heimgewebe/commonthing-web",
    ]
    assert contract["legacy_aliases"] == {
        "ghcr.io/heimgewebe/weltgewebe-api": "ghcr.io/heimgewebe/commonthing-api",
        "ghcr.io/heimgewebe/weltgewebe-web": "ghcr.io/heimgewebe/commonthing-web",
    }
    assert contract["platforms"] == ["linux/amd64", "linux/arm64"]
    assert contract["attestations"] == ["provenance-mode-max", "sbom"]

    text = WORKFLOW.read_text(encoding="utf-8")
    assert '--output "type=image,name=$API_LEGACY' not in text
    assert '--output "type=image,name=$WEB_LEGACY' not in text
    assert '"$API_CANONICAL@$api_digest"' in text
    assert '"$WEB_CANONICAL@$web_digest"' in text
    assert 'test "$api_legacy_digest" = "$api_digest"' in text
    assert 'test "$web_legacy_digest" = "$web_digest"' in text


def test_promotion_merges_digest_artifacts_and_binds_attestations_to_source() -> None:
    workflow = load_workflow()
    promote = workflow["jobs"]["promote"]
    uses = [step.get("uses") for step in promote["steps"] if isinstance(step, dict)]
    assert CHECKOUT in uses
    assert BUILDX in uses
    assert DOWNLOAD in uses
    assert UPLOAD in uses

    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'test "${#api_digests[@]}" -eq 2' in text
    assert 'test "${#web_digests[@]}" -eq 2' in text
    assert 'index .SLSA' in text
    assert 'index .Image' in text
    assert 'index .SBOM' in text
    assert '.metadata.completeness.parameters == true' in text
    assert 'build-arg:GIT_COMMIT_SHA' in text
    assert 'org.opencontainers.image.revision' in text
    assert 'org.opencontainers.image.source' in text
    assert '--arg commit "$SOURCE_COMMIT"' in text
    assert '--arg source "$expected_source"' in text
    assert 'sort == ["amd64", "arm64"]' in text


def test_promotion_persists_a_revision_and_digest_bound_receipt() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'source_commit: $source_commit' in text
    assert 'digest: $api_digest' in text
    assert 'digest: $web_digest' in text
    assert 'scope: "staging-only"' in text
    assert 'production_activation: false' in text
    assert "staging-image-promotion-${{ inputs.source_commit }}" in text
