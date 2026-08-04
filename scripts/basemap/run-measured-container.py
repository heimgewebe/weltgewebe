#!/usr/bin/env python3
"""Run one Docker container and record bounded build-resource peaks."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

SIZE_RE = re.compile(r"^([0-9]+(?:\.[0-9]+)?)\s*([KMGTPE]?i?B)$", re.IGNORECASE)
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
UNITS = {
    "B": 1,
    "KB": 1000,
    "MB": 1000**2,
    "GB": 1000**3,
    "TB": 1000**4,
    "PB": 1000**5,
    "EB": 1000**6,
    "KIB": 1024,
    "MIB": 1024**2,
    "GIB": 1024**3,
    "TIB": 1024**4,
    "PIB": 1024**5,
    "EIB": 1024**6,
}


class MeasurementError(RuntimeError):
    pass


def fail(message: str) -> None:
    raise MeasurementError(message)


def parse_size(value: str) -> int:
    match = SIZE_RE.fullmatch(value.strip())
    if not match:
        fail(f"unrecognized Docker size value: {value!r}")
    number = float(match.group(1))
    if not math.isfinite(number) or number < 0:
        fail(f"invalid Docker size value: {value!r}")
    return int(round(number * UNITS[match.group(2).upper()]))


def parse_pair(value: str) -> tuple[int, int]:
    parts = [part.strip() for part in value.split("/")]
    if len(parts) != 2:
        fail(f"Docker size pair must contain one slash: {value!r}")
    return parse_size(parts[0]), parse_size(parts[1])


def workspace_bytes(root: Path) -> int:
    total = 0
    pending = [root]
    while pending:
        current = pending.pop()
        try:
            entries = list(os.scandir(current))
        except FileNotFoundError:
            continue
        for entry in entries:
            try:
                if entry.is_symlink():
                    continue
                if entry.is_dir(follow_symlinks=False):
                    pending.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    total += entry.stat(follow_symlinks=False).st_size
            except FileNotFoundError:
                continue
    return total


def run_command(
    argv: list[str], *, timeout: int = 30
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )


def inspect_state(name: str) -> dict[str, Any]:
    result = run_command(
        ["docker", "inspect", "--format", "{{json .State}}", name], timeout=15
    )
    if result.returncode != 0:
        fail(f"docker inspect failed: {result.stderr.strip()}")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        fail(f"docker inspect returned invalid JSON: {exc}")
    if not isinstance(value, dict):
        fail("docker inspect state must be an object")
    return value


def read_stats(name: str) -> dict[str, Any]:
    result = run_command(
        ["docker", "stats", "--no-stream", "--format", "{{json .}}", name],
        timeout=20,
    )
    if result.returncode != 0:
        fail(f"docker stats failed: {result.stderr.strip()}")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        fail(f"docker stats returned invalid JSON: {exc}")
    if not isinstance(value, dict):
        fail("docker stats payload must be an object")
    memory_used, _memory_limit = parse_pair(str(value.get("MemUsage", "")))
    block_read, block_write = parse_pair(str(value.get("BlockIO", "")))
    network_received, network_transmitted = parse_pair(str(value.get("NetIO", "")))
    cpu_raw = str(value.get("CPUPerc", "")).strip().removesuffix("%")
    try:
        cpu_percent = float(cpu_raw)
        pids = int(str(value.get("PIDs", "0")).strip())
    except ValueError as exc:
        fail(f"docker stats numeric field is invalid: {exc}")
    if not math.isfinite(cpu_percent) or cpu_percent < 0 or pids < 0:
        fail("docker stats contains a negative or non-finite value")
    return {
        "cpu_percent": cpu_percent,
        "memory_bytes": memory_used,
        "block_read_bytes": block_read,
        "block_write_bytes": block_write,
        "network_received_bytes": network_received,
        "network_transmitted_bytes": network_transmitted,
        "pids": pids,
    }


def write_atomic(path: Path, payload: dict[str, Any]) -> None:
    absolute = Path(os.path.abspath(path))
    absolute.parent.mkdir(parents=True, exist_ok=True)
    if absolute.is_symlink() or (absolute.exists() and not absolute.is_file()):
        fail(f"receipt must be absent or a regular file: {absolute}")
    fd, temporary = tempfile.mkstemp(prefix=f".{absolute.name}.", dir=absolute.parent)
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


def execute(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    workspace = Path(os.path.abspath(args.workspace))
    if not workspace.is_dir() or workspace.is_symlink():
        fail(f"workspace must be a non-symlink directory: {workspace}")
    if not NAME_RE.fullmatch(args.container_name):
        fail("container-name has an invalid Docker identifier")
    if args.sample_interval_seconds <= 0:
        fail("sample interval must be positive")
    command = list(args.command)
    if command[:2] != ["docker", "run"]:
        fail("measured command must start with: docker run")
    forbidden = {"--rm", "-d", "--detach", "--name"}
    if any(
        argument in forbidden or argument.startswith("--name=")
        for argument in command[2:]
    ):
        fail("measured docker run must not supply --rm, --detach or --name")

    started_at = dt.datetime.now(dt.timezone.utc)
    started_monotonic = time.monotonic()
    initial_workspace = workspace_bytes(workspace)
    initial_free = shutil.disk_usage(workspace).free
    peaks: dict[str, int | float] = {
        "cpu_percent": 0.0,
        "memory_bytes": 0,
        "workspace_bytes": initial_workspace,
        "workspace_growth_bytes": 0,
        "filesystem_consumed_bytes": 0,
        "block_read_bytes": 0,
        "block_write_bytes": 0,
        "network_received_bytes": 0,
        "network_transmitted_bytes": 0,
        "pids": 0,
    }
    minimum_free = initial_free
    sample_count = 0
    container_started = False
    state: dict[str, Any] = {}
    logs = ""

    launch = [
        "docker",
        "run",
        "--detach",
        "--name",
        args.container_name,
        *command[2:],
    ]
    command_sha256 = hashlib.sha256(
        json.dumps(launch, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    try:
        result = run_command(launch, timeout=120)
        if result.returncode != 0:
            fail(f"docker run failed: {result.stderr.strip()}")
        container_started = True
        while True:
            state = inspect_state(args.container_name)
            current_workspace = workspace_bytes(workspace)
            current_free = shutil.disk_usage(workspace).free
            minimum_free = min(minimum_free, current_free)
            peaks["workspace_bytes"] = max(
                int(peaks["workspace_bytes"]), current_workspace
            )
            peaks["workspace_growth_bytes"] = max(
                int(peaks["workspace_growth_bytes"]),
                max(0, current_workspace - initial_workspace),
            )
            peaks["filesystem_consumed_bytes"] = max(
                int(peaks["filesystem_consumed_bytes"]),
                max(0, initial_free - current_free),
            )
            if state.get("Running") is True:
                try:
                    sample = read_stats(args.container_name)
                except MeasurementError:
                    # The container may finish between inspect and stats. Re-read
                    # its state and accept that narrow race only after a terminal
                    # state is observed; a still-running stats failure remains fatal.
                    state = inspect_state(args.container_name)
                    if state.get("Running") is True:
                        raise
                    continue
                sample_count += 1
                for field, value in sample.items():
                    peaks[field] = max(peaks[field], value)
                time.sleep(args.sample_interval_seconds)
                continue
            break
    except KeyboardInterrupt:
        fail("measurement interrupted")
    finally:
        if container_started:
            log_result = run_command(
                ["docker", "logs", "--tail", "200", args.container_name], timeout=30
            )
            logs = (log_result.stdout + log_result.stderr)[-20000:]
            if not state:
                try:
                    state = inspect_state(args.container_name)
                except MeasurementError:
                    state = {}
            run_command(["docker", "rm", "-f", args.container_name], timeout=30)

    finished_at = dt.datetime.now(dt.timezone.utc)
    exit_code = state.get("ExitCode")
    if type(exit_code) is not int:
        exit_code = 1
    payload = {
        "schema_version": 1,
        "contract": "bounded-docker-build-measurement-v1",
        "status": "completed" if exit_code == 0 else "failed",
        "container_name": args.container_name,
        "command_sha256": command_sha256,
        "started_at": started_at.isoformat().replace("+00:00", "Z"),
        "finished_at": finished_at.isoformat().replace("+00:00", "Z"),
        "duration_seconds": round(time.monotonic() - started_monotonic, 3),
        "sample_interval_seconds": args.sample_interval_seconds,
        "sample_count": sample_count,
        "exit_code": exit_code,
        "oom_killed": state.get("OOMKilled") is True,
        "measurement_scope": {
            "cpu_and_memory": "planetiler-container",
            "workspace_storage": workspace.as_posix(),
            "filesystem_storage": "filesystem-containing-workspace",
        },
        "baseline": {
            "workspace_bytes": initial_workspace,
            "filesystem_free_bytes": initial_free,
        },
        "peaks": {
            **peaks,
            "minimum_filesystem_free_bytes": minimum_free,
        },
        "diagnostic_log_tail": logs if exit_code != 0 else "",
    }
    return payload, exit_code


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--container-name", required=True)
    result.add_argument("--workspace", required=True)
    result.add_argument("--receipt", required=True)
    result.add_argument("--sample-interval-seconds", type=float, default=1.0)
    result.add_argument("command", nargs=argparse.REMAINDER)
    return result


def main() -> int:
    try:
        args = parser().parse_args()
        if args.command and args.command[0] == "--":
            args.command = args.command[1:]
        payload, exit_code = execute(args)
        write_atomic(Path(args.receipt), payload)
        print(json.dumps(payload, sort_keys=True))
        return exit_code
    except MeasurementError as exc:
        print(f"MEASUREMENT_FAILED: {exc}", file=sys.stderr)
        return 1


def _interrupt(_signum: int, _frame: object) -> None:
    raise KeyboardInterrupt


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _interrupt)
    raise SystemExit(main())
