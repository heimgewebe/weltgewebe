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


def _compose_with_env_file(
    tmp_path: pathlib.Path,
    env_file: pathlib.Path,
    environment: str = "",
) -> pathlib.Path:
    lines = [
        "services:",
        "  api:",
        "    env_file:",
        "      - ${WELTGEWEBE_ENV_FILE:-/etc/weltgewebe/weltgewebe.env}",
    ]
    extra = textwrap.dedent(environment).strip()
    if extra:
        lines.extend(f"    {line}" for line in extra.splitlines())
    return _write(tmp_path / "compose.yml", "\n".join(lines) + "\n")


def test_accepts_verify_applied_from_selected_env_file(tmp_path: pathlib.Path) -> None:
    module = _load_module()
    env_file = _write(
        tmp_path / ".env",
        """
        OTHER_KEY=redacted-example
        WELTGEWEBE_API_STARTUP_MIGRATIONS=verify-applied
        """,
    )
    compose = _compose_with_env_file(
        tmp_path,
        env_file,
        """
        environment:
          APP_BASE_URL: https://commonthing.net
        """,
    )

    result = module.validate_boundary(
        compose_source=compose,
        env_file=env_file,
        compose_env={"WELTGEWEBE_ENV_FILE": str(env_file)},
    )

    assert result.observed_mode == "verify-applied"
    assert result.has_env_file_hook is True
    assert result.has_service_environment_override is False
    assert pathlib.Path(result.env_file) == env_file.resolve()


def test_repo_vps_override_accepts_selected_env_file_without_service_migration_override(tmp_path: pathlib.Path) -> None:
    module = _load_module()
    repo = pathlib.Path(__file__).resolve().parents[3]
    compose = repo / "infra" / "compose" / "compose.vps.override.yml"
    env_file = _write(
        tmp_path / ".env",
        """
        WELTGEWEBE_API_STARTUP_MIGRATIONS=verify-applied
        APP_BASE_URL=https://commonthing.net
        """,
    )

    result = module.validate_boundary(
        compose_source=compose,
        env_file=env_file,
        compose_env={"WELTGEWEBE_ENV_FILE": str(env_file)},
    )

    assert result.observed_mode == "verify-applied"
    assert result.has_env_file_hook is True
    assert result.has_service_environment_override is False
    assert pathlib.Path(result.env_file) == env_file.resolve()


def test_rejects_service_environment_override_map_syntax(tmp_path: pathlib.Path) -> None:
    module = _load_module()
    env_file = _write(
        tmp_path / ".env",
        "WELTGEWEBE_API_STARTUP_MIGRATIONS=verify-applied\n",
    )
    compose = _compose_with_env_file(
        tmp_path,
        env_file,
        """
        environment:
          WELTGEWEBE_API_STARTUP_MIGRATIONS: ${WELTGEWEBE_API_STARTUP_MIGRATIONS:-run}
        """,
    )

    try:
        module.validate_boundary(
            compose_source=compose,
            env_file=env_file,
            compose_env={"WELTGEWEBE_ENV_FILE": str(env_file)},
        )
    except module.BoundaryCheckError as error:
        assert "override env_file" in str(error)
    else:
        raise AssertionError("service-level migration override must fail closed")


def test_rejects_service_environment_override_array_assignment(tmp_path: pathlib.Path) -> None:
    module = _load_module()
    env_file = _write(
        tmp_path / ".env",
        "WELTGEWEBE_API_STARTUP_MIGRATIONS=verify-applied\n",
    )
    compose = _compose_with_env_file(
        tmp_path,
        env_file,
        """
        environment:
          - WELTGEWEBE_API_STARTUP_MIGRATIONS=run
        """,
    )

    try:
        module.validate_boundary(
            compose_source=compose,
            env_file=env_file,
            compose_env={"WELTGEWEBE_ENV_FILE": str(env_file)},
        )
    except module.BoundaryCheckError as error:
        assert "override env_file" in str(error)
    else:
        raise AssertionError("array-form migration override must fail closed")


def test_rejects_service_environment_override_array_bare_key(tmp_path: pathlib.Path) -> None:
    module = _load_module()
    env_file = _write(
        tmp_path / ".env",
        "WELTGEWEBE_API_STARTUP_MIGRATIONS=verify-applied\n",
    )
    compose = _compose_with_env_file(
        tmp_path,
        env_file,
        """
        environment:
          - WELTGEWEBE_API_STARTUP_MIGRATIONS
        """,
    )

    try:
        module.validate_boundary(
            compose_source=compose,
            env_file=env_file,
            compose_env={"WELTGEWEBE_ENV_FILE": str(env_file)},
        )
    except module.BoundaryCheckError as error:
        assert "override env_file" in str(error)
    else:
        raise AssertionError("bare array-form migration override must fail closed")


def test_rejects_quoted_array_assignment_with_inline_comment(tmp_path: pathlib.Path) -> None:
    module = _load_module()
    env_file = _write(
        tmp_path / ".env",
        "WELTGEWEBE_API_STARTUP_MIGRATIONS=verify-applied\n",
    )
    compose = _compose_with_env_file(
        tmp_path,
        env_file,
        """
        environment:
          - "WELTGEWEBE_API_STARTUP_MIGRATIONS=run" # documented override
        """,
    )

    try:
        module.validate_boundary(
            compose_source=compose,
            env_file=env_file,
            compose_env={"WELTGEWEBE_ENV_FILE": str(env_file)},
        )
    except module.BoundaryCheckError as error:
        assert "override env_file" in str(error)
    else:
        raise AssertionError("quoted array-form override with comment must fail closed")


def test_rejects_bare_array_key_with_inline_comment(tmp_path: pathlib.Path) -> None:
    module = _load_module()
    env_file = _write(
        tmp_path / ".env",
        "WELTGEWEBE_API_STARTUP_MIGRATIONS=verify-applied\n",
    )
    compose = _compose_with_env_file(
        tmp_path,
        env_file,
        """
        environment:
          - WELTGEWEBE_API_STARTUP_MIGRATIONS # inherited from shell
        """,
    )

    try:
        module.validate_boundary(
            compose_source=compose,
            env_file=env_file,
            compose_env={"WELTGEWEBE_ENV_FILE": str(env_file)},
        )
    except module.BoundaryCheckError as error:
        assert "override env_file" in str(error)
    else:
        raise AssertionError("bare array-form override with comment must fail closed")


def test_rejects_missing_effective_env_file_key(tmp_path: pathlib.Path) -> None:
    module = _load_module()
    env_file = _write(tmp_path / ".env", "APP_BASE_URL=https://commonthing.net\n")
    compose = _compose_with_env_file(
        tmp_path,
        env_file,
        """
        environment:
          APP_BASE_URL: https://commonthing.net
        """,
    )

    try:
        module.validate_boundary(
            compose_source=compose,
            env_file=env_file,
            compose_env={"WELTGEWEBE_ENV_FILE": str(env_file)},
        )
    except module.BoundaryCheckError as error:
        assert "effective env_file set does not set WELTGEWEBE_API_STARTUP_MIGRATIONS" in str(error)
    else:
        raise AssertionError("missing migration mode must fail closed")


def test_rejects_duplicate_key_in_selected_env_file(tmp_path: pathlib.Path) -> None:
    module = _load_module()
    env_file = _write(
        tmp_path / ".env",
        """
        WELTGEWEBE_API_STARTUP_MIGRATIONS=verify-applied
        WELTGEWEBE_API_STARTUP_MIGRATIONS=run
        """,
    )
    compose = _compose_with_env_file(tmp_path, env_file)

    try:
        module.validate_boundary(
            compose_source=compose,
            env_file=env_file,
            compose_env={"WELTGEWEBE_ENV_FILE": str(env_file)},
        )
    except module.BoundaryCheckError as error:
        assert "more than once" in str(error)
    else:
        raise AssertionError("duplicate migration mode must fail closed")


def test_accepts_quoted_dotenv_value(tmp_path: pathlib.Path) -> None:
    module = _load_module()
    env_file = _write(
        tmp_path / ".env",
        'WELTGEWEBE_API_STARTUP_MIGRATIONS="verify-applied"\n',
    )
    compose = _compose_with_env_file(tmp_path, env_file)

    result = module.validate_boundary(
        compose_source=compose,
        env_file=env_file,
        compose_env={"WELTGEWEBE_ENV_FILE": str(env_file)},
    )

    assert result.observed_mode == "verify-applied"


def test_accepts_colon_dotenv_value(tmp_path: pathlib.Path) -> None:
    module = _load_module()
    env_file = _write(
        tmp_path / ".env",
        "WELTGEWEBE_API_STARTUP_MIGRATIONS: verify-applied\n",
    )
    compose = _compose_with_env_file(tmp_path, env_file)

    result = module.validate_boundary(
        compose_source=compose,
        env_file=env_file,
        compose_env={"WELTGEWEBE_ENV_FILE": str(env_file)},
    )

    assert result.observed_mode == "verify-applied"


def test_accepts_unquoted_inline_comment_after_space(tmp_path: pathlib.Path) -> None:
    module = _load_module()
    env_file = _write(
        tmp_path / ".env",
        "WELTGEWEBE_API_STARTUP_MIGRATIONS=verify-applied # approved smoke\n",
    )
    compose = _compose_with_env_file(tmp_path, env_file)

    result = module.validate_boundary(
        compose_source=compose,
        env_file=env_file,
        compose_env={"WELTGEWEBE_ENV_FILE": str(env_file)},
    )

    assert result.observed_mode == "verify-applied"


def test_does_not_treat_hash_without_space_as_inline_comment(tmp_path: pathlib.Path) -> None:
    module = _load_module()
    env_file = _write(
        tmp_path / ".env",
        "WELTGEWEBE_API_STARTUP_MIGRATIONS=verify-applied#not-comment\n",
    )
    compose = _compose_with_env_file(tmp_path, env_file)

    try:
        module.validate_boundary(
            compose_source=compose,
            env_file=env_file,
            compose_env={"WELTGEWEBE_ENV_FILE": str(env_file)},
        )
    except module.BoundaryCheckError as error:
        assert "non-approved value" in str(error)
    else:
        raise AssertionError("hash without preceding space must not be stripped")


def test_accepts_quoted_value_with_trailing_comment(tmp_path: pathlib.Path) -> None:
    module = _load_module()
    env_file = _write(
        tmp_path / ".env",
        'WELTGEWEBE_API_STARTUP_MIGRATIONS="verify-applied" # approved smoke\n',
    )
    compose = _compose_with_env_file(tmp_path, env_file)

    result = module.validate_boundary(
        compose_source=compose,
        env_file=env_file,
        compose_env={"WELTGEWEBE_ENV_FILE": str(env_file)},
    )

    assert result.observed_mode == "verify-applied"


def test_rejects_env_file_that_is_not_effective_compose_source(tmp_path: pathlib.Path) -> None:
    module = _load_module()
    checked_env = _write(
        tmp_path / "checked.env",
        "WELTGEWEBE_API_STARTUP_MIGRATIONS=verify-applied\n",
    )
    effective_env = _write(
        tmp_path / "effective.env",
        "WELTGEWEBE_API_STARTUP_MIGRATIONS=verify-applied\n",
    )
    compose = _write(
        tmp_path / "compose.yml",
        f"""
        services:
          api:
            env_file:
              - {effective_env}
        """,
    )

    try:
        module.validate_boundary(compose_source=compose, env_file=checked_env)
    except module.BoundaryCheckError as error:
        assert "not the effective env_file source" in str(error)
    else:
        raise AssertionError("checked env file must be bound to compose env_file source")


def test_multiple_env_files_later_value_wins(tmp_path: pathlib.Path) -> None:
    module = _load_module()
    base_env = _write(tmp_path / "base.env", "WELTGEWEBE_API_STARTUP_MIGRATIONS=run\n")
    selected_env = _write(
        tmp_path / "selected.env",
        "WELTGEWEBE_API_STARTUP_MIGRATIONS=verify-applied\n",
    )
    compose = _write(
        tmp_path / "compose.yml",
        f"""
        services:
          api:
            env_file:
              - {base_env}
              - {selected_env}
        """,
    )

    result = module.validate_boundary(compose_source=compose, env_file=selected_env)

    assert result.observed_mode == "verify-applied"
    assert pathlib.Path(result.env_file) == selected_env.resolve()


def test_rejects_selected_env_file_when_later_env_file_wins(tmp_path: pathlib.Path) -> None:
    module = _load_module()
    selected_env = _write(
        tmp_path / "selected.env",
        "WELTGEWEBE_API_STARTUP_MIGRATIONS=verify-applied\n",
    )
    later_env = _write(tmp_path / "later.env", "WELTGEWEBE_API_STARTUP_MIGRATIONS=run\n")
    compose = _write(
        tmp_path / "compose.yml",
        f"""
        services:
          api:
            env_file:
              - {selected_env}
              - {later_env}
        """,
    )

    try:
        module.validate_boundary(compose_source=compose, env_file=selected_env)
    except module.BoundaryCheckError as error:
        assert "not the effective env_file source" in str(error)
    else:
        raise AssertionError("selected env file must be the effective source")
