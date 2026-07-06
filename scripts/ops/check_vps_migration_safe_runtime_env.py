#!/usr/bin/env python3
"""Validate the VPS migration-safe runtime-smoke environment boundary.

This helper is intentionally narrow. It does not call Docker, start containers,
render the full compose output, inspect arbitrary environment values, or print
confidential values. It checks only the single startup-migration mode key plus
the non-confidential compose source shape needed to bind the selected env file.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

MIGRATION_MODE_KEY = "WELTGEWEBE_API_STARTUP_MIGRATIONS"
COMPOSE_ENV_FILE_KEY = "WELTGEWEBE_ENV_FILE"
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
            "helper_printed_confidential_values": False,
            "helper_started_runtime": False,
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


def _find_mapping_block(
    lines: list[str],
    key: str,
    min_indent: int = 0,
) -> tuple[int, int, int] | None:
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


def _strip_optional_quotes(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1]
    return text


def _strip_yaml_inline_comment(value: str) -> str:
    """Strip a YAML-style inline comment outside quotes.

    YAML treats ``#`` as a comment delimiter only when it starts the scalar or is
    preceded by whitespace. This helper intentionally implements only the narrow
    scalar shapes accepted by this guard; unterminated quotes fail closed.
    """

    in_quote: str | None = None
    escaped = False

    for index, char in enumerate(value):
        if in_quote:
            if in_quote == '"' and escaped:
                escaped = False
                continue
            if in_quote == '"' and char == "\\":
                escaped = True
                continue
            if char == in_quote:
                in_quote = None
            continue

        if char in {"'", '"'}:
            in_quote = char
            continue

        if char == "#" and (index == 0 or value[index - 1].isspace()):
            return value[:index].rstrip()

    if in_quote:
        raise BoundaryCheckError(
            "unterminated quoted compose scalar; cannot prove migration-mode absence"
        )

    return value.rstrip()


def _flow_items(value: str) -> list[str]:
    text = value.strip()
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        if not inner:
            return []
        return [_strip_optional_quotes(_strip_yaml_inline_comment(part)) for part in inner.split(",")]
    raise BoundaryCheckError(
        "unsupported flow-style compose value; use block list/map syntax for this guard"
    )


def _find_child_entry(service_lines: list[str], key: str) -> tuple[int, int, int, str] | None:
    pattern = re.compile(rf"^(\s*){re.escape(key)}\s*:\s*(.*?)\s*(?:#.*)?$")
    matches: list[tuple[int, int, int, str]] = []
    for index, line in enumerate(service_lines):
        match = pattern.match(_without_comment(line))
        if match is None:
            continue

        indent = len(match.group(1))
        end = len(service_lines)
        for later_index in range(index + 1, len(service_lines)):
            later = _without_comment(service_lines[later_index])
            if not later.strip():
                continue
            if _leading_spaces(later) <= indent:
                end = later_index
                break
        matches.append((index, end, indent, match.group(2).strip()))

    if len(matches) > 1:
        raise BoundaryCheckError(f"service declares {key!r} more than once; refusing ambiguity")
    return matches[0] if matches else None


def _service_has_env_file_hook(service_lines: list[str]) -> bool:
    return _find_child_entry(service_lines, "env_file") is not None


def _normalise_env_key_token(token: str) -> str:
    text = _strip_yaml_inline_comment(token).strip()
    if not text:
        return text
    if text[0] in {"'", '"'} and len(text) >= 2:
        text = _strip_optional_quotes(text)
    return text.strip()


def _environment_item_sets_key(item: str) -> bool:
    text = _normalise_env_key_token(item)
    if text == MIGRATION_MODE_KEY:
        return True
    if text.startswith(f"{MIGRATION_MODE_KEY}="):
        return True
    if text.startswith(f"{MIGRATION_MODE_KEY}:"):
        return True
    return False


def _service_has_migration_override(service_lines: list[str]) -> bool:
    entry = _find_child_entry(service_lines, "environment")
    if entry is None:
        return False

    start, end, _indent, inline_value = entry
    if inline_value:
        text = inline_value.strip()
        if MIGRATION_MODE_KEY in text:
            return True
        if text.startswith("[") or text.startswith("{"):
            raise BoundaryCheckError(
                "unsupported flow-style service environment; cannot prove migration-mode absence"
            )
        raise BoundaryCheckError(
            "unsupported inline service environment; use block map/list syntax for this guard"
        )

    for raw_line in service_lines[start + 1 : end]:
        line = _without_comment(raw_line)
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith("-"):
            item = stripped[1:].strip()
            if _environment_item_sets_key(item):
                return True
            continue

        key_match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:", stripped)
        if key_match:
            if key_match.group(1) == MIGRATION_MODE_KEY:
                return True
            continue

        if "<<" in stripped or "&" in stripped or "*" in stripped:
            raise BoundaryCheckError(
                "unsupported YAML merge/anchor in service environment; cannot prove migration-mode absence"
            )

        raise BoundaryCheckError(
            "unsupported service environment entry; cannot prove migration-mode absence"
        )

    return False


def _extract_env_file_entries(service_lines: list[str]) -> list[str]:
    entry = _find_child_entry(service_lines, "env_file")
    if entry is None:
        return []

    start, end, _indent, inline_value = entry
    if inline_value:
        if inline_value.startswith("["):
            entries = _flow_items(inline_value)
        else:
            entries = [_strip_optional_quotes(_strip_yaml_inline_comment(inline_value))]
        return [entry for entry in entries if entry]

    entries: list[str] = []
    for raw_line in service_lines[start + 1 : end]:
        line = _without_comment(raw_line)
        stripped = line.strip()
        if not stripped:
            continue
        if not stripped.startswith("-"):
            raise BoundaryCheckError(
                "unsupported env_file entry; use string entries for this guard"
            )

        item = _strip_yaml_inline_comment(stripped[1:].strip()).strip()
        if not item:
            raise BoundaryCheckError("empty env_file entry; refusing ambiguity")
        if item.startswith("{") or re.match(r"^[A-Za-z_][A-Za-z0-9_-]*\s*:", item):
            raise BoundaryCheckError(
                "unsupported structured env_file entry; use string path entries for this guard"
            )
        entries.append(_strip_optional_quotes(item))

    return entries


_COMPOSE_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?:(:-|-)([^}]*))?\}")


def _resolve_compose_vars(value: str, compose_env: Mapping[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        op = match.group(2)
        default = match.group(3)
        current = compose_env.get(name)

        if op == ":-":
            return current if current else default
        if op == "-":
            return current if current is not None else default
        if op is None:
            if current is None:
                raise BoundaryCheckError(
                    f"compose env_file entry references unset variable {name!r}"
                )
            return current

        raise BoundaryCheckError(
            f"unsupported compose variable operator in env_file entry for {name!r}"
        )

    if "$" in value and "${" not in value:
        raise BoundaryCheckError(
            "unsupported compose env_file variable syntax; use ${VAR:-default}"
        )
    return _COMPOSE_VAR_RE.sub(replace, value)


def _normalise_path(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _resolve_env_file_entries(
    *,
    compose_source: Path,
    entries: Iterable[str],
    compose_env: Mapping[str, str],
) -> list[Path]:
    resolved: list[Path] = []
    for entry in entries:
        resolved_entry = _resolve_compose_vars(entry, compose_env).strip()
        if not resolved_entry:
            raise BoundaryCheckError("env_file entry resolved to an empty path")

        path = Path(resolved_entry)
        if not path.is_absolute():
            path = compose_source.parent / path
        resolved.append(_normalise_path(path))

    if not resolved:
        raise BoundaryCheckError("service env_file resolves to an empty list")
    return resolved


def _parse_dotenv_value(raw: str, *, key: str) -> str:
    value = raw.strip()
    if not value:
        return ""

    if value[0] in {"'", '"'}:
        quote = value[0]
        escaped = False
        chars: list[str] = []
        for index, char in enumerate(value[1:], start=1):
            if quote == '"' and escaped:
                chars.append(char)
                escaped = False
                continue
            if quote == '"' and char == "\\":
                escaped = True
                continue
            if char == quote:
                remainder = value[index + 1 :].strip()
                if remainder and not remainder.startswith("#"):
                    raise BoundaryCheckError(
                        f"unsupported trailing content after quoted value for {key}"
                    )
                return "".join(chars)
            chars.append(char)

        raise BoundaryCheckError(f"unterminated quoted value for {key}")

    if " #" in value:
        value = value.split(" #", 1)[0].rstrip()
    return value


def _read_dotenv_key(env_file: Path, key: str) -> str | None:
    try:
        lines = env_file.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise BoundaryCheckError(f"could not read selected env file {env_file}: {error}") from error

    values: list[str] = []
    pattern = re.compile(
        r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*(=|:)\s*(.*)$"
    )
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = pattern.match(stripped)
        if match is None:
            continue
        name, _separator, raw_value = match.groups()
        if name == key:
            values.append(_parse_dotenv_value(raw_value, key=key))

    if len(values) > 1:
        raise BoundaryCheckError(
            f"selected env file {env_file} sets {key} more than once; refusing ambiguous migration mode"
        )
    if not values:
        return None
    return values[0].strip()


def _read_effective_dotenv_key(env_files: Iterable[Path], key: str) -> tuple[Path, str]:
    selected_path: Path | None = None
    selected_value: str | None = None

    for env_file in env_files:
        value = _read_dotenv_key(env_file, key)
        if value is not None:
            selected_path = env_file
            selected_value = value

    if selected_path is None or selected_value is None:
        raise BoundaryCheckError(
            f"effective env_file set does not set {key}; refusing migration-safe runtime smoke"
        )

    return selected_path, selected_value


def validate_boundary(
    *,
    compose_source: Path,
    env_file: Path,
    service: str = DEFAULT_SERVICE,
    expected_mode: str = DEFAULT_EXPECTED_MODE,
    compose_env: Mapping[str, str] | None = None,
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

    compose_env_map = dict(compose_env or {})
    entries = _extract_env_file_entries(service_lines)
    effective_env_files = _resolve_env_file_entries(
        compose_source=compose_source,
        entries=entries,
        compose_env=compose_env_map,
    )

    selected_env_file = _normalise_path(env_file)
    effective_env_file, observed_mode = _read_effective_dotenv_key(
        effective_env_files,
        MIGRATION_MODE_KEY,
    )
    if selected_env_file != effective_env_file:
        raise BoundaryCheckError(
            "selected --env-file is not the effective env_file source for "
            f"{MIGRATION_MODE_KEY}; refusing ambiguous migration mode"
        )

    if observed_mode != expected_mode:
        raise BoundaryCheckError(
            f"effective env file sets {MIGRATION_MODE_KEY} to a non-approved value; "
            f"expected {expected_mode!r}"
        )

    return BoundaryCheckResult(
        service=service,
        compose_source=str(compose_source),
        env_file=str(effective_env_file),
        expected_mode=expected_mode,
        observed_mode=observed_mode,
        has_env_file_hook=has_env_file_hook,
        has_service_environment_override=has_override,
    )


def _parse_compose_env(values: list[str]) -> dict[str, str]:
    compose_env: dict[str, str] = {}
    if COMPOSE_ENV_FILE_KEY in os.environ:
        compose_env[COMPOSE_ENV_FILE_KEY] = os.environ[COMPOSE_ENV_FILE_KEY]

    for value in values:
        if "=" not in value:
            raise BoundaryCheckError(
                f"--compose-env value must use NAME=VALUE syntax, got {value!r}"
            )
        name, raw = value.split("=", 1)
        name = name.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise BoundaryCheckError(f"invalid compose env variable name {name!r}")
        compose_env[name] = raw

    return compose_env


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the redacted env/compose source boundary for a VPS "
            "migration-safe runtime smoke."
        )
    )
    parser.add_argument(
        "--compose-source",
        type=Path,
        default=Path("infra/compose/compose.vps.override.yml"),
        help="Repo compose override source to inspect; this should not contain confidential values.",
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
    parser.add_argument(
        "--compose-env",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help=(
            "Non-confidential compose interpolation input for env_file path "
            "resolution. May be repeated. The helper also reads WELTGEWEBE_ENV_FILE "
            "from the process environment when present."
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
            compose_env=_parse_compose_env(args.compose_env),
        )
    except BoundaryCheckError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1

    payload = result.redacted_payload()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("PASS: migration-safe runtime-smoke source boundary is proven")
        print(f"- service: {payload['service']}")
        print(f"- compose source: {payload['compose_source']}")
        print(f"- effective env file: {payload['env_file']}")
        print(f"- checked key: {payload['checked_key']}")
        print(f"- observed mode: {payload['observed_mode']}")
        print("- service-level migration override: absent")
        print("- helper printed confidential values: no")
        print("- helper started runtime: no")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
