from __future__ import annotations

import os
import subprocess
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


def test_weltgewebe_up_selects_canonical_vps_credential_source_when_unset() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert 'ENV_FILE_WAS_SET="${ENV_FILE:+x}"' in text
    assert (
        'VPS_DEFAULT_ENV_FILE="${VPS_DEFAULT_ENV_FILE:-/etc/weltgewebe/weltgewebe.env}"'
        in text
    )
    assert '[[ "$DEPLOY_TARGET" == "vps" && -z "$ENV_FILE_WAS_SET" ]]' in text
    assert '&& -f "$VPS_DEFAULT_ENV_FILE"' not in text
    assert 'ENV_FILE="$VPS_DEFAULT_ENV_FILE"' in text

    explicit_default = text.index('ENV_FILE="${ENV_FILE:-/opt/weltgewebe/.env}"')
    vps_default = text.index(
        'VPS_DEFAULT_ENV_FILE="${VPS_DEFAULT_ENV_FILE:-/etc/weltgewebe/weltgewebe.env}"'
    )
    deploy_target = text.index('DEPLOY_TARGET="${DEPLOY_TARGET:-vps}"')
    switch_default = text.index('ENV_FILE="$VPS_DEFAULT_ENV_FILE"')
    env_normalize = text.index('if [[ "$ENV_FILE" != /* ]]')
    env_check = text.index('if [[ ! -r "$ENV_FILE" ]]')

    assert explicit_default < vps_default < deploy_target < switch_default < env_normalize < env_check
    assert 'ENV_FILE is missing or not readable' in text
    assert 'documented privileged operator path' in text


def run_until_env_guard(tmp_path: Path, *, env_file: str | None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "DEPLOY_TARGET": "vps",
            "CADDY_BIND": "203.0.113.10",
            "CADDY_IPV6_BIND": "[2001:db8::10]",
            "REPO_DIR": str(REPO),
            "VPS_DEFAULT_ENV_FILE": str(tmp_path / "canonical.env"),
            "WELTGEWEBE_STATE_DIR": str(tmp_path / "state"),
        }
    )
    if env_file is None:
        env.pop("ENV_FILE", None)
    else:
        env["ENV_FILE"] = env_file

    return subprocess.run(
        [str(SCRIPT), "--no-pull"],
        cwd=REPO,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def test_empty_env_file_selects_canonical_source_and_fails_closed(tmp_path: Path) -> None:
    proc = run_until_env_guard(tmp_path, env_file="")

    assert proc.returncode == 2
    assert str(tmp_path / "canonical.env") in proc.stdout
    assert "/opt/weltgewebe/.env" not in proc.stdout
    assert "missing or not readable" in proc.stdout


def test_unreadable_canonical_source_fails_with_operator_guidance(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical.env"
    canonical.write_text("APP_BASE_URL=https://commonthing.net\n", encoding="utf-8")
    canonical.chmod(0)
    try:
        proc = run_until_env_guard(tmp_path, env_file=None)
    finally:
        canonical.chmod(0o600)

    assert proc.returncode == 2
    assert "missing or not readable" in proc.stdout
    assert "documented privileged operator path" in proc.stdout


def test_vps_binds_compose_env_mount_to_selected_env_file() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert 'if [[ "$DEPLOY_TARGET" == "vps" ]]' in text
    assert 'export WELTGEWEBE_ENV_FILE="$ENV_FILE"' in text


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
