#!/usr/bin/env python3
"""Sample docker stats peaks for an already-running API replica container.

This reuses the docker-stats parsing helpers from
scripts/basemap/run-measured-container.py (loaded read-only via
importlib, the same pattern scripts/ci/tests/test_germany_measured_container.py
already uses) instead of duplicating unit-parsing logic. Unlike that script,
this sampler never starts or stops a container: the API replica is already
running under an external orchestrator (docker compose), and this tool only
observes it for a bounded window that is expected to overlap the
scripts/performance/api_runtime_k6.js load test.

The resulting receipt feeds scripts/performance/api_runtime_evidence.py
check --resource-receipt, covering the api_replica_resources peak_cpu_percent
and peak_memory_bytes evidence declared in policies/performance.v1.json.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import stat
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
MEASURED_CONTAINER_SCRIPT = REPO_ROOT / "scripts" / "basemap" / "run-measured-container.py"

SCHEMA_VERSION = 1
CONTRACT = "api-replica-resource-sample-v1"


class SamplerError(RuntimeError):
    pass


def _load_measured_container_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "weltgewebe_run_measured_container", MEASURED_CONTAINER_SCRIPT
    )
    if spec is None or spec.loader is None:
        raise SamplerError(f"cannot load {MEASURED_CONTAINER_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def accumulate_peaks(samples: Sequence[dict[str, Any]]) -> dict[str, Any]:
    if not samples:
        raise SamplerError("at least one docker stats sample is required")
    peak_cpu_percent = 0.0
    peak_memory_bytes = 0
    for sample in samples:
        cpu_percent = sample.get("cpu_percent")
        memory_bytes = sample.get("memory_bytes")
        if (
            not isinstance(cpu_percent, (int, float))
            or isinstance(cpu_percent, bool)
            or cpu_percent < 0
        ):
            raise SamplerError(f"sample has an invalid cpu_percent: {cpu_percent!r}")
        if not isinstance(memory_bytes, int) or isinstance(memory_bytes, bool) or memory_bytes < 0:
            raise SamplerError(f"sample has an invalid memory_bytes: {memory_bytes!r}")
        peak_cpu_percent = max(peak_cpu_percent, float(cpu_percent))
        peak_memory_bytes = max(peak_memory_bytes, memory_bytes)
    return {
        "cpu_percent": peak_cpu_percent,
        "memory_bytes": peak_memory_bytes,
        "sample_count": len(samples),
    }


def run_sampling_loop(
    *,
    container_name: str,
    duration_seconds: float,
    interval_seconds: float,
    read_stats: Callable[[str], dict[str, Any]],
    sleep: Callable[[float], None],
    monotonic: Callable[[], float],
) -> list[dict[str, Any]]:
    if duration_seconds <= 0:
        raise SamplerError("duration-seconds must be positive")
    if interval_seconds <= 0:
        raise SamplerError("sample-interval-seconds must be positive")
    samples: list[dict[str, Any]] = []
    started = monotonic()
    while True:
        samples.append(read_stats(container_name))
        elapsed = monotonic() - started
        remaining = duration_seconds - elapsed
        if remaining <= 0:
            break
        sleep(min(interval_seconds, remaining))
    return samples


def build_receipt(*, container_name: str, samples: Sequence[dict[str, Any]]) -> dict[str, Any]:
    peaks = accumulate_peaks(samples)
    return {
        "schema_version": SCHEMA_VERSION,
        "contract": CONTRACT,
        "container_name": container_name,
        "peaks": {
            "cpu_percent": peaks["cpu_percent"],
            "memory_bytes": peaks["memory_bytes"],
        },
        "sample_count": peaks["sample_count"],
    }


def write_atomic_json(path: Path, payload: dict[str, Any]) -> None:
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
    module = _load_measured_container_module()

    def read_stats(name: str) -> dict[str, Any]:
        try:
            return module.read_stats(name)
        except module.MeasurementError as exc:
            raise SamplerError(str(exc)) from exc

    samples = run_sampling_loop(
        container_name=args.container_name,
        duration_seconds=args.duration_seconds,
        interval_seconds=args.sample_interval_seconds,
        read_stats=read_stats,
        sleep=time.sleep,
        monotonic=time.monotonic,
    )
    receipt = build_receipt(container_name=args.container_name, samples=samples)
    write_atomic_json(args.receipt, receipt)
    print(json.dumps(receipt, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    sample = subparsers.add_parser(
        "sample", help="sample docker stats peaks for an already-running container"
    )
    sample.add_argument("--container-name", required=True)
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
        print(f"container-resource-sampler: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
