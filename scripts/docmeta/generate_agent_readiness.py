#!/usr/bin/env python3
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

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


def _required(root, cap_id, title, hard, files, rationale):
    evidence, missing = [], []
    for rel in files:
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
        cap_id, title, hard, status, evidence, missing, rationale
    )


def _handoff(root):
    presence = _required(
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
        run = subprocess.run(
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
    if run.returncode:
        diagnostic = (run.stderr or run.stdout).strip()
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


def _regex_files(root, regex):
    matcher = re.compile(regex)
    found = []
    base = root / "scripts/agent"
    if not base.is_dir():
        return found
    for path in base.rglob("*"):
        if path.is_file():
            rel = str(path.relative_to(root)).replace("\\", "/")
            if matcher.search(rel.lower()):
                found.append(rel)
    return sorted(set(found))


def evaluate_capabilities(repo_root):
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
    out = [_required(repo_root, *spec) for spec in specs]
    out.append(_handoff(repo_root))
    out.append(
        _required(
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

    evidence = _regex_files(repo_root, r"(?=.*dry[_-]?run)(?=.*runner)")
    partial = _regex_files(repo_root, r"dry[_-]?run|runner")
    if evidence:
        status, shown, missing = "pass", evidence, []
    elif partial:
        status, shown = "partial", partial
        missing = ["scripts/agent/*dry_run*runner*"]
    else:
        status, shown = "open", []
        missing = ["scripts/agent/*dry_run*runner*"]
    out.append(
        CapabilityResult(
            "dry_run_runner",
            "Dry-run runner",
            True,
            status,
            shown,
            missing,
            "Dry-Run Runner prueft Agentenpfade ohne schreibende Seiteneffekte.",
        )
    )
    for item in out:
        if item.status not in VALID_STATUSES:
            raise ValueError(f"Invalid status for {item.id}: {item.status}")
    return out


def determine_overall_status(results):
    gaps = [item.id for item in results if item.hard and item.status != "pass"]
    failing = [item.id for item in results if item.status == "fail"]
    passing = [item.id for item in results if item.status == "pass"]
    partial = [item.id for item in results if item.status == "partial"]
    if failing:
        return (
            "fail",
            f"Inconsistent capability state detected: {', '.join(failing)}",
            gaps,
        )
    if gaps:
        return (
            "partial",
            f"Hard capabilities are still missing: {', '.join(gaps)}",
            gaps,
        )
    if len(passing) == len(results):
        return "pass", "All hard and non-hard capabilities are present.", []
    if not passing and not partial:
        hard = [item.id for item in results if item.hard]
        return "open", "No capability evidence detected yet.", hard
    return "partial", "Capabilities are partially implemented.", gaps


def _display(items):
    if not items:
        return "-"
    shown = items[:4]
    text = ", ".join(f"`{item}`" for item in shown)
    if len(items) > len(shown):
        text += f", … (+{len(items) - len(shown)} more)"
    return text


def render_report(results, overall, reason, gaps):
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
    for item in results:
        hard = "yes" if item.hard else "no"
        lines.append(
            f"| {item.id} | {item.status} | {hard} | "
            f"{_display(item.evidence)} | {_display(item.missing)} | "
            f"{item.rationale} |"
        )
    lines.extend(["", "## Residual Gaps", ""])
    if gaps:
        lines.extend(f"- Hard capability missing: {gap}" for gap in gaps)
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


def generate(repo_root=None):
    root = Path(repo_root) if repo_root is not None else Path(REPO_ROOT)
    out_file = root / "docs/_generated/agent-readiness.md"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    results = evaluate_capabilities(root)
    overall, reason, gaps = determine_overall_status(results)
    out_file.write_text(
        render_report(results, overall, reason, gaps),
        encoding="utf-8",
    )
    return out_file


def main():
    try:
        print(f"Generated {generate()}")
        return 0
    except Exception as exc:
        print(f"Error generating agent readiness: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
