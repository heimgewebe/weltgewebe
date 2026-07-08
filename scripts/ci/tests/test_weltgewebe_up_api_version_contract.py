from __future__ import annotations

from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "weltgewebe-up"
COMPOSE = REPO / "infra" / "compose" / "compose.prod.yml"


def test_api_image_tag_is_bound_to_selected_deploy_head_before_compose_config() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    git_summary = script.index('echo "   Target HEAD after pull: $HEAD_AFTER"')
    export_tag = script.index('export API_VERSION="$HEAD_AFTER"')
    compose_base_args = script.index('BASE_ARGS=("--env-file" "$ENV_FILE"')
    compose_up = script.index('CMD_BASE=("docker" "compose"')

    assert git_summary < export_tag < compose_base_args < compose_up
    assert 'if [[ "$HEAD_AFTER" == "unknown" ]]' in script
    assert 'refusing to select an API image tag' in script


def test_prod_compose_uses_api_version_for_api_image_tag() -> None:
    compose = COMPOSE.read_text(encoding="utf-8")

    assert "image: weltgewebe-api:${API_VERSION:-latest}" in compose


def test_no_pull_path_resolves_current_checkout_head_before_api_tag_guard() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    no_pull = script.index('echo ">> Git: Skipped (--no-pull)"')
    resolve_current_head = script.index('HEAD_AFTER=$(git rev-parse --short HEAD', no_pull)
    unknown_guard = script.index('if [[ "$HEAD_AFTER" == "unknown" ]]')
    export_tag = script.index('export API_VERSION="$HEAD_AFTER"')

    assert no_pull < resolve_current_head < unknown_guard < export_tag
