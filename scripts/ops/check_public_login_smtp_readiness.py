#!/usr/bin/env python3
"""Read-only public-login SMTP readiness preflight.

The checker reads dotenv-style runtime env files and prints only pass/fail
metadata. It never prints configured values, because some keys are secrets.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

EXPECTED_APP_BASE_URL = "https://weltgewebe.net"
SECRET_KEYS = {"SMTP_PASS", "SMTP_USER"}
REQUIRED_SMTP_KEYS = ("SMTP_HOST", "SMTP_PORT", "SMTP_FROM")


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str
    data: dict[str, object] = field(default_factory=dict)

    def payload(self) -> dict[str, object]:
        return {
            "name": self.name,
            "status": "pass" if self.ok else "fail",
            "detail": self.detail,
            **({"data": self.data} if self.data else {}),
        }


def pass_result(name: str, detail: str, **data: object) -> CheckResult:
    return CheckResult(name=name, ok=True, detail=detail, data=dict(data))


def fail_result(name: str, detail: str, **data: object) -> CheckResult:
    return CheckResult(name=name, ok=False, detail=detail, data=dict(data))


def parse_bool(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def parse_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            raise ValueError(f"{path}:{line_number}: expected KEY=VALUE")
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Z0-9_]+", key):
            raise ValueError(f"{path}:{line_number}: invalid env key")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'\"', "'"}:
            value = value[1:-1]
        env[key] = value
    return env


def merged_env(paths: Sequence[Path]) -> dict[str, str]:
    env: dict[str, str] = {}
    for path in paths:
        env.update(parse_env_file(path))
    return env


def present(env: Mapping[str, str], key: str) -> bool:
    return bool(env.get(key, "").strip())


def safe_presence_data(env: Mapping[str, str], keys: Sequence[str]) -> dict[str, str]:
    return {key: "present" if present(env, key) else "absent" for key in keys}


def check_public_login(env: Mapping[str, str], *, require_enabled: bool) -> CheckResult:
    enabled = parse_bool(env.get("AUTH_PUBLIC_LOGIN"))
    if require_enabled and not enabled:
        return fail_result("auth-public-login", "AUTH_PUBLIC_LOGIN is not enabled", status="disabled")
    if enabled:
        return pass_result("auth-public-login", "AUTH_PUBLIC_LOGIN is enabled", status="enabled")
    return pass_result("auth-public-login", "AUTH_PUBLIC_LOGIN is disabled", status="disabled")


def check_log_magic_token(env: Mapping[str, str], *, require_disabled: bool) -> CheckResult:
    enabled = parse_bool(env.get("AUTH_LOG_MAGIC_TOKEN"))
    if require_disabled and enabled:
        return fail_result(
            "auth-log-magic-token",
            "AUTH_LOG_MAGIC_TOKEN is enabled; production public login must not log tokens",
            status="enabled",
        )
    if enabled:
        return pass_result("auth-log-magic-token", "AUTH_LOG_MAGIC_TOKEN is enabled", status="enabled")
    return pass_result("auth-log-magic-token", "AUTH_LOG_MAGIC_TOKEN is disabled", status="disabled")


def check_app_base_url(env: Mapping[str, str], *, expected: str) -> CheckResult:
    value = env.get("APP_BASE_URL", "").strip()
    if value == expected:
        return pass_result("app-base-url", "APP_BASE_URL matches public production URL", status="configured")
    if not value:
        return fail_result("app-base-url", "APP_BASE_URL is missing", status="absent")
    return fail_result("app-base-url", "APP_BASE_URL does not match public production URL", status="mismatch")


def check_smtp_presence(env: Mapping[str, str]) -> CheckResult:
    missing = [key for key in REQUIRED_SMTP_KEYS if not present(env, key)]
    if missing:
        return fail_result(
            "smtp-required-keys",
            "required SMTP delivery keys are missing",
            missing=missing,
            presence=safe_presence_data(env, (*REQUIRED_SMTP_KEYS, "SMTP_USER", "SMTP_PASS")),
        )
    return pass_result(
        "smtp-required-keys",
        "required SMTP delivery keys are present",
        presence=safe_presence_data(env, (*REQUIRED_SMTP_KEYS, "SMTP_USER", "SMTP_PASS")),
    )


def check_smtp_port(env: Mapping[str, str]) -> CheckResult:
    raw = env.get("SMTP_PORT", "").strip()
    try:
        port = int(raw)
    except ValueError:
        return fail_result("smtp-port", "SMTP_PORT is not a number", status="invalid")
    if port in {465, 587}:
        return pass_result("smtp-port", "SMTP_PORT is a production TLS port", port=port)
    if port == 25:
        return fail_result("smtp-port", "SMTP_PORT 25 is not accepted for public-login rollout", port=port)
    return fail_result("smtp-port", "SMTP_PORT is not an accepted production TLS port", port=port)


def check_smtp_auth(env: Mapping[str, str], *, allow_unauthenticated: bool) -> CheckResult:
    policy = env.get("SMTP_AUTH", "auto").strip().lower() or "auto"
    if policy not in {"auto", "on", "off"}:
        return fail_result("smtp-auth", "SMTP_AUTH must be auto, on, or off", policy="invalid")

    has_user = present(env, "SMTP_USER")
    has_pass = present(env, "SMTP_PASS")

    if policy == "off":
        if allow_unauthenticated:
            return pass_result("smtp-auth", "SMTP_AUTH=off accepted by explicit override", policy="off")
        return fail_result("smtp-auth", "SMTP_AUTH=off is not accepted for production public-login rollout", policy="off")

    if policy == "on" and not (has_user and has_pass):
        return fail_result(
            "smtp-auth",
            "SMTP_AUTH=on requires SMTP_USER and SMTP_PASS",
            policy="on",
            presence=safe_presence_data(env, ("SMTP_USER", "SMTP_PASS")),
        )

    if policy == "auto":
        if has_user != has_pass:
            return fail_result(
                "smtp-auth",
                "SMTP_AUTH=auto has a partial credential pair",
                policy="auto",
                presence=safe_presence_data(env, ("SMTP_USER", "SMTP_PASS")),
            )
        if has_user and has_pass:
            return pass_result("smtp-auth", "SMTP_AUTH=auto will use the configured credential pair", policy="auto")
        if allow_unauthenticated:
            return pass_result("smtp-auth", "SMTP_AUTH=auto without credentials accepted by explicit override", policy="auto")
        return fail_result(
            "smtp-auth",
            "SMTP_AUTH=auto has no SMTP_USER/SMTP_PASS pair for production public-login rollout",
            policy="auto",
            presence=safe_presence_data(env, ("SMTP_USER", "SMTP_PASS")),
        )

    return pass_result("smtp-auth", "SMTP_AUTH=on has SMTP_USER and SMTP_PASS", policy="on")


def check_no_secret_values_leaked(results: Sequence[CheckResult]) -> CheckResult:
    serialized = json.dumps([result.payload() for result in results], sort_keys=True)
    leaked = [key for key in SECRET_KEYS if key in serialized and "present" not in serialized and "absent" not in serialized]
    if leaked:
        return fail_result("no-secret-values", "internal checker payload may leak secret-like values", keys=leaked)
    return pass_result("no-secret-values", "checker output contains presence metadata only")


def run_checks(
    env: Mapping[str, str],
    *,
    production_public_login: bool,
    expected_app_base_url: str,
    allow_unauthenticated_smtp: bool,
) -> list[CheckResult]:
    results = [
        check_public_login(env, require_enabled=production_public_login),
        check_log_magic_token(env, require_disabled=production_public_login),
        check_app_base_url(env, expected=expected_app_base_url),
        check_smtp_presence(env),
    ]
    if present(env, "SMTP_PORT"):
        results.append(check_smtp_port(env))
    else:
        results.append(fail_result("smtp-port", "SMTP_PORT is missing", status="absent"))
    results.append(check_smtp_auth(env, allow_unauthenticated=allow_unauthenticated_smtp))
    results.append(check_no_secret_values_leaked(results))
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check production public-login SMTP readiness.")
    parser.add_argument("--env-file", action="append", type=Path, required=True)
    parser.add_argument("--production-public-login", action="store_true")
    parser.add_argument("--expected-app-base-url", default=EXPECTED_APP_BASE_URL)
    parser.add_argument("--allow-unauthenticated-smtp", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    for path in args.env_file:
        if not path.is_file():
            print(f"ERROR: env file not found: {path}", file=sys.stderr)
            return 2
    try:
        env = merged_env(args.env_file)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    results = run_checks(
        env,
        production_public_login=args.production_public_login,
        expected_app_base_url=args.expected_app_base_url,
        allow_unauthenticated_smtp=args.allow_unauthenticated_smtp,
    )
    ok = all(result.ok for result in results)
    payload = {"status": "pass" if ok else "fail", "checks": [result.payload() for result in results]}
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for result in results:
            marker = "PASS" if result.ok else "FAIL"
            print(f"{marker}: {result.name}: {result.detail}")
        print(f"overall={payload['status']}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
