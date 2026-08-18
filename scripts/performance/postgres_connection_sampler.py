#!/usr/bin/env python3
"""Sample PostgreSQL connection counts for one bounded api_runtime load window.

The sampler observes ``pg_stat_activity`` through the already-running,
digest-bound PostgreSQL container. It never starts, stops, or mutates the
database. A caller-provided run id binds these samples to the k6, live-runtime,
and API-container resource receipts consumed by api_runtime_evidence.py.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable, Sequence

SCHEMA_VERSION = 1
CONTRACT = "postgres-connection-sample-v1"
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
CONTAINER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class SamplerError(RuntimeError):
    pass


def validate_run_id(value: str) -> str:
    if not isinstance(value, str) or not RUN_ID_RE.fullmatch(value):
        raise SamplerError("run-id must match [A-Za-z0-9][A-Za-z0-9._-]{0,127}")
    return value


def validate_container_name(value: str) -> str:
    if not isinstance(value, str) or not CONTAINER_RE.fullmatch(value):
        raise SamplerError("database-container has an invalid name")
    return value


def read_connection_count(
    container_name: str,
    *,
    database_user: str,
    database_name: str,
) -> int:
    validate_container_name(container_name)
    if not database_user or not database_name:
        raise SamplerError("database-user and database-name must be non-empty")
    argv = [
        "docker",
        "exec",
        container_name,
        "psql",
        "-U",
        database_user,
        "-d",
        database_name,
        "-At",
        "-c",
        "SELECT count(*) FROM pg_stat_activity;",
    ]
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SamplerError(f"cannot sample pg_stat_activity: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise SamplerError(f"pg_stat_activity query failed: {detail}")
    raw = result.stdout.strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise SamplerError(f"pg_stat_activity count is not an integer: {raw!r}") from exc
    if value < 0:
        raise SamplerError("pg_stat_activity count cannot be negative")
    return value


def run_sampling_loop(
    *,
    duration_seconds: float,
    interval_seconds: float,
    read_count: Callable[[], int],
    sleep: Callable[[float], None],
    monotonic: Callable[[], float],
) -> list[int]:
    if duration_seconds <= 0:
        raise SamplerError("duration-seconds must be positive")
    if interval_seconds <= 0:
        raise SamplerError("sample-interval-seconds must be positive")
    samples: list[int] = []
    started = monotonic()
    while True:
        value = read_count()
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise SamplerError(f"connection sample is invalid: {value!r}")
        samples.append(value)
        elapsed = monotonic() - started
        remaining = duration_seconds - elapsed
        if remaining <= 0:
            break
        sleep(min(interval_seconds, remaining))
    return samples


def build_receipt(*, run_id: str, database_container: str, samples: Sequence[int]) -> dict:
    validate_run_id(run_id)
    validate_container_name(database_container)
    if not samples:
        raise SamplerError("at least one PostgreSQL connection sample is required")
    normalized: list[int] = []
    for value in samples:
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise SamplerError(f"connection sample is invalid: {value!r}")
        normalized.append(value)
    return {
        "schema_version": SCHEMA_VERSION,
        "contract": CONTRACT,
        "run_id": run_id,
        "database_container": database_container,
        "max_connections": max(normalized),
        "sample_count": len(normalized),
        "samples": normalized,
    }


def write_atomic_json(path: Path, payload: dict) -> None:
    absolute = Path(os.path.abspath(path))
    absolute.parent.mkdir(parents=True, exist_ok=True)
    if absolute.is_symlink() or (absolute.exists() and not absolute.is_file()):
        raise SamplerError(f"receipt must be absent or a regular file: {absolute}")
    fd, temporary_name = tempfile.mkstemp(prefix=f".{absolute.name}.", dir=absolute.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, stat.S_IRUSR | stat.S_IWUSR)
        os.replace(temporary, absolute)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _cli_sample(args: argparse.Namespace) -> int:
    run_id = validate_run_id(args.run_id)
    container = validate_container_name(args.database_container)

    def sample() -> int:
        return read_connection_count(
            container,
            database_user=args.database_user,
            database_name=args.database_name,
        )

    samples = run_sampling_loop(
        duration_seconds=args.duration_seconds,
        interval_seconds=args.sample_interval_seconds,
        read_count=sample,
        sleep=time.sleep,
        monotonic=time.monotonic,
    )
    receipt = build_receipt(run_id=run_id, database_container=container, samples=samples)
    write_atomic_json(args.receipt, receipt)
    print(json.dumps(receipt, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    sample = subparsers.add_parser("sample", help="sample pg_stat_activity over a bounded window")
    sample.add_argument("--run-id", required=True)
    sample.add_argument("--database-container", required=True)
    sample.add_argument("--database-user", default="welt")
    sample.add_argument("--database-name", default="weltgewebe")
    sample.add_argument("--duration-seconds", type=float, required=True)
    sample.add_argument("--sample-interval-seconds", type=float, default=1.0)
    sample.add_argument("--receipt", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "sample":
            return _cli_sample(args)
        parser.error(f"unsupported command {args.command}")
        return 1
    except SamplerError as exc:
        print(f"postgres-connection-sampler: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
