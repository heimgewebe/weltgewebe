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


def test_rejects_service_level_yaml_merge(tmp_path: pathlib.Path) -> None:
    module = _load_module()
    mode_key = module.MIGRATION_MODE_KEY
    selected = _write(tmp_path / "selected.env", f"{mode_key}=verify-applied\n")
    compose = _write(
        tmp_path / "compose.yml",
        f"""
        x-base: &base
          environment:
            {mode_key}: run
        services:
          api:
            <<: *base
            env_file:
              - {selected}
        """,
    )

    try:
        module.validate_boundary(compose_source=compose, env_file=selected)
    except module.BoundaryCheckError as error:
        assert "YAML merge" in str(error)
    else:
        raise AssertionError("service-level merge must fail closed")


def test_rejects_service_level_environment_alias(tmp_path: pathlib.Path) -> None:
    module = _load_module()
    mode_key = module.MIGRATION_MODE_KEY
    selected = _write(tmp_path / "selected.env", f"{mode_key}=verify-applied\n")
    compose = _write(
        tmp_path / "compose.yml",
        f"""
        x-env: &env
          {mode_key}: run
        services:
          api:
            environment: *env
            env_file:
              - {selected}
        """,
    )

    try:
        module.validate_boundary(compose_source=compose, env_file=selected)
    except module.BoundaryCheckError as error:
        assert "YAML merge" in str(error) or "anchor" in str(error)
    else:
        raise AssertionError("service-level environment alias must fail closed")


def test_rejects_service_extends_that_can_import_environment(
    tmp_path: pathlib.Path,
) -> None:
    module = _load_module()
    mode_key = module.MIGRATION_MODE_KEY
    selected = _write(tmp_path / "selected.env", f"{mode_key}=verify-applied\n")
    compose = _write(
        tmp_path / "compose.yml",
        f"""
        services:
          api-base:
            environment:
              {mode_key}: run
          api:
            extends:
              service: api-base
            env_file:
              - {selected}
        """,
    )

    try:
        module.validate_boundary(compose_source=compose, env_file=selected)
    except module.BoundaryCheckError as error:
        assert "extends" in str(error)
    else:
        raise AssertionError("service-level extends must fail closed")


def test_rejects_required_compose_interpolation_in_env_file(
    tmp_path: pathlib.Path,
) -> None:
    module = _load_module()
    mode_key = module.MIGRATION_MODE_KEY
    selected = _write(tmp_path / "selected.env", f"{mode_key}=verify-applied\n")
    compose = _write(
        tmp_path / "compose.yml",
        """
        services:
          api:
            env_file:
              - ${WELTGEWEBE_ENV_FILE:?required}
        """,
    )

    try:
        module.validate_boundary(compose_source=compose, env_file=selected)
    except module.BoundaryCheckError as error:
        assert "unsupported compose env_file variable syntax" in str(error)
    else:
        raise AssertionError("required interpolation must fail closed")


def test_rejects_alternative_compose_interpolation_in_env_file(
    tmp_path: pathlib.Path,
) -> None:
    module = _load_module()
    mode_key = module.MIGRATION_MODE_KEY
    selected = _write(tmp_path / "selected.env", f"{mode_key}=verify-applied\n")
    compose = _write(
        tmp_path / "compose.yml",
        """
        services:
          api:
            env_file:
              - ${WELTGEWEBE_ENV_FILE:+alternate.env}
        """,
    )

    try:
        module.validate_boundary(compose_source=compose, env_file=selected)
    except module.BoundaryCheckError as error:
        assert "unsupported compose env_file variable syntax" in str(error)
    else:
        raise AssertionError("alternative interpolation must fail closed")


def test_rejects_nested_compose_interpolation_in_env_file(
    tmp_path: pathlib.Path,
) -> None:
    module = _load_module()
    mode_key = module.MIGRATION_MODE_KEY
    selected = _write(tmp_path / "selected.env", f"{mode_key}=verify-applied\n")
    compose = _write(
        tmp_path / "compose.yml",
        """
        services:
          api:
            env_file:
              - ${WELTGEWEBE_ENV_FILE:-${OTHER_ENV_FILE}}
        """,
    )

    try:
        module.validate_boundary(compose_source=compose, env_file=selected)
    except module.BoundaryCheckError as error:
        assert "unsupported compose env_file variable syntax" in str(error)
    else:
        raise AssertionError("nested interpolation must fail closed")


def test_later_bare_env_file_key_unsets_previous_value(tmp_path: pathlib.Path) -> None:
    module = _load_module()
    mode_key = module.MIGRATION_MODE_KEY
    base_env = _write(tmp_path / "base.env", f"{mode_key}=verify-applied\n")
    unset_env = _write(tmp_path / "unset.env", f"{mode_key}\n")
    compose = _write(
        tmp_path / "compose.yml",
        f"""
        services:
          api:
            env_file:
              - {base_env}
              - {unset_env}
        """,
    )

    try:
        module.validate_boundary(compose_source=compose, env_file=base_env)
    except module.BoundaryCheckError as error:
        assert "unsets" in str(error)
    else:
        raise AssertionError("later bare key must fail closed")


def test_earlier_bare_env_file_key_can_be_overridden(tmp_path: pathlib.Path) -> None:
    module = _load_module()
    mode_key = module.MIGRATION_MODE_KEY
    base_env = _write(tmp_path / "base.env", f"{mode_key}\n")
    selected = _write(tmp_path / "selected.env", f"{mode_key}=verify-applied\n")
    compose = _write(
        tmp_path / "compose.yml",
        f"""
        services:
          api:
            env_file:
              - {base_env}
              - {selected}
        """,
    )

    result = module.validate_boundary(compose_source=compose, env_file=selected)

    assert result.observed_mode == "verify-applied"
    assert pathlib.Path(result.env_file) == selected.resolve()
