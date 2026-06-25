#!/usr/bin/env python3
"""Check or update task digests in repository-owned Handoff fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.agent.json_contract import DuplicateKeyError, load_json_strict
from scripts.docmeta.docmeta import REPO_ROOT

TASK_PATH = Path("tests/fixtures/agent/handoff-task.json")
DIGEST_FIXTURES = (
    Path("tests/fixtures/agent/handoff-valid.json"),
    Path("tests/fixtures/agent/handoff-valid-residual-gap.json"),
    Path("tests/fixtures/agent/handoff-invalid-path.json"),
    Path("tests/fixtures/agent/handoff-invalid-outcome.json"),
)


def _canonical_json(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def task_digest(repo_root: Path) -> str:
    return hashlib.sha256((repo_root / TASK_PATH).read_bytes()).hexdigest()


def check_or_update(repo_root: Path, *, write: bool) -> list[str]:
    expected = task_digest(repo_root)
    drift: list[str] = []
    for rel in DIGEST_FIXTURES:
        path = repo_root / rel
        data = load_json_strict(path)
        if not isinstance(data, dict):
            raise ValueError(f"{rel}: fixture must be a JSON object")
        if data.get("task_contract_sha256") == expected:
            continue
        drift.append(str(rel))
        if write:
            data["task_contract_sha256"] = expected
            path.write_text(_canonical_json(data), encoding="utf-8")
    return drift


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    try:
        drift = check_or_update(Path(REPO_ROOT), write=args.write)
    except (OSError, json.JSONDecodeError, DuplicateKeyError, ValueError) as exc:
        print(
            json.dumps(
                {"code": "FIXTURE_UPDATE_ERROR", "message": str(exc)},
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2

    payload = {
        "status": "updated" if args.write and drift else "drift" if drift else "clean",
        "task_file": str(TASK_PATH),
        "fixtures": [str(path) for path in DIGEST_FIXTURES],
        "drift": drift,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if args.check and drift else 0


if __name__ == "__main__":
    raise SystemExit(main())
