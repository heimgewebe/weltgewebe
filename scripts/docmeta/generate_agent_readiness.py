#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.agent.json_contract import (
    DuplicateKeyError,
    load_json_strict,
    loads_json_strict,
)
from scripts.agent.validate_handoff import validate_handoff
from scripts.docmeta.docmeta import REPO_ROOT
from scripts.docmeta import validate_claim_registry


@dataclass(frozen=True)
class CapabilityResult:
    id: str
    title: str
    hard: bool
    status: str
    evidence: list[str]
    missing: list[str]
    rationale: str


VALID_STATUSES = {"pass", "partial", "open", "fail"}

HANDOFF_TASK_FILE = "tests/fixtures/agent/handoff-task.json"
HANDOFF_VALID_FILE = "tests/fixtures/agent/handoff-valid.json"
DRY_RUN_TASK_FILE = "tests/fixtures/agent/valid-doc-drift-task.json"
HANDOFF_REQUIRED_FILES = [
    "contracts/agent/task.schema.json",
    "contracts/agent/handoff.schema.json",
    "scripts/agent/json_contract.py",
    "scripts/agent/check_non_ideal_task.py",
    "scripts/agent/validate_handoff.py",
    "scripts/agent/tests/test_validate_handoff.py",
    "scripts/docmeta/docmeta.py",
    "scripts/docmeta/validate_claim_registry.py",
    "docs/claims/registry.yml",
    HANDOFF_TASK_FILE,
    HANDOFF_VALID_FILE,
]
DRY_RUN_REQUIRED_FILES = [
    "scripts/agent/run_task.py",
    "scripts/agent/tests/test_run_task.py",
    DRY_RUN_TASK_FILE,
]


def _handoff_failure(
    presence: CapabilityResult,
    diagnostic: str,
) -> CapabilityResult:
    diagnostic = diagnostic.strip()
    if len(diagnostic) > 240:
        diagnostic = diagnostic[:237] + "..."
    suffix = f": {diagnostic}" if diagnostic else "."
    return CapabilityResult(
        id=presence.id,
        title=presence.title,
        hard=presence.hard,
        status="fail",
        evidence=presence.evidence,
        missing=["functional handoff smoke"],
        rationale=f"{presence.rationale} Functional smoke failed{suffix}",
    )


def _capability_failure(
    presence: CapabilityResult,
    missing_item: str,
    diagnostic: str,
) -> CapabilityResult:
    diagnostic = diagnostic.strip()
    if len(diagnostic) > 240:
        diagnostic = diagnostic[:237] + "..."
    suffix = f": {diagnostic}" if diagnostic else "."
    return CapabilityResult(
        id=presence.id,
        title=presence.title,
        hard=presence.hard,
        status="fail",
        evidence=presence.evidence,
        missing=[missing_item],
        rationale=f"{presence.rationale} Functional smoke failed{suffix}",
    )


def _evaluate_handoff_validation(root: Path) -> CapabilityResult:
    presence = _evaluate_required_files(
        root=root,
        cap_id="handoff_validation",
        title="Handoff validation",
        hard=True,
        required_files=HANDOFF_REQUIRED_FILES,
        rationale=(
            "Handoff-Checks begrenzen unvollstaendige oder unsichere Uebergaben."
        ),
    )
    if presence.status != "pass":
        return presence

    env = os.environ.copy()
    env["PYTHONPATH"] = str(root)
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.agent.validate_handoff",
                "--task-file",
                HANDOFF_TASK_FILE,
                "--handoff-file",
                HANDOFF_VALID_FILE,
            ],
            cwd=root,
            env=env,
            check=False,
            text=True,
            capture_output=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return _handoff_failure(presence, str(exc))

    try:
        payload = loads_json_strict(completed.stdout)
    except (json.JSONDecodeError, DuplicateKeyError) as exc:
        return _handoff_failure(presence, f"invalid JSON output: {exc}")

    expected_output = (
        completed.returncode == 0
        and isinstance(payload, dict)
        and payload.get("status") == "valid"
        and payload.get("findings_count") == 0
        and payload.get("findings") == []
        and payload.get("task_file") == HANDOFF_TASK_FILE
        and payload.get("handoff_file") == HANDOFF_VALID_FILE
    )
    if not expected_output:
        diagnostic = completed.stderr or completed.stdout
        return _handoff_failure(presence, diagnostic or "unexpected CLI result")

    return CapabilityResult(
        id=presence.id,
        title=presence.title,
        hard=presence.hard,
        status="pass",
        evidence=presence.evidence,
        missing=[],
        rationale=(
            f"{presence.rationale} Required files and the canonical CLI smoke "
            "both pass."
        ),
    )


def _git_status_bytes(root: Path) -> bytes:
    completed = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=root,
        check=False,
        capture_output=True,
        timeout=15,
    )
    if completed.returncode != 0:
        raise RuntimeError("git status failed")
    return completed.stdout


def _validate_dry_run_payload(root: Path, payload: object) -> str | None:
    if not isinstance(payload, dict):
        return "runner output must be a JSON object"
    if payload.get("mode") != "dry_run":
        return "mode is not dry_run"
    if payload.get("status") != "planned":
        return "status is not planned"
    if payload.get("findings") != []:
        return "findings are not empty"
    if payload.get("repository_unchanged") is not True:
        return "repository_unchanged is not true"

    handoff = payload.get("handoff")
    if not isinstance(handoff, dict):
        return "handoff is missing"
    if handoff.get("outcome") != "incomplete":
        return "handoff outcome is not incomplete"
    validation_results = handoff.get("validation_results")
    if not isinstance(validation_results, list) or not validation_results:
        return "handoff validation_results are missing"
    if any(
        not isinstance(item, dict) or item.get("status") != "not_run"
        for item in validation_results
    ):
        return "handoff validation_results are not all not_run"

    try:
        task = load_json_strict(root / DRY_RUN_TASK_FILE)
        task_bytes = (root / DRY_RUN_TASK_FILE).read_bytes()
        registry, parser_findings, parser_exit = validate_claim_registry.load_registry(
            root / "docs/claims/registry.yml"
        )
    except (OSError, json.JSONDecodeError, DuplicateKeyError) as exc:
        return f"dry-run validation dependency failed: {exc}"
    if parser_exit != 0 or registry is None:
        return f"claim registry could not be loaded: {parser_findings}"
    findings = validate_handoff(
        task,
        handoff,
        task_bytes=task_bytes,
        repo_root=root,
        claim_registry=registry,
    )
    if findings:
        return f"handoff validator findings: {findings[:3]}"
    return None


def _evaluate_dry_run_runner(root: Path) -> CapabilityResult:
    presence = _evaluate_required_files(
        root=root,
        cap_id="dry_run_runner",
        title="Dry-run runner",
        hard=True,
        required_files=DRY_RUN_REQUIRED_FILES,
        rationale="Dry-Run Runner prueft Agentenpfade ohne schreibende Seiteneffekte.",
    )
    if presence.status != "pass":
        return presence

    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(root),
        "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
    }
    try:
        before = _git_status_bytes(root)
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.agent.run_task",
                "--dry-run",
                DRY_RUN_TASK_FILE,
            ],
            cwd=root,
            env=env,
            check=False,
            text=True,
            capture_output=True,
            timeout=20,
        )
        after = _git_status_bytes(root)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        return _capability_failure(presence, "functional dry-run smoke", str(exc))

    if before != after:
        return _capability_failure(
            presence,
            "functional dry-run smoke",
            "git status changed during smoke",
        )
    try:
        payload = loads_json_strict(completed.stdout)
    except (json.JSONDecodeError, DuplicateKeyError) as exc:
        return _capability_failure(
            presence,
            "functional dry-run smoke",
            f"invalid JSON output: {exc}",
        )
    if completed.returncode != 0 or completed.stderr:
        return _capability_failure(
            presence,
            "functional dry-run smoke",
            completed.stderr or f"unexpected exit code {completed.returncode}",
        )
    payload_error = _validate_dry_run_payload(root, payload)
    if payload_error is not None:
        return _capability_failure(
            presence,
            "functional dry-run smoke",
            payload_error,
        )

    return CapabilityResult(
        id=presence.id,
        title=presence.title,
        hard=presence.hard,
        status="pass",
        evidence=presence.evidence,
        missing=[],
        rationale=(
            f"{presence.rationale} Required files and the canonical dry-run "
            "smoke both pass."
        ),
    )


def _as_rel(root: Path, path: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def _files_for_patterns(root: Path, patterns: Iterable[str]) -> list[str]:
    matches: set[str] = set()
    for pattern in patterns:
        for path in root.glob(pattern):
            if path.is_file():
                matches.add(_as_rel(root, path))
    return sorted(matches)


def _files_for_regex(root: Path, search_roots: Iterable[str], regex: str) -> list[str]:
    matcher = re.compile(regex)
    matches: list[str] = []
    for rel_root in search_roots:
        base = root / rel_root
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            rel = _as_rel(root, path)
            if matcher.search(rel.lower()):
                matches.append(rel)
    return sorted(set(matches))


def _evaluate_required_files(
    root: Path,
    cap_id: str,
    title: str,
    hard: bool,
    required_files: list[str],
    rationale: str,
) -> CapabilityResult:
    evidence: list[str] = []
    missing: list[str] = []
    for rel in required_files:
        path = root / rel
        if path.exists() and not path.is_file():
            return CapabilityResult(
                id=cap_id,
                title=title,
                hard=hard,
                status="fail",
                evidence=evidence,
                missing=[rel],
                rationale=f"{rationale} Expected file path resolves to non-file artifact.",
            )
        if path.is_file():
            evidence.append(rel)
        else:
            missing.append(rel)

    if not missing:
        status = "pass"
    elif evidence:
        status = "partial"
    else:
        status = "open"

    return CapabilityResult(
        id=cap_id,
        title=title,
        hard=hard,
        status=status,
        evidence=evidence,
        missing=missing,
        rationale=rationale,
    )


def evaluate_capabilities(repo_root: Path) -> list[CapabilityResult]:
    results: list[CapabilityResult] = []

    results.append(
        _evaluate_required_files(
            root=repo_root,
            cap_id="agent_policy",
            title="Agent policy baseline",
            hard=False,
            required_files=["AGENTS.md", "agent-policy.yaml"],
            rationale="Agenten brauchen dokumentierte Grenzen und Schreibregeln.",
        )
    )

    results.append(
        _evaluate_required_files(
            root=repo_root,
            cap_id="safety_preflight",
            title="Safety preflight guard",
            hard=False,
            required_files=[
                "scripts/agent/check_agent_preflight.py",
                "scripts/agent/tests/test_check_agent_preflight.py",
                ".github/workflows/agent-safety-preflight.yml",
                "docs/security/agent-write-scope-baseline.md",
            ],
            rationale="Report-only Preflight schafft belastbare Baseline vor Blocking.",
        )
    )

    results.append(
        _evaluate_required_files(
            root=repo_root,
            cap_id="claim_evidence_spine",
            title="Claim evidence spine",
            hard=True,
            required_files=[
                "docs/claims/registry.yml",
                "scripts/docmeta/validate_claim_registry.py",
            ],
            rationale="Ohne Claim-Registry und Validator fehlt maschinenlesbare Evidenzbindung.",
        )
    )

    results.append(
        _evaluate_required_files(
            root=repo_root,
            cap_id="agent_contracts",
            title="Agent contracts",
            hard=True,
            required_files=["contracts/agent/task.schema.json"],
            rationale="Contracts definieren maschinenlesbare Agent-Task-Grenzen.",
        )
    )

    results.append(_evaluate_handoff_validation(repo_root))

    results.append(
        _evaluate_required_files(
            root=repo_root,
            cap_id="non_ideal_guard",
            title="Non-ideal guard",
            hard=True,
            required_files=[
                "scripts/agent/check_non_ideal_task.py",
                "scripts/agent/tests/test_check_non_ideal_task.py",
            ],
            rationale="Non-Ideal-Guard erkennt riskante Ausnahmefaelle vor Ausfuehrung.",
        )
    )

    results.append(_evaluate_dry_run_runner(repo_root))

    for result in results:
        if result.status not in VALID_STATUSES:
            raise ValueError(f"Invalid status for {result.id}: {result.status}")

    return results


def determine_overall_status(
    results: list[CapabilityResult],
) -> tuple[str, str, list[str]]:
    hard_gaps = [r.id for r in results if r.hard and r.status != "pass"]
    failing = [r.id for r in results if r.status == "fail"]
    passing = [r.id for r in results if r.status == "pass"]
    partial = [r.id for r in results if r.status == "partial"]

    if failing:
        reason = f"Inconsistent capability state detected: {', '.join(failing)}"
        return "fail", reason, hard_gaps

    if hard_gaps:
        reason = f"Hard capabilities are still missing: {', '.join(hard_gaps)}"
        return "partial", reason, hard_gaps

    if len(passing) == len(results):
        return "pass", "All hard and non-hard capabilities are present.", []

    if not passing and not partial:
        return (
            "open",
            "No capability evidence detected yet.",
            [r.id for r in results if r.hard],
        )

    return "partial", "Capabilities are partially implemented.", hard_gaps


def render_report(
    results: list[CapabilityResult],
    overall: str,
    reason: str,
    hard_gaps: list[str],
) -> str:
    lines: list[str] = []
    lines.append("---")
    lines.append("id: docs.generated.agent-readiness")
    lines.append("title: Agent Readiness")
    lines.append("doc_type: generated")
    lines.append("status: active")
    lines.append("summary: Deterministische Agent-Readiness-Matrix.")
    lines.append("---")
    lines.append("")
    lines.append("## Weltgewebe Agent Readiness")
    lines.append("")
    lines.append("Generated automatically. Do not edit.")
    lines.append("")
    lines.append("## Overall Status")
    lines.append("")
    lines.append(f"- **Overall:** {overall}")
    lines.append(f"- **Reason:** {reason}")
    lines.append("")
    lines.append("## Capability Matrix")
    lines.append("")
    lines.append("| Capability | Status | Hard | Evidence | Missing | Rationale |")
    lines.append("|---|---|---:|---|---|---|")

    handoff_evidence: list[str] = []
    for result in results:
        if result.id == "handoff_validation":
            handoff_evidence = result.evidence
            evidence = "See Handoff Evidence"
        else:
            evidence = (
                ", ".join(f"`{item}`" for item in result.evidence)
                if result.evidence
                else "-"
            )
        missing = (
            ", ".join(f"`{item}`" for item in result.missing) if result.missing else "-"
        )
        hard = "yes" if result.hard else "no"
        lines.append(
            f"| {result.id} | {result.status} | {hard} | {evidence} | "
            f"{missing} | {result.rationale} |"
        )

    lines.append("")
    lines.append("## Handoff Evidence")
    lines.append("")
    if handoff_evidence:
        lines.extend(f"- `{item}`" for item in handoff_evidence)
    else:
        lines.append("- No handoff evidence detected.")

    lines.append("")
    lines.append("## Residual Gaps")
    lines.append("")
    if hard_gaps:
        for capability in hard_gaps:
            lines.append(f"- Hard capability missing: {capability}")
    else:
        lines.append("- No residual hard gaps detected.")

    lines.append("")
    lines.append("## Interpretation Rule")
    lines.append("")
    lines.append("Dieser Report ist diagnostisch. Er aktiviert keinen Blocking-Mode.")
    lines.append(
        "`pass` bezeichnet nur die read-only Contract- und Planungsfaehigkeit "
        "der Agent-Safety-Schicht. Es bestaetigt keine Task-Ausfuehrung, "
        "keine Run-Attestierung, keine Patch-Anwendung, keinen Write Mode und "
        "keine autonome Merge-Faehigkeit."
    )
    lines.append("")
    return "\n".join(lines)


def generate(repo_root: str | Path | None = None) -> Path:
    root = Path(repo_root) if repo_root is not None else Path(REPO_ROOT)
    out_file = root / "docs" / "_generated" / "agent-readiness.md"
    out_file.parent.mkdir(parents=True, exist_ok=True)

    results = evaluate_capabilities(root)
    overall, reason, hard_missing = determine_overall_status(results)
    content = render_report(results, overall, reason, hard_missing)
    out_file.write_text(content, encoding="utf-8")
    return out_file


def main() -> int:
    try:
        out_file = generate()
        print(f"Generated {out_file}")
        return 0
    except Exception as exc:
        print(f"Error generating agent readiness: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
