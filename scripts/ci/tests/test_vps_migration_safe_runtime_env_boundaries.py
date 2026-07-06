from __future__ import annotations

import importlib.util
import pathlib
import sys
import textwrap


def _load_module():
    repo = pathlib.Path(__file__).resolve().parents[3]
    script = repo / "scripts" / "ops" / "check_vps_migration_safe_runtime_env.py"
    spec = importlib.util.spec_from_file_location("check_vps_migration_safe_runtime_env", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write(path: pathlib.Path, text: str) -> pathlib.Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")
    return path


def _compose_with_env_file(tmp_path: pathlib.Path, entry: str) -> pathlib.Path:
    return _write(
        tmp_path / "compose.yml",
        f"""
        services:
          api:
            env_file:
              - {entry}
        """,
    )


def test_accepts_tilde_env_file_entry_after_expanding_home(
    tmp_path: pathlib.Path,
    monkeypatch,
) -> None:
    module = _load_module()
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    selected = _write(
        home / ".weltgewebe-test.env",
        "WELTGEWEBE_API_STARTUP_MIGRATIONS=verify-applied\n",
    )
    compose = _compose_with_env_file(tmp_path, "~/.weltgewebe-test.env")

    result = module.validate_boundary(compose_source=compose, env_file=selected)

    assert result.observed_mode == "verify-applied"
    assert pathlib.Path(result.env_file) == selected.resolve()


def test_rejects_export_prefix_for_migration_mode_key(tmp_path: pathlib.Path) -> None:
    module = _load_module()
    selected = _write(
        tmp_path / ".env",
        "export WELTGEWEBE_API_STARTUP_MIGRATIONS=verify-applied\n",
    )
    compose = _compose_with_env_file(tmp_path, str(selected))

    try:
        module.validate_boundary(compose_source=compose, env_file=selected)
    except module.BoundaryCheckError as error:
        assert "export" in str(error)
    else:
        raise AssertionError("shell-style export for the migration mode key must fail closed")


def test_rejects_multiline_quoted_dotenv_value_before_checked_key(
    tmp_path: pathlib.Path,
) -> None:
    module = _load_module()
    selected = _write(
        tmp_path / ".env",
        """
        OTHER_KEY="first line
        WELTGEWEBE_API_STARTUP_MIGRATIONS=verify-applied
        "
        """,
    )
    compose = _compose_with_env_file(tmp_path, str(selected))

    try:
        module.validate_boundary(compose_source=compose, env_file=selected)
    except module.BoundaryCheckError as error:
        assert "unterminated quoted dotenv value" in str(error)
    else:
        raise AssertionError("multi-line dotenv values must fail closed before key scanning")
