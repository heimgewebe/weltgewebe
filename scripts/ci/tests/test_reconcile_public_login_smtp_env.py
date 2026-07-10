from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import stat
import subprocess
import sys

import pytest


REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "ops" / "reconcile_public_login_smtp_env.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "reconcile_public_login_smtp_env", SCRIPT
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def valid_source(*, port: str = "2525") -> str:
    return "\n".join(
        (
            "AUTH_PUBLIC_LOGIN=1",
            "AUTH_LOG_MAGIC_TOKEN=0",
            "SMTP_HOST=smtp.example.test",
            f"SMTP_PORT={port}",
            "SMTP_AUTH=on",
            "SMTP_USER=test-user",
            "SMTP_PASS=test-pass",
            "SMTP_FROM=noreply@example.test",
            "UNRELATED_SOURCE=must-not-copy",
            "",
        )
    )


def test_build_reconciles_only_approved_keys_and_preserves_unrelated_values() -> None:
    module = load_module()
    source = module.parse_env(valid_source(), label="source")
    selected = module.validate_source(source.values)
    destination = (
        "DATABASE_URL=postgres://preserve\nAUTH_PUBLIC_LOGIN=0\nSMTP_HOST=old\n"
    )

    content = module.build_reconciled_content(destination, selected)
    parsed = module.parse_env(content, label="result").values

    assert parsed["DATABASE_URL"] == "postgres://preserve"
    assert parsed["AUTH_PUBLIC_LOGIN"] == "1"
    assert parsed["SMTP_HOST"] == "smtp.example.test"
    assert "UNRELATED_SOURCE" not in parsed
    assert content.count("AUTH_PUBLIC_LOGIN=") == 1
    assert content.count("SMTP_HOST=") == 1


def test_validate_source_rejects_missing_required_key_without_value_output() -> None:
    module = load_module()
    values = module.parse_env(
        valid_source().replace("SMTP_PASS=test-pass\n", ""), label="source"
    ).values

    with pytest.raises(module.ReconcileError, match="SMTP_PASS") as exc_info:
        module.validate_source(values)

    assert "test-pass" not in str(exc_info.value)


@pytest.mark.parametrize("port", ["25", "1025", "2526", "not-a-number"])
def test_validate_source_rejects_non_tls_submission_ports(port: str) -> None:
    module = load_module()
    values = module.parse_env(valid_source(port=port), label="source").values

    with pytest.raises(module.ReconcileError):
        module.validate_source(values)


@pytest.mark.parametrize("port", ["465", "587", "2525"])
def test_validate_source_accepts_supported_tls_ports(port: str) -> None:
    module = load_module()
    values = module.parse_env(valid_source(port=port), label="source").values

    selected = module.validate_source(values)

    assert selected["SMTP_PORT"] == port


def test_cli_dry_run_is_value_redacted_and_does_not_mutate(tmp_path: Path) -> None:
    source = tmp_path / "legacy.env"
    destination = tmp_path / "canonical.env"
    backup_dir = tmp_path / "backups"
    source.write_text(valid_source(), encoding="utf-8")
    original = "DATABASE_URL=postgres://preserve\nAUTH_PUBLIC_LOGIN=0\n"
    destination.write_text(original, encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source",
            str(source),
            "--destination",
            str(destination),
            "--backup-dir",
            str(backup_dir),
            "--json",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    receipt = json.loads(proc.stdout)
    assert receipt["status"] == "planned"
    assert receipt["applied"] is False
    assert receipt["values_redacted"] is True
    assert destination.read_text(encoding="utf-8") == original
    assert not backup_dir.exists()
    assert "test-pass" not in proc.stdout
    assert "test-pass" not in proc.stderr


def test_apply_creates_backup_and_forces_mode_0600(tmp_path: Path) -> None:
    module = load_module()
    source = tmp_path / "legacy.env"
    destination = tmp_path / "canonical.env"
    backup_dir = tmp_path / "backups"
    source.write_text(valid_source(), encoding="utf-8")
    original = "DATABASE_URL=postgres://preserve\nAUTH_PUBLIC_LOGIN=0\n"
    destination.write_text(original, encoding="utf-8")
    destination.chmod(0o640)

    receipt = module.reconcile(
        source_path=source,
        destination_path=destination,
        backup_dir=backup_dir,
        apply=True,
        require_root=False,
    )

    assert receipt["status"] == "reconciled"
    assert receipt["applied"] is True
    assert receipt["values_redacted"] is True
    assert receipt["mode"] == "0600"
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    backup = Path(receipt["backup"])
    assert backup.read_text(encoding="utf-8") == original
    assert stat.S_IMODE(backup.stat().st_mode) == 0o600
    parsed = module.parse_env(
        destination.read_text(encoding="utf-8"), label="result"
    ).values
    assert parsed["DATABASE_URL"] == "postgres://preserve"
    assert parsed["SMTP_PASS"] == "test-pass"


def test_apply_is_idempotent_after_first_reconciliation(tmp_path: Path) -> None:
    module = load_module()
    source = tmp_path / "legacy.env"
    destination = tmp_path / "canonical.env"
    backup_dir = tmp_path / "backups"
    source.write_text(valid_source(), encoding="utf-8")
    destination.write_text("DATABASE_URL=postgres://preserve\n", encoding="utf-8")

    first = module.reconcile(
        source_path=source,
        destination_path=destination,
        backup_dir=backup_dir,
        apply=True,
        require_root=False,
    )
    second = module.reconcile(
        source_path=source,
        destination_path=destination,
        backup_dir=backup_dir,
        apply=True,
        require_root=False,
    )

    assert first["status"] == "reconciled"
    assert second["status"] == "already_reconciled"
    assert len(list(backup_dir.iterdir())) == 1


def test_symlink_source_is_rejected(tmp_path: Path) -> None:
    module = load_module()
    real_source = tmp_path / "real.env"
    source = tmp_path / "legacy.env"
    destination = tmp_path / "canonical.env"
    real_source.write_text(valid_source(), encoding="utf-8")
    source.symlink_to(real_source)
    destination.write_text("DATABASE_URL=postgres://preserve\n", encoding="utf-8")

    with pytest.raises(module.ReconcileError, match="must not be a symlink"):
        module.reconcile(
            source_path=source,
            destination_path=destination,
            backup_dir=tmp_path / "backups",
            apply=False,
            require_root=False,
        )


def test_non_root_apply_fails_before_backup_or_mutation(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_module()
    source = tmp_path / "legacy.env"
    destination = tmp_path / "canonical.env"
    backup_dir = tmp_path / "backups"
    source.write_text(valid_source(), encoding="utf-8")
    original = "DATABASE_URL=postgres://preserve\n"
    destination.write_text(original, encoding="utf-8")
    monkeypatch.setattr(module.os, "geteuid", lambda: 1000)

    with pytest.raises(module.ReconcileError, match="requires root"):
        module.reconcile(
            source_path=source,
            destination_path=destination,
            backup_dir=backup_dir,
            apply=True,
        )

    assert destination.read_text(encoding="utf-8") == original
    assert not backup_dir.exists()


def test_backup_directory_symlink_is_rejected(tmp_path: Path) -> None:
    module = load_module()
    source = tmp_path / "legacy.env"
    destination = tmp_path / "canonical.env"
    real_backup_dir = tmp_path / "real-backups"
    backup_dir = tmp_path / "backups"
    source.write_text(valid_source(), encoding="utf-8")
    destination.write_text("DATABASE_URL=postgres://preserve\n", encoding="utf-8")
    real_backup_dir.mkdir()
    backup_dir.symlink_to(real_backup_dir, target_is_directory=True)

    with pytest.raises(module.ReconcileError, match="must not be a symlink"):
        module.reconcile(
            source_path=source,
            destination_path=destination,
            backup_dir=backup_dir,
            apply=True,
            require_root=False,
        )

    assert list(real_backup_dir.iterdir()) == []


def test_source_and_destination_must_be_different_files(tmp_path: Path) -> None:
    module = load_module()
    shared = tmp_path / "shared.env"
    shared.write_text(valid_source(), encoding="utf-8")

    with pytest.raises(module.ReconcileError, match="must be different files"):
        module.reconcile(
            source_path=shared,
            destination_path=shared,
            backup_dir=tmp_path / "backups",
            apply=False,
            require_root=False,
        )


def test_quoted_whitespace_secret_is_rejected() -> None:
    module = load_module()
    values = module.parse_env(
        valid_source().replace("SMTP_PASS=test-pass", 'SMTP_PASS="   "'),
        label="source",
    ).values

    with pytest.raises(module.ReconcileError, match="SMTP_PASS is empty"):
        module.validate_source(values)
