from __future__ import annotations

from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "weltgewebe-up"
COMPOSE = REPO / "infra" / "compose" / "compose.prod.yml"
DOCKERFILE = REPO / "apps" / "api" / "Dockerfile"
TELEMETRY = REPO / "apps" / "api" / "src" / "telemetry" / "mod.rs"
API_SMOKE = REPO / ".github" / "workflows" / "api-smoke.yml"
VERIFY_SCRIPT = REPO / "scripts" / "ops" / "verify-api-release-identity.sh"
META_ROUTE = REPO / "apps" / "api" / "src" / "routes" / "meta.rs"


def test_api_image_tag_is_bound_to_selected_deploy_head_before_compose_config() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    git_summary = script.index('echo "   Target HEAD after pull: $HEAD_AFTER_FULL"')
    full_commit_guard = script.index(
        'if [[ ! "$HEAD_AFTER_FULL" =~ ^[0-9a-f]{40}$ || "$HEAD_AFTER" == "unknown" ]]'
    )
    export_tag = script.index('export API_VERSION="$HEAD_AFTER"')
    export_build = script.index('export WELTGEWEBE_BUILD="$HEAD_AFTER"')
    compose_base_args = script.index('BASE_ARGS=("--env-file" "$ENV_FILE"')
    compose_up = script.index('CMD_BASE=("docker" "compose"')

    assert (
        git_summary
        < full_commit_guard
        < export_tag
        < export_build
        < compose_base_args
        < compose_up
    )
    assert 'HEAD_AFTER_FULL=$(git rev-parse HEAD' in script
    assert 'refusing deployment' in script


def test_prod_compose_uses_api_version_for_api_image_tag() -> None:
    compose = COMPOSE.read_text(encoding="utf-8")

    assert "image: weltgewebe-api:${API_VERSION:?API_VERSION must be set}" in compose
    assert "image: weltgewebe-api:${API_VERSION:-latest}" not in compose


def test_prod_compose_requires_caddy_build_header_value() -> None:
    compose = COMPOSE.read_text(encoding="utf-8")

    assert (
        "WELTGEWEBE_BUILD: ${WELTGEWEBE_BUILD:?WELTGEWEBE_BUILD must be set}"
        in compose
    )


def test_no_pull_path_resolves_current_checkout_head_before_api_tag_guard() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    no_pull = script.index('echo ">> Git: Skipped (--no-pull)"')
    resolve_short_head = script.index('HEAD_AFTER=$(git rev-parse --short HEAD', no_pull)
    resolve_full_head = script.index('HEAD_AFTER_FULL=$(git rev-parse HEAD', no_pull)
    full_commit_guard = script.index(
        'if [[ ! "$HEAD_AFTER_FULL" =~ ^[0-9a-f]{40}$ || "$HEAD_AFTER" == "unknown" ]]'
    )
    export_tag = script.index('export API_VERSION="$HEAD_AFTER"')

    assert (
        no_pull
        < resolve_short_head
        < resolve_full_head
        < full_commit_guard
        < export_tag
    )


def test_deploy_derives_binary_identity_from_full_commit_before_compose_config() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    full_commit_guard = script.index(
        'if [[ ! "$HEAD_AFTER_FULL" =~ ^[0-9a-f]{40}$ || "$HEAD_AFTER" == "unknown" ]]'
    )
    timestamp = script.index(
        'HEAD_COMMIT_TIMESTAMP="$(git show -s --format=%cI "$HEAD_AFTER_FULL"'
    )
    export_commit = script.index('export GIT_COMMIT_SHA="$HEAD_AFTER_FULL"')
    export_timestamp = script.index('export BUILD_TIMESTAMP="$HEAD_COMMIT_TIMESTAMP"')
    compose_base_args = script.index('BASE_ARGS=("--env-file" "$ENV_FILE"')

    assert (
        full_commit_guard
        < timestamp
        < export_commit
        < export_timestamp
        < compose_base_args
    )
    assert "Git committer timestamp" in script


def test_prod_compose_requires_binary_build_provenance_args() -> None:
    compose = COMPOSE.read_text(encoding="utf-8")

    assert "GIT_COMMIT_SHA: ${GIT_COMMIT_SHA:?GIT_COMMIT_SHA must be set}" in compose
    assert "BUILD_TIMESTAMP: ${BUILD_TIMESTAMP:?BUILD_TIMESTAMP must be set}" in compose


def test_api_dockerfile_compiles_validated_provenance_into_release_binary() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")

    assert "ARG GIT_COMMIT_SHA" in dockerfile
    assert "ARG BUILD_TIMESTAMP" in dockerfile
    assert "grep -Eq '^[0-9a-f]{40}$'" in dockerfile
    assert 'GIT_COMMIT_SHA="${GIT_COMMIT_SHA}"' in dockerfile
    assert 'BUILD_TIMESTAMP="${BUILD_TIMESTAMP}"' in dockerfile
    assert "cargo build --release --locked --bin weltgewebe-api" in dockerfile


def test_release_build_info_cannot_fall_back_to_unknown() -> None:
    telemetry = TELEMETRY.read_text(encoding="utf-8")

    assert "#[cfg(not(debug_assertions))]\nconst GIT_COMMIT_SHA: &str = env!(" in telemetry
    assert "#[cfg(not(debug_assertions))]\nconst BUILD_TIMESTAMP: &str = env!(" in telemetry
    assert "commit: GIT_COMMIT_SHA" in telemetry
    assert "build_timestamp: BUILD_TIMESTAMP" in telemetry


def test_api_smoke_checks_exact_release_identity() -> None:
    workflow = API_SMOKE.read_text(encoding="utf-8")

    assert 'commit="$(git rev-parse HEAD)"' in workflow
    assert 'build_timestamp="$(git show -s --format=%cI "$commit")"' in workflow
    assert 'GIT_COMMIT_SHA="$commit"' in workflow
    assert 'BUILD_TIMESTAMP="$build_timestamp"' in workflow
    assert ".commit == $commit" in workflow
    assert ".build_timestamp == $build_timestamp" in workflow
    assert '.commit != "unknown"' in workflow
    assert '.build_timestamp != "unknown"' in workflow
    assert 'tolower($1) == "x-weltgewebe-api-build:"' in workflow
    assert '[[ "$api_build" == "$WELTGEWEBE_API_BUILD_COMMIT" ]]' in workflow


def test_public_release_identity_verifier_binds_body_and_header() -> None:
    verifier = VERIFY_SCRIPT.read_text(encoding="utf-8")

    assert 'EXPECTED_COMMIT must be a full lowercase Git SHA' in verifier
    assert 'tolower($1) == "x-weltgewebe-api-build:"' in verifier
    assert 'commit != expected_commit' in verifier
    assert 'build_timestamp != expected_timestamp' in verifier
    assert 'API build header mismatch' in verifier
    assert 'api_release_identity=ok' in verifier


def test_api_version_response_owns_a_separate_full_commit_header() -> None:
    route = META_ROUTE.read_text(encoding="utf-8")

    assert 'pub const API_BUILD_HEADER: &str = "x-weltgewebe-api-build";' in route
    assert "HeaderValue::from_static(info.commit)" in route
    assert "HeaderName::from_static(API_BUILD_HEADER)" in route
    assert "version_response_exposes_the_binary_commit_header" in route
