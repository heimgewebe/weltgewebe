from __future__ import annotations

from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "weltgewebe-up"
COMPOSE = REPO / "infra" / "compose" / "compose.prod.yml"


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
