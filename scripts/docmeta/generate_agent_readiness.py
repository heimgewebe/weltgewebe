#!/usr/bin/env python3
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.docmeta.docmeta import REPO_ROOT


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
    "tests/fixtures/agent/handoff-task.json",
    "tests/fixtures/agent/handoff-valid.json",
]


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
                cap_id,
                title,
                hard,
                "fail",
                evidence,
                [rel],
                f"{rationale} Expected file path resolves to non-file artifact.",
            )
        (evidence if path.is_file() else missing).append(rel)
    status = "pass" if not missing else "partial" if evidence else "open"
    return CapabilityResult(
        cap_id,
        title,
        hard,
        status,
        evidence,
        missing,
        rationale,
    )


def _evaluate_handoff_validation(root: Path) -> CapabilityResult:
    presence = _evaluate_required_files(
        root,
        "handoff_validation",
        "Handoff validation",
        True,
        HANDOFF_REQUIRED_FILES,
        "Handoff-Checks begrenzen unvollstaendige oder unsichere Uebergaben.",
    )
    if presence.status != "pass":
        return presence

    env = os.environ.copy()
    env["PYTHONPATH"] = str(root)
    command = [
        sys.executable,
        "-m",
        "scripts.agent.validate_handoff",
        "--task-file",
        "tests/fixtures/agent/handoff-task.json",
        "--handoff-file",
        "tests/fixtures/agent/handoff-valid.json",
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            env=env,
            check=False,
            text=True,
            capture_output=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CapabilityResult(
            presence.id,
            presence.title,
            presence.hard,
            "fail",
            presence.evidence,
            ["functional handoff smoke"],
            f"{presence.rationale} Functional smoke failed: {exc}",
        )

    if completed.returncode != 0:
        diagnostic = (completed.stderr or completed.stdout).strip()
        if len(diagnostic) > 240:
            diagnostic = diagnostic[:237] + "..."
        suffix = f": {diagnostic}" if diagnostic else "."
        return CapabilityResult(
            presence.id,
            presence.title,
            presence.hard,
            "fail",
            presence.evidence,
            ["functional handoff smoke"],
            f"{presence.rationale} Functional smoke failed{suffix}",
        )

    return CapabilityResult(
        presence.id,
        presence.title,
        presence.hard,
        "pass",
        presence.evidence,
        [],
        (
            f"{presence.rationale} Required files and the repository CLI smoke "
            "both pass against the real claim registry."
        ),
    )


def _as_rel(root: Path, path: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def _files_for_regex(
    root: Path,
    search_roots: Iterable[str],
    regex: str,
) -> list[str]:
    matcher = re.compile(regex)
    matches: list[str] = []
    for rel_root in search_roots:
        base = root / rel_root
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if path.is_file():
                rel = _as_rel(root, path)
                if matcher.search(rel.lower()):
                    matches.append(rel)
    return sorted(set(matches))


def evaluate_capabilities(repo_root: Path) -> list[CapabilityResult]:
    specs = [
        (
            "agent_policy",
            "Agent policy baseline",
            False,
            ["AGENTS.md", "agent-policy.yaml"],
            "Agenten brauchen dokumentierte Grenzen und Schreibregeln.",
        ),
        (
            "safety_preflight",
            "Safety preflight guard",
            False,
            [
                "scripts/agent/check_agent_preflight.py",
                "scripts/agent/tests/test_check_agent_preflight.py",
                ".github/workflows/agent-safety-preflight.yml",
                "docs/security/agent-write-scope-baseline.md",
            ],
            "Report-only Preflight schafft belastbare Baseline vor Blocking.",
        ),
        (
            "claim_evidence_spine",
            "Claim evidence spine",
            True,
            [
                "docs/claims/registry.yml",
                "scripts/docmeta/validate_claim_registry.py",
            ],
            "Ohne Claim-Registry und Validator fehlt maschinenlesbare Evidenzbindung.",
        ),
        (
            "agent_contracts",
            "Agent contracts",
            True,
            ["contracts/agent/task.schema.json"],
            "Contracts definieren maschinenlesbare Agent-Task-Grenzen.",
        ),
    ]
    results = [_evaluate_required_files(repo_root, *spec) for spec in specs]
    results.append(_evaluate_handoff_validation(repo_root))
    results.append(
        _evaluate_required_files(
            repo_root,
            "non_ideal_guard",
            "Non-ideal guard",
            True,
            [
                "scripts/agent/check_non_ideal_task.py",
                "scripts/agent/tests/test_check_non_ideal_task.py",
            ],
            "Non-Ideal-Guard erkennt riskante Ausnahmefaelle vor Ausfuehrung.",
        )
    )

    evidence = _files_for_regex(
        repo_root,
        ["scripts/agent"],
        r"(?=.*dry[_-]?run)(?=.*runner)",
    )
    partial = _files_for_regex(
        repo_root,
        ["scripts/agent"],
        r"dry[_-]?run|runner",
    )
    if evidence:
        dry_status, dry_report, dry_missing = "pass", evidence, []
    elif partial:
        dry_status = "partial"
        dry_report = partial
        dry_missing = ["scripts/agent/*dry_run*runner*"]
    else:
        dry_status, dry_report = "open", []
        dry_missing = ["scripts/agent/*dry_run*runner*"]

    results.append(
        CapabilityResult(
            "dry_run_runner",
            "Dry-run runner",
            True,
            dry_status,
            dry_report,
            dry_missing,
            "Dry-Run Runner prueft Agentenpfade ohne schreibende Seiteneffekte.",
        )
    )
    for result in results:
        if result.status not in VALID_STATUSES:
            raise ValueError(f"Invalid status for {result.id}: {result.status}")
    return results


def determine_overall_status(
    results: list[CapabilityResult],
) -> tuple[str, str, list[str]]:
    hard_gaps = [item.id for item in results if item.hard and item.status != "pass"]
    failing = [item.id for item in results if item.status == "fail"]
    passing = [item.id for item in results if item.status == "pass"]
    partial = [item.id for item in results if item.status == "partial"]

    if failing:
        reason = f"Inconsistent capability state detected: {', '.join(failing)}"
        return "fail", reason, hard_gaps
    if hard_gaps:
        reason = f"Hard capabilities are still missing: {', '.join(hard_gaps)}"
        return "partial", reason, hard_gaps
    if len(passing) == len(results):
        return "pass", "All hard and non-hard capabilities are present.", []
    if not passing and not partial:
        gaps = [item.id for item in results if item.hard]
        return "open", "No capability evidence detected yet.", gaps
    return "partial", "Capabilities are partially implemented.", hard_gaps


def render_report(
    results: list[CapabilityResult],
    overall: str,
    reason: str,
    hard_gaps: list[str],
) -> str:
    lines = [
        "---",
        "id: docs.generated.agent-readiness",
        "title: Agent Readiness",
        "doc_type: generated",
        "status: active",
        "summary: Deterministische Agent-Readiness-Matrix.",
        "---",
        "",
        "## Weltgewebe Agent Readiness",
        "",
        "Generated automatically. Do not edit.",
        "",
        "## Overall Status",
        "",
        f"- **Overall:** {overall}",
        f"- **Reason:** {reason}",
        "",
        "## Capability Matrix",
        "",
        "| Capability | Status | Hard | Evidence | Missing | Rationale |",
        "|---|---|---:|---|---|---|",
    ]
    for result in results:
        evidence = (
            ", ".join(f"`{item}`" for item in result.evidence)
            if result.evidence
            else "-"
        )
        missing = (
            ", ".join(f"`{item}`" for item in result.missing)
            if result.missing
            else "-"
        )
        hard = "yes" if result.hard else "no"
        lines.append(
            f"| {result.id} | {result.status} | {hard} | "
            f"{evidence} | {missing} | {result.rationale} |"
        )

    lines.extend(["", "## Residual Gaps", ""])
    if hard_gaps:
        lines.extend(
            f"- Hard capability missing: {capability}"
            for capability in hard_gaps
        )
    else:
        lines.append("- No residual hard gaps detected.")
    lines.extend(
        [
            "",
            "## Interpretation Rule",
            "",
            "Dieser Report ist diagnostisch. Er aktiviert keinen Blocking-Mode.",
            "",
        ]
    )
    return "\n".join(lines)


def generate(repo_root: str | Path | None = None) -> Path:
    root = Path(repo_root) if repo_root is not None else Path(REPO_ROOT)
    out_file = root / "docs" / "_generated" / "agent-readiness.md"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    results = evaluate_capabilities(root)
    overall, reason, hard_missing = determine_overall_status(results)
    out_file.write_text(
        render_report(results, overall, reason, hard_missing),
        encoding="utf-8",
    )
    return out_file


def main() -> int:
    try:
        print(f"Generated {generate()}")
        return 0
    except Exception as exc:
        print(f"Error generating agent readiness: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
