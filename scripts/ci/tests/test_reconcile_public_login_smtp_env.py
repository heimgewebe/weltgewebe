from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import stat
import sys

import pytest


REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "ops" / "reconcile_public_login_smtp_env.py"
SECRET_SENTINEL = "secret-value-that-must-never-appear-in-a-receipt"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "reconcile_public_login_smtp_env", SCRIPT
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def valid_source(
    *,
    public_login: str = "1",
    magic_log: str = "0",
    smtp_auth: str = "on",
    port: str = "2525",
    password: str = SECRET_SENTINEL,
    smtp_from: str = "noreply@example.test",
    app_base_url: str = "https://weltgewebe.net",
) -> str:
    return "\n".join(
        (
            f"AUTH_PUBLIC_LOGIN={public_login}",
            f"AUTH_LOG_MAGIC_TOKEN={magic_log}",
            "SMTP_HOST=smtp.example.test",
            f"SMTP_PORT={port}",
            f"SMTP_AUTH={smtp_auth}",
            "SMTP_USER=test-user",
            f"SMTP_PASS={password}",
            f"SMTP_FROM={smtp_from}",
            f"APP_BASE_URL={app_base_url}",
            "UNRELATED_SOURCE=must-not-copy",
            "",
        )
    )


def create_runtime_files(
    tmp_path: Path,
    *,
    source_text: str | None = None,
    destination_text: str = "DATABASE_URL=postgres://preserve\nAUTH_PUBLIC_LOGIN=0\n",
) -> tuple[Path, Path, Path]:
    source = tmp_path / "legacy.env"
    destination = tmp_path / "canonical.env"
    backup_dir = tmp_path / "backups"
    source.write_text(source_text or valid_source(), encoding="utf-8")
    destination.write_text(destination_text, encoding="utf-8")
    backup_dir.mkdir(mode=0o700)
    backup_dir.chmod(0o700)
    return source, destination, backup_dir


def preview(
    module,
    source: Path,
    destination: Path,
    backup_dir: Path,
    *,
    smtp_from_override: str | None = None,
):
    return module.reconcile(
        source_path=source,
        destination_path=destination,
        backup_dir=backup_dir,
        apply=False,
        smtp_from_override=smtp_from_override,
        require_root=False,
    )


def apply_preview(
    module,
    source: Path,
    destination: Path,
    backup_dir: Path,
    *,
    smtp_from_override: str | None = None,
):
    dry_run = preview(
        module,
        source,
        destination,
        backup_dir,
        smtp_from_override=smtp_from_override,
    )
    applied = module.reconcile(
        source_path=source,
        destination_path=destination,
        backup_dir=backup_dir,
        apply=True,
        expected_plan_sha256=dry_run["plan_sha256"],
        smtp_from_override=smtp_from_override,
        require_root=False,
    )
    return dry_run, applied


def stat_with(
    original: os.stat_result,
    *,
    mode: int | None = None,
    uid: int | None = None,
    gid: int | None = None,
) -> os.stat_result:
    values = list(original)
    if mode is not None:
        values[0] = mode
    if uid is not None:
        values[4] = uid
    if gid is not None:
        values[5] = gid
    return os.stat_result(values)


def test_validate_source_canonicalizes_exact_runtime_values() -> None:
    module = load_module()
    values = module.parse_env(
        valid_source(
            public_login='"true"',
            magic_log="FALSE",
            smtp_auth="ON",
            port="02525",
        ),
        label="source",
    ).values

    selected = module.validate_source(values)

    assert selected["AUTH_PUBLIC_LOGIN"] == "1"
    assert selected["AUTH_LOG_MAGIC_TOKEN"] == "0"
    assert selected["SMTP_AUTH"] == "on"
    assert selected["SMTP_PORT"] == "2525"


@pytest.mark.parametrize("value", ["yes", "on", "2", "FALSE", "'   '"])
def test_validate_source_rejects_non_runtime_public_login_values(value: str) -> None:
    module = load_module()
    values = module.parse_env(valid_source(public_login=value), label="source").values

    with pytest.raises(module.ReconcileError, match="not enabled"):
        module.validate_source(values)


@pytest.mark.parametrize("value", ["no", "off", "2", "TRUE", "'   '"])
def test_validate_source_rejects_non_runtime_magic_log_values(value: str) -> None:
    module = load_module()
    values = module.parse_env(valid_source(magic_log=value), label="source").values

    with pytest.raises(module.ReconcileError, match="not disabled"):
        module.validate_source(values)


@pytest.mark.parametrize("value", ["true", "1", "yes", "off", "'   '"])
def test_validate_source_requires_exact_smtp_auth_on(value: str) -> None:
    module = load_module()
    values = module.parse_env(valid_source(smtp_auth=value), label="source").values

    with pytest.raises(module.ReconcileError, match="exactly 'on'"):
        module.validate_source(values)


@pytest.mark.parametrize("port", ["25", "1025", "2526", "not-a-number"])
def test_validate_source_rejects_non_tls_submission_ports(port: str) -> None:
    module = load_module()
    values = module.parse_env(valid_source(port=port), label="source").values

    with pytest.raises(module.ReconcileError):
        module.validate_source(values)


@pytest.mark.parametrize("port", ["+2525", "2 525", "２５２５", "2525#comment"])
def test_validate_source_rejects_non_ascii_or_decorated_ports(port: str) -> None:
    module = load_module()
    values = module.parse_env(valid_source(port=port), label="source").values

    with pytest.raises(module.ReconcileError, match="ASCII digits"):
        module.validate_source(values)


@pytest.mark.parametrize("port", ["465", "587", "2525"])
def test_validate_source_accepts_supported_tls_ports(port: str) -> None:
    module = load_module()
    values = module.parse_env(valid_source(port=port), label="source").values

    selected = module.validate_source(values)

    assert selected["SMTP_PORT"] == port


def test_validate_source_rejects_missing_required_key_without_secret_output() -> None:
    module = load_module()
    values = module.parse_env(
        valid_source().replace(f"SMTP_PASS={SECRET_SENTINEL}\n", ""),
        label="source",
    ).values

    with pytest.raises(module.ReconcileError, match="SMTP_PASS") as exc_info:
        module.validate_source(values)

    assert SECRET_SENTINEL not in str(exc_info.value)


@pytest.mark.parametrize("separator", ["\x0b", "\u2028"])
def test_source_rejects_unsupported_line_separator_without_secret_output(
    separator: str,
) -> None:
    module = load_module()
    source = valid_source(password=f"prefix{separator}{SECRET_SENTINEL}")

    with pytest.raises(
        module.ReconcileError, match="unsupported line separator"
    ) as exc_info:
        module.parse_env(source, label="source")

    assert SECRET_SENTINEL not in str(exc_info.value)


@pytest.mark.parametrize("separator", ["\x0b", "\u2028"])
def test_destination_rejects_unsupported_line_separator(separator: str) -> None:
    module = load_module()
    destination = f"DATABASE_URL=postgres://user:pass{separator}host/db\n"

    with pytest.raises(module.ReconcileError, match="unsupported line separator"):
        module.parse_env(destination, label="destination")


def test_validate_source_rejects_quoted_whitespace_secret() -> None:
    module = load_module()
    values = module.parse_env(valid_source(password='"   "'), label="source").values

    with pytest.raises(module.ReconcileError, match="SMTP_PASS is empty"):
        module.validate_source(values)


@pytest.mark.parametrize("value", ['"unterminated', "unterminated'", "'"])
def test_validate_source_rejects_malformed_quotes(value: str) -> None:
    module = load_module()
    values = module.parse_env(valid_source(password=value), label="source").values

    with pytest.raises(module.ReconcileError, match="malformed quoted value"):
        module.validate_source(values)


def test_build_reconciles_only_allowlisted_keys_and_preserves_unrelated_values() -> (
    None
):
    module = load_module()
    selected = module.validate_source(
        module.parse_env(valid_source(), label="source").values
    )
    destination = (
        "DATABASE_URL=postgres://preserve\n"
        "AUTH_PUBLIC_LOGIN=0\n"
        "SMTP_HOST=old\n"
        "SMTP_HOST=duplicate\n"
    )

    with pytest.raises(module.ReconcileError, match="duplicate key"):
        module.build_reconciled_content(destination, selected)

    destination = destination.replace("SMTP_HOST=duplicate\n", "")
    content = module.build_reconciled_content(destination, selected)
    parsed = module.parse_env(content, label="result").values

    assert parsed["DATABASE_URL"] == "postgres://preserve"
    assert parsed["AUTH_PUBLIC_LOGIN"] == "1"
    assert parsed["SMTP_HOST"] == "smtp.example.test"
    assert "UNRELATED_SOURCE" not in parsed
    assert content.count("AUTH_PUBLIC_LOGIN=") == 1
    assert content.count("SMTP_HOST=") == 1


def test_dry_run_is_value_redacted_and_does_not_mutate(tmp_path: Path) -> None:
    module = load_module()
    source, destination, backup_dir = create_runtime_files(tmp_path)
    original = destination.read_bytes()

    receipt = preview(module, source, destination, backup_dir)

    serialized = json.dumps(receipt, sort_keys=True)
    assert receipt["status"] == "planned"
    assert receipt["applied"] is False
    assert receipt["values_redacted"] is True
    assert len(receipt["plan_sha256"]) == 64
    assert destination.read_bytes() == original
    assert list(backup_dir.iterdir()) == []
    assert SECRET_SENTINEL not in serialized


def test_dry_run_requires_root_in_production_mode(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    module = load_module()
    source, destination, backup_dir = create_runtime_files(tmp_path)
    monkeypatch.setattr(module.os, "geteuid", lambda: 1000)

    rc = module.main(
        [
            "--source",
            str(source),
            "--destination",
            str(destination),
            "--backup-dir",
            str(backup_dir),
            "--json",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 2
    assert "require root" in captured.err
    assert SECRET_SENTINEL not in captured.out
    assert SECRET_SENTINEL not in captured.err


def test_dry_run_requires_precreated_mode_0700_backup_directory(
    tmp_path: Path,
) -> None:
    module = load_module()
    source, destination, backup_dir = create_runtime_files(tmp_path)
    backup_dir.chmod(0o750)

    with pytest.raises(module.ReconcileError, match="mode 0700"):
        preview(module, source, destination, backup_dir)


def test_apply_requires_plan_hash_from_dry_run(tmp_path: Path) -> None:
    module = load_module()
    source, destination, backup_dir = create_runtime_files(tmp_path)
    original = destination.read_bytes()

    with pytest.raises(module.ReconcileError, match="requires --expected-plan"):
        module.reconcile(
            source_path=source,
            destination_path=destination,
            backup_dir=backup_dir,
            apply=True,
            require_root=False,
        )

    assert destination.read_bytes() == original
    assert list(backup_dir.iterdir()) == []


def test_apply_rejects_stale_plan_after_destination_change(tmp_path: Path) -> None:
    module = load_module()
    source, destination, backup_dir = create_runtime_files(tmp_path)
    receipt = preview(module, source, destination, backup_dir)
    destination.write_text(
        destination.read_text(encoding="utf-8") + "NEW_SETTING=changed\n",
        encoding="utf-8",
    )
    changed = destination.read_bytes()

    with pytest.raises(module.ReconcileError, match="does not match current inputs"):
        module.reconcile(
            source_path=source,
            destination_path=destination,
            backup_dir=backup_dir,
            apply=True,
            expected_plan_sha256=receipt["plan_sha256"],
            require_root=False,
        )

    assert destination.read_bytes() == changed
    assert list(backup_dir.iterdir()) == []


def test_apply_rejects_stale_plan_after_source_change(tmp_path: Path) -> None:
    module = load_module()
    source, destination, backup_dir = create_runtime_files(tmp_path)
    receipt = preview(module, source, destination, backup_dir)
    source.write_text(valid_source(port="587"), encoding="utf-8")

    with pytest.raises(module.ReconcileError, match="does not match current inputs"):
        module.reconcile(
            source_path=source,
            destination_path=destination,
            backup_dir=backup_dir,
            apply=True,
            expected_plan_sha256=receipt["plan_sha256"],
            require_root=False,
        )

    assert list(backup_dir.iterdir()) == []


def test_plan_hash_binds_all_effect_paths(tmp_path: Path) -> None:
    module = load_module()
    source, destination, backup_dir = create_runtime_files(tmp_path)
    source_stat = source.stat()
    destination_stat = destination.stat()
    backup_stat = backup_dir.stat()
    source_text = source.read_text(encoding="utf-8")
    destination_text = destination.read_text(encoding="utf-8")
    selected = module.validate_source(
        module.parse_env(source_text, label="source").values
    )
    planned = module.build_reconciled_content(destination_text, selected)

    def digest(
        source_path=source, destination_path=destination, backup_path=backup_dir
    ):
        return module.plan_sha256(
            source_path=source_path,
            destination_path=destination_path,
            backup_dir=backup_path,
            source_stat=source_stat,
            destination_stat=destination_stat,
            backup_dir_stat=backup_stat,
            source_text=source_text,
            destination_text=destination_text,
            planned_content=planned,
        )

    baseline = digest()
    assert digest(source_path=tmp_path / "other-source.env") != baseline
    assert digest(destination_path=tmp_path / "other-destination.env") != baseline
    assert digest(backup_path=tmp_path / "other-backups") != baseline


def test_plan_hash_rejects_unrelated_source_text_change(tmp_path: Path) -> None:
    module = load_module()
    source, destination, backup_dir = create_runtime_files(tmp_path)
    receipt = preview(module, source, destination, backup_dir)
    source.write_text(
        source.read_text(encoding="utf-8").replace(
            "UNRELATED_SOURCE=must-not-copy", "UNRELATED_SOURCE=changed"
        ),
        encoding="utf-8",
    )

    with pytest.raises(module.ReconcileError, match="does not match current inputs"):
        module.reconcile(
            source_path=source,
            destination_path=destination,
            backup_dir=backup_dir,
            apply=True,
            expected_plan_sha256=receipt["plan_sha256"],
            require_root=False,
        )

    assert list(backup_dir.iterdir()) == []


def test_plan_hash_binds_backup_path_and_identity(tmp_path: Path) -> None:
    module = load_module()
    source, destination, backup_dir = create_runtime_files(tmp_path)
    receipt = preview(module, source, destination, backup_dir)
    alternate_backup = tmp_path / "alternate-backups"
    alternate_backup.mkdir(mode=0o700)

    with pytest.raises(module.ReconcileError, match="does not match current inputs"):
        module.reconcile(
            source_path=source,
            destination_path=destination,
            backup_dir=alternate_backup,
            apply=True,
            expected_plan_sha256=receipt["plan_sha256"],
            require_root=False,
        )

    assert destination.read_text(encoding="utf-8").startswith("DATABASE_URL=")
    assert list(backup_dir.iterdir()) == []
    assert list(alternate_backup.iterdir()) == []


def test_plan_hash_rejects_identical_source_inode_replacement(tmp_path: Path) -> None:
    module = load_module()
    source, destination, backup_dir = create_runtime_files(tmp_path)
    receipt = preview(module, source, destination, backup_dir)
    replacement = tmp_path / "replacement.env"
    replacement.write_bytes(source.read_bytes())
    replacement.replace(source)

    with pytest.raises(module.ReconcileError, match="does not match current inputs"):
        module.reconcile(
            source_path=source,
            destination_path=destination,
            backup_dir=backup_dir,
            apply=True,
            expected_plan_sha256=receipt["plan_sha256"],
            require_root=False,
        )

    assert list(backup_dir.iterdir()) == []


def test_apply_creates_exact_backup_preserves_owner_and_forces_mode_0600(
    tmp_path: Path,
) -> None:
    module = load_module()
    source, destination, backup_dir = create_runtime_files(tmp_path)
    original = destination.read_bytes()
    original_stat = destination.stat()
    destination.chmod(0o640)

    dry_run, receipt = apply_preview(module, source, destination, backup_dir)

    serialized = json.dumps(receipt, sort_keys=True)
    backup = Path(receipt["backup"])
    assert dry_run["status"] == "planned"
    assert receipt["status"] == "reconciled"
    assert receipt["applied"] is True
    assert receipt["plan_sha256"] == dry_run["plan_sha256"]
    assert receipt["mode"] == "0600"
    assert receipt["owner_uid"] == original_stat.st_uid
    assert receipt["owner_gid"] == original_stat.st_gid
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert backup.read_bytes() == original
    assert stat.S_IMODE(backup.stat().st_mode) == 0o600
    assert SECRET_SENTINEL not in serialized


def test_apply_reports_only_actually_changed_keys(tmp_path: Path) -> None:
    module = load_module()
    selected = module.validate_source(
        module.parse_env(valid_source(), label="source").values
    )
    destination_text = "DATABASE_URL=postgres://preserve\n" + "\n".join(
        f"{key}={value}" for key, value in selected.items() if key != "SMTP_PORT"
    )
    destination_text += "\nSMTP_PORT=587\n"
    source, destination, backup_dir = create_runtime_files(
        tmp_path, destination_text=destination_text
    )

    dry_run, applied = apply_preview(module, source, destination, backup_dir)

    assert dry_run["updated_keys"] == ["SMTP_PORT"]
    assert applied["updated_keys"] == ["SMTP_PORT"]


def test_apply_is_idempotent_and_creates_no_second_backup(tmp_path: Path) -> None:
    module = load_module()
    source, destination, backup_dir = create_runtime_files(tmp_path)
    _, first = apply_preview(module, source, destination, backup_dir)
    second_preview = preview(module, source, destination, backup_dir)
    second = module.reconcile(
        source_path=source,
        destination_path=destination,
        backup_dir=backup_dir,
        apply=True,
        expected_plan_sha256=second_preview["plan_sha256"],
        require_root=False,
    )

    assert first["status"] == "reconciled"
    assert second_preview["status"] == "already_reconciled"
    assert second_preview["updated_keys"] == []
    assert second["status"] == "already_reconciled"
    assert second["updated_keys"] == []
    assert len(list(backup_dir.iterdir())) == 1


def test_read_regular_at_preserves_raw_bytes_and_rejects_no_newline_translation(
    tmp_path: Path,
) -> None:
    module = load_module()
    path = tmp_path / "raw.env"
    original = b"KEY=one\r\nOTHER=two\r"
    path.write_bytes(original)
    directory_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        opened = module._read_regular_at(
            directory_fd, path.name, label="raw", require_root=False
        )
    finally:
        os.close(directory_fd)

    assert opened.raw_bytes == original
    assert opened.text == original.decode("utf-8")


def test_destination_parent_open_failure_does_not_leak_source_directory_fd(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_module()
    source, destination, backup_dir = create_runtime_files(tmp_path)
    original_open = module._open_trusted_directory
    opened_source_fd: int | None = None

    def fail_destination(path, *, label, require_root, exact_mode=None):
        nonlocal opened_source_fd
        if label == "source parent directory":
            opened_source_fd = original_open(
                path, label=label, require_root=require_root, exact_mode=exact_mode
            )
            return opened_source_fd
        if label == "destination parent directory":
            raise module.ReconcileError("injected destination parent failure")
        return original_open(
            path, label=label, require_root=require_root, exact_mode=exact_mode
        )

    monkeypatch.setattr(module, "_open_trusted_directory", fail_destination)
    with pytest.raises(
        module.ReconcileError, match="injected destination parent failure"
    ):
        preview(module, source, destination, backup_dir)

    assert opened_source_fd is not None
    with pytest.raises(OSError):
        os.fstat(opened_source_fd)


@pytest.mark.parametrize("target", ["source", "destination"])
def test_final_file_symlink_is_rejected(tmp_path: Path, target: str) -> None:
    module = load_module()
    source, destination, backup_dir = create_runtime_files(tmp_path)
    selected = source if target == "source" else destination
    real = tmp_path / f"real-{target}.env"
    selected.replace(real)
    selected.symlink_to(real)

    with pytest.raises(module.ReconcileError, match=f"unable to open {target} safely"):
        preview(module, source, destination, backup_dir)


def test_intermediate_directory_symlink_is_rejected(tmp_path: Path) -> None:
    module = load_module()
    real_dir = tmp_path / "real"
    linked_dir = tmp_path / "linked"
    real_dir.mkdir()
    linked_dir.symlink_to(real_dir, target_is_directory=True)
    source = linked_dir / "legacy.env"
    destination = tmp_path / "canonical.env"
    backup_dir = tmp_path / "backups"
    (real_dir / "legacy.env").write_text(valid_source(), encoding="utf-8")
    destination.write_text("DATABASE_URL=postgres://preserve\n", encoding="utf-8")
    backup_dir.mkdir(mode=0o700)

    with pytest.raises(module.ReconcileError, match="source parent directory"):
        preview(module, source, destination, backup_dir)


def test_backup_directory_symlink_is_rejected(tmp_path: Path) -> None:
    module = load_module()
    source, destination, backup_dir = create_runtime_files(tmp_path)
    real_backup = tmp_path / "real-backups"
    backup_dir.rmdir()
    real_backup.mkdir(mode=0o700)
    backup_dir.symlink_to(real_backup, target_is_directory=True)

    with pytest.raises(module.ReconcileError, match="backup directory"):
        preview(module, source, destination, backup_dir)


def test_source_and_destination_hardlink_is_rejected(tmp_path: Path) -> None:
    module = load_module()
    source = tmp_path / "legacy.env"
    destination = tmp_path / "canonical.env"
    backup_dir = tmp_path / "backups"
    source.write_text(valid_source(), encoding="utf-8")
    os.link(source, destination)
    backup_dir.mkdir(mode=0o700)

    with pytest.raises(module.ReconcileError, match="must be different files"):
        preview(module, source, destination, backup_dir)


@pytest.mark.parametrize("which", ["source", "destination"])
def test_apply_rejects_inode_replacement_after_lock(
    tmp_path: Path, monkeypatch, which: str
) -> None:
    module = load_module()
    source, destination, backup_dir = create_runtime_files(tmp_path)
    receipt = preview(module, source, destination, backup_dir)
    replacement = tmp_path / f"replacement-{which}.env"
    if which == "source":
        replacement.write_text(valid_source(), encoding="utf-8")
        replace_target = source
    else:
        replacement.write_bytes(destination.read_bytes())
        replace_target = destination
    original_destination = destination.read_bytes()
    original_flock = module.fcntl.flock

    def replace_after_lock(fd, operation):
        original_flock(fd, operation)
        replacement.replace(replace_target)

    monkeypatch.setattr(module.fcntl, "flock", replace_after_lock)

    with pytest.raises(module.ReconcileError, match=f"{which} file identity changed"):
        module.reconcile(
            source_path=source,
            destination_path=destination,
            backup_dir=backup_dir,
            apply=True,
            expected_plan_sha256=receipt["plan_sha256"],
            require_root=False,
        )

    if which == "source":
        assert destination.read_bytes() == original_destination
    assert list(backup_dir.iterdir()) == []


@pytest.mark.parametrize("which", ["source", "destination"])
def test_apply_rejects_content_change_after_lock(
    tmp_path: Path, monkeypatch, which: str
) -> None:
    module = load_module()
    source, destination, backup_dir = create_runtime_files(tmp_path)
    receipt = preview(module, source, destination, backup_dir)
    original_flock = module.fcntl.flock

    def mutate_after_lock(fd, operation):
        original_flock(fd, operation)
        target = source if which == "source" else destination
        target.write_text(
            target.read_text(encoding="utf-8") + "# changed\n", encoding="utf-8"
        )

    monkeypatch.setattr(module.fcntl, "flock", mutate_after_lock)

    with pytest.raises(module.ReconcileError, match=f"{which} content changed"):
        module.reconcile(
            source_path=source,
            destination_path=destination,
            backup_dir=backup_dir,
            apply=True,
            expected_plan_sha256=receipt["plan_sha256"],
            require_root=False,
        )

    assert list(backup_dir.iterdir()) == []


def test_apply_revalidates_root_trust_after_lock(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    source, destination, backup_dir = create_runtime_files(tmp_path)
    original_read = module._read_regular_at
    read_calls = 0

    def root_bound_read(parent_fd, name, *, label, require_root):
        nonlocal read_calls
        read_calls += 1
        opened = original_read(parent_fd, name, label=label, require_root=False)
        fake_uid = 1000 if read_calls == 3 else 0
        fake_stat = stat_with(opened.file_stat, uid=fake_uid, gid=0)
        if require_root:
            module._validate_root_owned_stat(fake_stat, label=label)
        return module.OpenedEnv(
            raw_bytes=opened.raw_bytes, text=opened.text, file_stat=fake_stat
        )

    original_open_dir = module._open_trusted_directory

    def unprivileged_test_directory(path, *, label, require_root, exact_mode=None):
        return original_open_dir(
            path, label=label, require_root=False, exact_mode=exact_mode
        )

    monkeypatch.setattr(module, "_read_regular_at", root_bound_read)
    monkeypatch.setattr(module, "_open_trusted_directory", unprivileged_test_directory)
    monkeypatch.setattr(module.os, "geteuid", lambda: 0)
    original_validate = module._validate_root_owned_stat

    def allow_lock_only(file_stat, *, label):
        if label == "reconciliation lock":
            return None
        return original_validate(file_stat, label=label)

    monkeypatch.setattr(module, "_validate_root_owned_stat", allow_lock_only)

    receipt = module.reconcile(
        source_path=source,
        destination_path=destination,
        backup_dir=backup_dir,
        apply=False,
        require_root=True,
    )
    read_calls = 0

    with pytest.raises(module.ReconcileError, match="source must be root-owned"):
        module.reconcile(
            source_path=source,
            destination_path=destination,
            backup_dir=backup_dir,
            apply=True,
            expected_plan_sha256=receipt["plan_sha256"],
            require_root=True,
        )

    assert read_calls >= 3
    assert list(backup_dir.iterdir()) == []


def test_apply_acquires_exclusive_lock(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    source, destination, backup_dir = create_runtime_files(tmp_path)
    receipt = preview(module, source, destination, backup_dir)
    operations: list[int] = []
    original_flock = module.fcntl.flock

    def record_lock(fd, operation):
        operations.append(operation)
        return original_flock(fd, operation)

    monkeypatch.setattr(module.fcntl, "flock", record_lock)

    module.reconcile(
        source_path=source,
        destination_path=destination,
        backup_dir=backup_dir,
        apply=True,
        expected_plan_sha256=receipt["plan_sha256"],
        require_root=False,
    )

    assert operations == [module.fcntl.LOCK_EX | module.fcntl.LOCK_NB]


def test_lock_wait_times_out_without_mutation(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    source, destination, backup_dir = create_runtime_files(tmp_path)
    receipt = preview(module, source, destination, backup_dir)
    original = destination.read_bytes()
    monkeypatch.setattr(module, "LOCK_TIMEOUT_SECONDS", 0.0)

    def always_busy(fd, operation):
        raise BlockingIOError("busy")

    monkeypatch.setattr(module.fcntl, "flock", always_busy)

    with pytest.raises(module.ReconcileError, match="timed out waiting"):
        module.reconcile(
            source_path=source,
            destination_path=destination,
            backup_dir=backup_dir,
            apply=True,
            expected_plan_sha256=receipt["plan_sha256"],
            require_root=False,
        )

    assert destination.read_bytes() == original
    assert list(backup_dir.iterdir()) == []


def test_partial_temp_write_is_removed_before_error_returns(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_module()
    source, destination, backup_dir = create_runtime_files(tmp_path)
    receipt = preview(module, source, destination, backup_dir)
    original = destination.read_bytes()
    original_fchown = module.os.fchown
    calls = 0

    def fail_temp_chown(fd, uid, gid):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected temp write failure")
        return original_fchown(fd, uid, gid)

    monkeypatch.setattr(module.os, "fchown", fail_temp_chown)

    with pytest.raises(OSError, match="injected temp write failure"):
        module.reconcile(
            source_path=source,
            destination_path=destination,
            backup_dir=backup_dir,
            apply=True,
            expected_plan_sha256=receipt["plan_sha256"],
            require_root=False,
        )

    assert destination.read_bytes() == original
    assert not list(destination.parent.glob(f".{destination.name}.reconcile-*"))
    backups = list(backup_dir.iterdir())
    assert len(backups) == 1
    assert backups[0].read_bytes() == original


def test_backup_is_read_back_before_destination_replace(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_module()
    source, destination, backup_dir = create_runtime_files(tmp_path)
    receipt = preview(module, source, destination, backup_dir)
    original = destination.read_bytes()
    original_read = module._read_regular_at

    def corrupt_backup(parent_fd, name, *, label, require_root):
        opened = original_read(parent_fd, name, label=label, require_root=require_root)
        if label == "backup":
            return module.OpenedEnv(
                raw_bytes=opened.raw_bytes + b"# corrupt\n",
                text=opened.text + "# corrupt\n",
                file_stat=opened.file_stat,
            )
        return opened

    monkeypatch.setattr(module, "_read_regular_at", corrupt_backup)

    with pytest.raises(module.ReconcileError, match="backup verification failed"):
        module.reconcile(
            source_path=source,
            destination_path=destination,
            backup_dir=backup_dir,
            apply=True,
            expected_plan_sha256=receipt["plan_sha256"],
            require_root=False,
        )

    assert destination.read_bytes() == original
    assert list(backup_dir.iterdir()) == []


def test_safe_orphan_temp_is_removed_under_lock(tmp_path: Path) -> None:
    module = load_module()
    source, destination, backup_dir = create_runtime_files(tmp_path)
    orphan = destination.parent / f".{destination.name}.reconcile-stale"
    orphan.write_text(SECRET_SENTINEL, encoding="utf-8")
    orphan.chmod(0o600)

    apply_preview(module, source, destination, backup_dir)

    assert not orphan.exists()


def test_unsafe_orphan_temp_is_not_removed(tmp_path: Path) -> None:
    module = load_module()
    source, destination, backup_dir = create_runtime_files(tmp_path)
    orphan = destination.parent / f".{destination.name}.reconcile-unsafe"
    orphan.write_text("preserve", encoding="utf-8")
    orphan.chmod(0o644)

    apply_preview(module, source, destination, backup_dir)

    assert orphan.read_text(encoding="utf-8") == "preserve"


def test_root_owned_stat_rejects_untrusted_owner_and_write_bits() -> None:
    module = load_module()
    base = os.stat(__file__)

    with pytest.raises(module.ReconcileError, match="must be root-owned"):
        module._validate_root_owned_stat(stat_with(base, uid=1000), label="source")
    with pytest.raises(module.ReconcileError, match="group or others"):
        module._validate_root_owned_stat(
            stat_with(base, uid=0, mode=base.st_mode | stat.S_IWGRP),
            label="source",
        )


def test_documented_workflow_relates_script_test_and_ci() -> None:
    docs = (REPO / "docs" / "deploy" / "vps.md").read_text(encoding="utf-8")
    workflow = (
        REPO / ".github" / "workflows" / "public-login-smtp-readiness.yml"
    ).read_text(encoding="utf-8")

    assert "scripts/ops/reconcile_public_login_smtp_env.py" in docs
    assert "--expected-plan-sha256" in docs
    assert "Restore" in docs
    assert "scripts/ops/reconcile_public_login_smtp_env.py" in workflow
    assert "scripts/ci/tests/test_reconcile_public_login_smtp_env.py" in workflow
    assert "test_reconcile_public_login_smtp_env.py" in workflow


def test_app_base_url_is_canonical_independent_of_source_value() -> None:
    module = load_module()
    values = module.parse_env(
        valid_source(app_base_url="https://weltgewebe.net"), label="source"
    ).values

    selected = module.validate_source(values)

    assert selected["APP_BASE_URL"] == "https://commonthing.net"


def test_reconcile_replaces_only_legacy_app_base_url_and_is_idempotent(
    tmp_path: Path,
) -> None:
    module = load_module()
    selected = module.validate_source(
        module.parse_env(valid_source(), label="source").values
    )
    destination_text = "DATABASE_URL=postgres://preserve\n" + "\n".join(
        f"{key}={value}" for key, value in selected.items()
    )
    destination_text = destination_text.replace(
        "APP_BASE_URL=https://commonthing.net",
        "APP_BASE_URL=https://weltgewebe.net",
    ) + "\n"
    source, destination, backup_dir = create_runtime_files(
        tmp_path, destination_text=destination_text
    )

    dry_run, applied = apply_preview(module, source, destination, backup_dir)
    second = preview(module, source, destination, backup_dir)

    assert dry_run["updated_keys"] == ["APP_BASE_URL"]
    assert applied["updated_keys"] == ["APP_BASE_URL"]
    assert module.parse_env(destination.read_text(encoding="utf-8"), label="result").values[
        "APP_BASE_URL"
    ] == "https://commonthing.net"
    assert second["status"] == "already_reconciled"
    assert second["updated_keys"] == []


@pytest.mark.parametrize(
    "sender",
    ["noreply@login.commonthing.net", "noreply@login.weltgewebe.net"],
)
def test_smtp_from_override_accepts_declared_cutover_senders(
    tmp_path: Path, sender: str
) -> None:
    module = load_module()
    source, destination, backup_dir = create_runtime_files(
        tmp_path,
        source_text=valid_source(smtp_from="noreply@login.weltgewebe.net"),
    )

    _, applied = apply_preview(
        module,
        source,
        destination,
        backup_dir,
        smtp_from_override=sender,
    )
    values = module.parse_env(destination.read_text(encoding="utf-8"), label="result").values

    assert applied["status"] == "reconciled"
    assert values["SMTP_FROM"] == sender
    assert values["APP_BASE_URL"] == "https://commonthing.net"


def test_smtp_from_override_rejects_unknown_sender_without_secret_output(
    tmp_path: Path,
) -> None:
    module = load_module()
    source, destination, backup_dir = create_runtime_files(tmp_path)

    with pytest.raises(module.ReconcileError, match="not an approved sender") as exc_info:
        preview(
            module,
            source,
            destination,
            backup_dir,
            smtp_from_override="noreply@untrusted.example",
        )

    assert SECRET_SENTINEL not in str(exc_info.value)
    assert list(backup_dir.iterdir()) == []


def test_plan_hash_binds_smtp_from_override_and_rejects_mismatched_apply(
    tmp_path: Path,
) -> None:
    module = load_module()
    source, destination, backup_dir = create_runtime_files(
        tmp_path,
        source_text=valid_source(smtp_from="noreply@login.weltgewebe.net"),
    )
    commonthing = preview(
        module,
        source,
        destination,
        backup_dir,
        smtp_from_override="noreply@login.commonthing.net",
    )
    legacy = preview(
        module,
        source,
        destination,
        backup_dir,
        smtp_from_override="noreply@login.weltgewebe.net",
    )

    assert commonthing["plan_sha256"] != legacy["plan_sha256"]

    with pytest.raises(module.ReconcileError, match="does not match current inputs"):
        module.reconcile(
            source_path=source,
            destination_path=destination,
            backup_dir=backup_dir,
            apply=True,
            expected_plan_sha256=commonthing["plan_sha256"],
            smtp_from_override="noreply@login.weltgewebe.net",
            require_root=False,
        )

    assert list(backup_dir.iterdir()) == []
