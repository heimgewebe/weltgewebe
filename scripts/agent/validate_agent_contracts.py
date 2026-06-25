#!/usr/bin/env python3
"""Validate repository-owned agent schemas and their contract fixtures."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.agent.json_contract import (
    DuplicateKeyError,
    UnsupportedSchemaError,
    ensure_supported_schema,
    load_json_strict,
    validate_instance,
)
from scripts.docmeta.docmeta import REPO_ROOT


def validate_contracts(repo_root: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    try:
        task_schema = load_json_strict(repo_root / "contracts/agent/task.schema.json")
        handoff_schema = load_json_strict(
            repo_root / "contracts/agent/handoff.schema.json"
        )
        task = load_json_strict(repo_root / "tests/fixtures/agent/handoff-task.json")
        handoff = load_json_strict(
            repo_root / "tests/fixtures/agent/handoff-valid.json"
        )
        if not isinstance(task_schema, dict) or not isinstance(handoff_schema, dict):
            raise UnsupportedSchemaError("schema root must be an object")
        ensure_supported_schema(task_schema)
        ensure_supported_schema(handoff_schema)

        cases = [
            ("tests/fixtures/agent/handoff-task.json", task, task_schema, True),
            ("tests/fixtures/agent/handoff-valid.json", handoff, handoff_schema, True),
        ]
        invalid_handoff = copy.deepcopy(handoff)
        invalid_handoff.pop("producer", None)
        cases.append(("synthetic:handoff-without-producer", invalid_handoff, handoff_schema, False))

        for label, fixture, schema, expected_valid in cases:
            violations = validate_instance(fixture, schema)
            if (not violations) != expected_valid:
                expectation = "valid" if expected_valid else "invalid"
                findings.append(
                    {
                        "code": "AGENT_CONTRACT_EXPECTATION_MISMATCH",
                        "path": label,
                        "message": (
                            f"fixture was expected to be {expectation}; "
                            f"violations={violations}"
                        ),
                    }
                )
    except (
        OSError,
        json.JSONDecodeError,
        DuplicateKeyError,
        UnsupportedSchemaError,
        ValueError,
    ) as exc:
        findings.append(
            {
                "code": "AGENT_CONTRACT_CHECK_ERROR",
                "path": "contracts/agent",
                "message": str(exc),
            }
        )

    return sorted(findings, key=lambda item: (item["code"], item["path"], item["message"]))


def main() -> int:
    findings = validate_contracts(Path(REPO_ROOT))
    print(
        json.dumps(
            {
                "status": "valid" if not findings else "invalid",
                "cases": 3,
                "findings_count": len(findings),
                "findings": findings,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
