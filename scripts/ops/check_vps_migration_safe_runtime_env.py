#!/usr/bin/env python3
"""Validate the VPS migration-safe runtime-smoke environment boundary.

This helper is intentionally narrow. It does not call Docker, start containers,
render the full compose output, inspect arbitrary environment values, or print
secrets. It checks only the single startup-migration mode key that protects a
no-migration runtime smoke.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

MIGRATION_MODE_KEY = "WELTGEWEBE_API_STARTUP_MIGRATIONS"
DEFAULT_EXPECTED_MODE = "verify-applied"
DEFAULT_SERVICE = "api"


@dataclass(frozen=True)
class BoundaryCheckResult:
    service: str
    compose_source: str
    env_file: str
    expected_mode: str
    observed_mode: str
    has_env_file_hook: bool
    has_service_environment_override: bool

    def redacted_payload(self) -> dict[str, object]:
        return {
            "status": "pass",
            "service": self.service,
            "compose_source": self.compose_source,
            "env_file": self.env_file,
            "checked_key": MIGRATION_MODE_KEY,
            "expected_mode": self.expected_mode,
            "observed_mode": self.observed_mode,
            "has_env_file_hook": self.has_env_file_hook,
            "has_service_environment_override": self.has_service_environment_override,
            "secrets_printed": False,
            "runtime_started": False,
        }


class BoundaryCheckError(RuntimeError):
    """Raised when the migration-safe runtime-smoke boundary is not proven."""


def _leading_spaces(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _without_comment(line: str) -> str:
    stripped = line.lstrip()
    if stripped.startswith("#"):
        return ""
    return line.rstrip("\n")


def _find_mapping_block(lines: list[str], key: str, min_indent: int = 0) -> tuple[int, int, int] | None:
    pattern = re.compile(rf"^(\s*){re.escape(key)}\s*:\s*(?:#.*)?$")
    for index, line in enumerate(lines):
        if _leading_spaces(line) < min_indent:
            continue
        if not pattern.match(_without_comment(line)):
            continue

        indent = _leading_spaces(line)
        end = len(lines)
        for later_index in range(index + 1, len(lines)):
            later = _without_comment(lines[later_index])
            if not later.strip():
                continue
            if _leading_spaces(later) <= indent:
                end = later_index
                break
        return index, end, indent
    return None


def _find_service_block(compose_text: str, service: str) -> list[str]:
    lines = compose_text.splitlines()
    services_block = _find_mapping_block(lines, "services")
    if services_block is None:
        raise BoundaryCheckError("compose source does not contain a top-level services block")

    services_start, services_end, services_indent = services_block
    service_block = _find_mapping_block(
        lines[services_start + 1 : services_end],
        service,
        min_indent=services_indent + 1,
    )
    if service_block is None:
        raise BoundaryCheckError(f"compose source does not contain service {service!r}")

    service_start, service_end, _ = service_block
    offset = services_start + 1
    return lines[offset + service_start : offset + service_end]


def _service_has_env_file_hook(service_lines: Iterable[str]) -> bool:
    return any(_without_comment(line).strip().startswith("env_file:") for line in service_lines)


def _service_has_migration_override(service_lines: Iterable[str]) -> bool:
    key_pattern = re.compile(rf"(^|[\s{{,\-]){re.escape(MIGRATION_MODE_KEY)}\s*:")
    for line in service_lines:
        text = _without_comment(line)
        if key_pattern.search(text):
            return True
    return False


def _unquote_dotenv_value(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _read_dotenv_key(env_file: Path, key: str) -> str:
    try:
        lines = env_file.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise BoundaryCheckError(f"could not read selected env file {env_file}: {error}") from error

    values: list[str] = []
    pattern = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = pattern.match(stripped)
        if match is None:
            continue
        name, raw_value = match.groups()
        if name == key:
            values.append(_unquote_dotenv_value(raw_value))

    if not values:
        raise BoundaryCheckError(
            f"selected env file does not set {key}; refusing migration-safe runtime smoke"
        )
    if len(values) > 1:
        raise BoundaryCheckError(
            f"selected env file sets {key} more than once; refusing ambiguous migration mode"
        )
    return values[0].strip()


def validate_boundary(
    *,
    compose_source: Path,
    env_file: Path,
    service: str = DEFAULT_SERVICE,
    expected_mode: str = DEFAULT_EXPECTED_MODE,
) -> BoundaryCheckResult:
    try:
        compose_text = compose_source.read_text(encoding="utf-8")
    except OSError as error:
        raise BoundaryCheckError(f"could not read compose source {compose_source}: {error}") from error

    service_lines = _find_service_block(compose_text, service)
    has_env_file_hook = _service_has_env_file_hook(service_lines)
    if not has_env_file_hook:
        raise BoundaryCheckError(
            f"service {service!r} does not declare env_file; cannot prove selected env source"
        )

    has_override = _service_has_migration_override(service_lines)
    if has_override:
        raise BoundaryCheckError(
            f"service {service!r} sets {MIGRATION_MODE_KEY} in its compose service block; "
            "this can override env_file and may re-enable startup migrations"
        )

    observed_mode = _read_dotenv_key(env_file, MIGRATION_MODE_KEY)
    if observed_mode != expected_mode:
        raise BoundaryCheckError(
            f"selected env file sets {MIGRATION_MODE_KEY} to a non-approved value; "
            f"expected {expected_mode!r}"
        )

    return BoundaryCheckResult(
        service=service,
        compose_source=str(compose_source),
        env_file=str(env_file),
        expected_mode=expected_mode,
        observed_mode=observed_mode,
        has_env_file_hook=has_env_file_hook,
        has_service_environment_override=has_override,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the redacted env/compose boundary for a VPS migration-safe runtime smoke."
        )
    )
    parser.add_argument(
        "--compose-source",
        type=Path,
        default=Path("infra/compose/compose.vps.override.yml"),
        help="Repo compose override source to inspect; this should not contain secrets.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        required=True,
        help=(
            "Selected runtime env file. The script reads only "
            f"{MIGRATION_MODE_KEY} and never prints full env contents."
        ),
    )
    parser.add_argument("--service", default=DEFAULT_SERVICE)
    parser.add_argument("--expected-mode", default=DEFAULT_EXPECTED_MODE)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print a redacted JSON receipt instead of text.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        result = validate_boundary(
            compose_source=args.compose_source,
            env_file=args.env_file,
            service=args.service,
            expected_mode=args.expected_mode,
        )
    except BoundaryCheckError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1

    payload = result.redacted_payload()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("PASS: migration-safe runtime-smoke env boundary is proven")
        print(f"- service: {payload['service']}")
        print(f"- compose source: {payload['compose_source']}")
        print(f"- selected env file: {payload['env_file']}")
        print(f"- checked key: {payload['checked_key']}")
        print(f"- observed mode: {payload['observed_mode']}")
        print("- service-level migration override: absent")
        print("- secrets printed: no")
        print("- runtime started: no")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
