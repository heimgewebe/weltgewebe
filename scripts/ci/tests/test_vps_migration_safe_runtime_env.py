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
    path.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")
    return path


def test_accepts_verify_applied_from_selected_env_file(tmp_path: pathlib.Path) -> None:
    module = _load_module()
    compose = _write(
        tmp_path / "compose.yml",
        """
        services:
          api:
            env_file:
              - ${WELTGEWEBE_ENV_FILE:-/opt/weltgewebe/.env}
            environment:
              APP_BASE_URL: https://weltgewebe.net
        """,
    )
    env_file = _write(
        tmp_path / ".env",
        """
        DATABASE_URL=postgres://redacted-example
        WELTGEWEBE_API_STARTUP_MIGRATIONS=verify-applied
        """,
    )

    result = module.validate_boundary(compose_source=compose, env_file=env_file)

    assert result.observed_mode == "verify-applied"
    assert result.has_env_file_hook is True
    assert result.has_service_environment_override is False


def test_rejects_service_environment_override(tmp_path: pathlib.Path) -> None:
    module = _load_module()
    compose = _write(
        tmp_path / "compose.yml",
        """
        services:
          api:
            env_file:
              - /opt/weltgewebe/.env
            environment:
              WELTGEWEBE_API_STARTUP_MIGRATIONS: ${WELTGEWEBE_API_STARTUP_MIGRATIONS:-run}
        """,
    )
    env_file = _write(tmp_path / ".env", "WELTGEWEBE_API_STARTUP_MIGRATIONS=verify-applied\n")

    try:
        module.validate_boundary(compose_source=compose, env_file=env_file)
    except module.BoundaryCheckError as error:
        assert "override env_file" in str(error)
    else:
        raise AssertionError("service-level migration override must fail closed")


def test_rejects_missing_selected_env_file_key(tmp_path: pathlib.Path) -> None:
    module = _load_module()
    compose = _write(
        tmp_path / "compose.yml",
        """
        services:
          api:
            env_file:
              - /opt/weltgewebe/.env
            environment:
              APP_BASE_URL: https://weltgewebe.net
        """,
    )
    env_file = _write(tmp_path / ".env", "APP_BASE_URL=https://weltgewebe.net\n")

    try:
        module.validate_boundary(compose_source=compose, env_file=env_file)
    except module.BoundaryCheckError as error:
        assert "does not set WELTGEWEBE_API_STARTUP_MIGRATIONS" in str(error)
    else:
        raise AssertionError("missing migration mode must fail closed")


def test_rejects_duplicate_selected_env_file_key(tmp_path: pathlib.Path) -> None:
    module = _load_module()
    compose = _write(
        tmp_path / "compose.yml",
        """
        services:
          api:
            env_file:
              - /opt/weltgewebe/.env
            environment:
              APP_BASE_URL: https://weltgewebe.net
        """,
    )
    env_file = _write(
        tmp_path / ".env",
        """
        WELTGEWEBE_API_STARTUP_MIGRATIONS=verify-applied
        WELTGEWEBE_API_STARTUP_MIGRATIONS=run
        """,
    )

    try:
        module.validate_boundary(compose_source=compose, env_file=env_file)
    except module.BoundaryCheckError as error:
        assert "more than once" in str(error)
    else:
        raise AssertionError("duplicate migration mode must fail closed")


def test_accepts_quoted_dotenv_value(tmp_path: pathlib.Path) -> None:
    module = _load_module()
    compose = _write(
        tmp_path / "compose.yml",
        """
        services:
          api:
            env_file:
              - /opt/weltgewebe/.env
        """,
    )
    env_file = _write(
        tmp_path / ".env",
        'WELTGEWEBE_API_STARTUP_MIGRATIONS="verify-applied"\n',
    )

    result = module.validate_boundary(compose_source=compose, env_file=env_file)

    assert result.observed_mode == "verify-applied"
