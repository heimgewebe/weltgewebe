from __future__ import annotations

from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "weltgewebe-up"
VPS_OVERRIDE = REPO / "infra" / "compose" / "compose.vps.override.yml"
HEIMSERVER_OVERRIDE = REPO / "infra" / "compose" / "compose.prod.override.yml"
VPS_RUNBOOK = REPO / "docs" / "deploy" / "vps.md"
RUNTIME_SMOKE = REPO / "docs" / "deploy" / "vps-migration-safe-runtime-smoke.md"


def test_vps_compose_prefers_host_managed_credential_source() -> None:
    text = VPS_OVERRIDE.read_text(encoding="utf-8")

    assert "${WELTGEWEBE_ENV_FILE:-/etc/weltgewebe/weltgewebe.env}" in text
    assert "${WELTGEWEBE_ENV_FILE:-/opt/weltgewebe/.env}" not in text


def test_heimserver_compose_keeps_legacy_host_local_env_source_when_explicitly_selected() -> None:
    text = HEIMSERVER_OVERRIDE.read_text(encoding="utf-8")

    assert "${WELTGEWEBE_ENV_FILE:-/opt/weltgewebe/.env}" in text


def test_weltgewebe_up_defaults_to_vps_and_keeps_heimserver_legacy_target_explicit() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert 'DEPLOY_TARGET="${DEPLOY_TARGET:-vps}"' in text
    assert 'vps | heimserver) ;;' in text
    assert "vps (default) or heimserver (legacy)" in text


def test_weltgewebe_up_selects_vps_credential_source_only_when_unset() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert 'ENV_FILE_WAS_SET="${ENV_FILE+x}"' in text
    assert (
        'VPS_DEFAULT_ENV_FILE="${VPS_DEFAULT_ENV_FILE:-/etc/weltgewebe/weltgewebe.env}"'
        in text
    )
    assert (
        '[[ "$DEPLOY_TARGET" == "vps" && -z "$ENV_FILE_WAS_SET" '
        '&& -f "$VPS_DEFAULT_ENV_FILE" ]]'
        in text
    )
    assert 'ENV_FILE="$VPS_DEFAULT_ENV_FILE"' in text

    explicit_default = text.index('ENV_FILE="${ENV_FILE:-/opt/weltgewebe/.env}"')
    vps_default = text.index(
        'VPS_DEFAULT_ENV_FILE="${VPS_DEFAULT_ENV_FILE:-/etc/weltgewebe/weltgewebe.env}"'
    )
    deploy_target = text.index('DEPLOY_TARGET="${DEPLOY_TARGET:-vps}"')
    switch_default = text.index('ENV_FILE="$VPS_DEFAULT_ENV_FILE"')
    env_check = text.index('if [[ ! -f "$ENV_FILE" ]]')

    assert explicit_default < vps_default < deploy_target < switch_default < env_check


def test_vps_runbook_documents_post_cutover_credential_source() -> None:
    text = VPS_RUNBOOK.read_text(encoding="utf-8")

    assert "/etc/weltgewebe/weltgewebe.env" in text
    assert "owner: root" in text
    assert "mode: 0600" in text
    assert "ENV_FILE=/path/to/runtime.env" in text


def test_runtime_smoke_runbook_names_selected_vps_credential_source() -> None:
    text = RUNTIME_SMOKE.read_text(encoding="utf-8")

    assert "/etc/weltgewebe/weltgewebe.env" in text
    assert "selected runtime env source" in text
    assert "WELTGEWEBE_API_STARTUP_MIGRATIONS=verify-applied" in text
