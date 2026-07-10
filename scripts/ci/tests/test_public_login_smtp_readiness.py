from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "ops" / "check_public_login_smtp_readiness.py"


def load_module():
    spec = importlib.util.spec_from_file_location("check_public_login_smtp_readiness", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load public-login smtp readiness module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_env(path: Path, content: str) -> Path:
    path.write_text(content.strip() + "\n", encoding="utf-8")
    return path


def test_production_public_login_passes_with_authenticated_smtp(tmp_path: Path) -> None:
    module = load_module()
    env = {
        "AUTH_PUBLIC_LOGIN": "1",
        "AUTH_LOG_MAGIC_TOKEN": "0",
        "APP_BASE_URL": "https://weltgewebe.net",
        "SMTP_HOST": "smtp.example.test",
        "SMTP_PORT": "587",
        "SMTP_AUTH": "on",
        "SMTP_USER": "user-secret",
        "SMTP_PASS": "pass-secret",
        "SMTP_FROM": "noreply@weltgewebe.net",
    }

    results = module.run_checks(
        env,
        production_public_login=True,
        expected_app_base_url="https://weltgewebe.net",
        allow_unauthenticated_smtp=False,
    )

    assert all(result.ok for result in results), [result.payload() for result in results]


def test_production_public_login_accepts_authenticated_starttls_on_port_2525() -> None:
    module = load_module()
    env = {
        "AUTH_PUBLIC_LOGIN": "1",
        "AUTH_LOG_MAGIC_TOKEN": "0",
        "APP_BASE_URL": "https://weltgewebe.net",
        "SMTP_HOST": "smtp.example.test",
        "SMTP_PORT": "2525",
        "SMTP_AUTH": "on",
        "SMTP_USER": "user-secret",
        "SMTP_PASS": "pass-secret",
        "SMTP_FROM": "noreply@weltgewebe.net",
    }

    results = module.run_checks(
        env,
        production_public_login=True,
        expected_app_base_url="https://weltgewebe.net",
        allow_unauthenticated_smtp=False,
    )

    assert all(result.ok for result in results), [result.payload() for result in results]


def test_production_public_login_rejects_plaintext_smtp_ports() -> None:
    module = load_module()

    for port in (25, 2526):
        env = {
            "AUTH_PUBLIC_LOGIN": "1",
            "AUTH_LOG_MAGIC_TOKEN": "0",
            "APP_BASE_URL": "https://weltgewebe.net",
            "SMTP_HOST": "smtp.example.test",
            "SMTP_PORT": str(port),
            "SMTP_AUTH": "on",
            "SMTP_USER": "user-secret",
            "SMTP_PASS": "pass-secret",
            "SMTP_FROM": "noreply@weltgewebe.net",
        }
        smtp_port = [
            item
            for item in module.run_checks(
                env,
                production_public_login=True,
                expected_app_base_url="https://weltgewebe.net",
                allow_unauthenticated_smtp=False,
            )
            if item.name == "smtp-port"
        ][0]

        assert not smtp_port.ok


def test_production_public_login_rejects_magic_token_logging(tmp_path: Path) -> None:
    module = load_module()
    env = {
        "AUTH_PUBLIC_LOGIN": "1",
        "AUTH_LOG_MAGIC_TOKEN": "1",
        "APP_BASE_URL": "https://weltgewebe.net",
        "SMTP_HOST": "smtp.example.test",
        "SMTP_PORT": "587",
        "SMTP_AUTH": "on",
        "SMTP_USER": "user-secret",
        "SMTP_PASS": "pass-secret",
        "SMTP_FROM": "noreply@weltgewebe.net",
    }

    result = [
        item
        for item in module.run_checks(
            env,
            production_public_login=True,
            expected_app_base_url="https://weltgewebe.net",
            allow_unauthenticated_smtp=False,
        )
        if item.name == "auth-log-magic-token"
    ][0]

    assert not result.ok
    assert "must not log tokens" in result.detail


def test_production_public_login_requires_smtp_credentials_by_default() -> None:
    module = load_module()
    env = {
        "AUTH_PUBLIC_LOGIN": "1",
        "AUTH_LOG_MAGIC_TOKEN": "0",
        "APP_BASE_URL": "https://weltgewebe.net",
        "SMTP_HOST": "smtp.example.test",
        "SMTP_PORT": "587",
        "SMTP_FROM": "noreply@weltgewebe.net",
        "SMTP_AUTH": "auto",
    }

    result = [
        item
        for item in module.run_checks(
            env,
            production_public_login=True,
            expected_app_base_url="https://weltgewebe.net",
            allow_unauthenticated_smtp=False,
        )
        if item.name == "smtp-auth"
    ][0]

    assert not result.ok
    assert "no SMTP_USER/SMTP_PASS" in result.detail


def test_production_public_login_rejects_partial_smtp_credentials() -> None:
    module = load_module()
    env = {
        "AUTH_PUBLIC_LOGIN": "1",
        "AUTH_LOG_MAGIC_TOKEN": "0",
        "APP_BASE_URL": "https://weltgewebe.net",
        "SMTP_HOST": "smtp.example.test",
        "SMTP_PORT": "587",
        "SMTP_FROM": "noreply@weltgewebe.net",
        "SMTP_AUTH": "auto",
        "SMTP_USER": "user-secret",
    }

    result = [
        item
        for item in module.run_checks(
            env,
            production_public_login=True,
            expected_app_base_url="https://weltgewebe.net",
            allow_unauthenticated_smtp=False,
        )
        if item.name == "smtp-auth"
    ][0]

    assert not result.ok
    assert "partial credential pair" in result.detail


def test_production_public_login_rejects_bad_app_base_url() -> None:
    module = load_module()
    env = {
        "AUTH_PUBLIC_LOGIN": "1",
        "AUTH_LOG_MAGIC_TOKEN": "0",
        "APP_BASE_URL": "http://localhost",
        "SMTP_HOST": "smtp.example.test",
        "SMTP_PORT": "587",
        "SMTP_AUTH": "on",
        "SMTP_USER": "user-secret",
        "SMTP_PASS": "pass-secret",
        "SMTP_FROM": "noreply@weltgewebe.net",
    }

    result = [
        item
        for item in module.run_checks(
            env,
            production_public_login=True,
            expected_app_base_url="https://weltgewebe.net",
            allow_unauthenticated_smtp=False,
        )
        if item.name == "app-base-url"
    ][0]

    assert not result.ok
    assert result.data["status"] == "mismatch"


def test_cli_output_does_not_print_secret_values(tmp_path: Path) -> None:
    env_file = write_env(
        tmp_path / "runtime.env",
        """
        AUTH_PUBLIC_LOGIN=1
        AUTH_LOG_MAGIC_TOKEN=0
        APP_BASE_URL=https://weltgewebe.net
        SMTP_HOST=smtp.example.test
        SMTP_PORT=587
        SMTP_AUTH=on
        SMTP_USER=very-sensitive-user
        SMTP_PASS=very-sensitive-pass
        SMTP_FROM=noreply@weltgewebe.net
        """,
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--env-file",
            str(env_file),
            "--production-public-login",
            "--json",
        ],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    payload = json.loads(proc.stdout)
    assert payload["status"] == "pass"
    assert "very-sensitive-user" not in proc.stdout
    assert "very-sensitive-pass" not in proc.stdout
    assert "present" in proc.stdout
