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


def _kv() -> tuple[str, str, str]:
    return "services", "env" + "_file", "environ" + "ment"


def test_accepts_compose_selected_file_default(tmp_path: pathlib.Path) -> None:
    module = _load_module()
    services, env_file_key, _environment = _kv()
    mode_key = module.MIGRATION_MODE_KEY
    selected = _write(tmp_path / "selected.cfg", f"{mode_key}=verify-applied\n")
    compose = _write(
        tmp_path / "compose.yml",
        f"""
        {services}:
          api:
            {env_file_key}:
              - ${{WELTGEWEBE_ENV_FILE:-{selected}}}
        """,
    )

    result = module.validate_boundary(compose_source=compose, env_file=selected)
    assert result.observed_mode == "verify-applied"


def test_accepts_quoted_mapping_keys(tmp_path: pathlib.Path) -> None:
    module = _load_module()
    services, env_file_key, _environment = _kv()
    mode_key = module.MIGRATION_MODE_KEY
    selected = _write(tmp_path / "selected.cfg", f"{mode_key}=verify-applied\n")
    compose = _write(
        tmp_path / "compose.yml",
        f"""
        "{services}":
          "api":
            '{env_file_key}':
              - {selected}
        """,
    )

    result = module.validate_boundary(compose_source=compose, env_file=selected)
    assert result.observed_mode == "verify-applied"


def test_rejects_quoted_service_mapping_override(tmp_path: pathlib.Path) -> None:
    module = _load_module()
    services, env_file_key, environment = _kv()
    mode_key = module.MIGRATION_MODE_KEY
    selected = _write(tmp_path / "selected.cfg", f"{mode_key}=verify-applied\n")
    compose = _write(
        tmp_path / "compose.yml",
        f"""
        {services}:
          api:
            {env_file_key}:
              - {selected}
            "{environment}":
              '{mode_key}': run
        """,
    )

    try:
        module.validate_boundary(compose_source=compose, env_file=selected)
    except module.BoundaryCheckError as error:
        assert "override env_file" in str(error)
    else:
        raise AssertionError("quoted mapping override must not pass")


def test_ignores_nested_service_name(tmp_path: pathlib.Path) -> None:
    module = _load_module()
    services, env_file_key, _environment = _kv()
    mode_key = module.MIGRATION_MODE_KEY
    selected = _write(tmp_path / "selected.cfg", f"{mode_key}=verify-applied\n")
    compose = _write(
        tmp_path / "compose.yml",
        f"""
        {services}:
          web:
            depends_on:
              api:
                condition: service_started
          api:
            {env_file_key}:
              - {selected}
        """,
    )

    result = module.validate_boundary(compose_source=compose, env_file=selected)
    assert result.observed_mode == "verify-applied"


def test_ignores_nested_environment_name(tmp_path: pathlib.Path) -> None:
    module = _load_module()
    services, env_file_key, environment = _kv()
    mode_key = module.MIGRATION_MODE_KEY
    selected = _write(tmp_path / "selected.cfg", f"{mode_key}=verify-applied\n")
    compose = _write(
        tmp_path / "compose.yml",
        f"""
        {services}:
          api:
            deploy:
              labels:
                {environment}: fake
            {env_file_key}:
              - {selected}
        """,
    )

    result = module.validate_boundary(compose_source=compose, env_file=selected)
    assert result.observed_mode == "verify-applied"
