#!/usr/bin/env python3
import re
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

    results.append(
        _evaluate_required_files(
            root=repo_root,
            cap_id="handoff_validation",
            title="Handoff validation",
            hard=True,
            required_files=[
                "contracts/agent/handoff.schema.json",
                "scripts/agent/validate_handoff.py",
                "scripts/agent/tests/test_validate_handoff.py",
                "tests/fixtures/agent/handoff-valid.json",
            ],
            rationale="Handoff-Checks begrenzen unvollstaendige oder unsichere Uebergaben.",
        )
    )

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

    dry_run_evidence = _files_for_regex(
        repo_root,
        ["scripts/agent"],
        r"(?=.*dry[_-]?run)(?=.*runner)",
    )
    dry_run_partial = _files_for_regex(
        repo_root,
        ["scripts/agent"],
        r"dry[_-]?run|runner",
    )
    if dry_run_evidence:
        dry_run_status = "pass"
        dry_run_missing: list[str] = []
        dry_run_report = dry_run_evidence
    elif dry_run_partial:
        dry_run_status = "partial"
        dry_run_missing = ["scripts/agent/*dry_run*runner*"]
        dry_run_report = dry_run_partial
    else:
        dry_run_status = "open"
        dry_run_missing = ["scripts/agent/*dry_run*runner*"]
        dry_run_report = []
    results.append(
        CapabilityResult(
            id="dry_run_runner",
            title="Dry-run runner",
            hard=True,
            status=dry_run_status,
            evidence=dry_run_report,
            missing=dry_run_missing,
            rationale="Dry-Run Runner prueft Agentenpfade ohne schreibende Seiteneffekte.",
        )
    )

    for result in results:
        if result.status not in VALID_STATUSES:
            raise ValueError(f"Invalid status for {result.id}: {result.status}")

    return results


def determine_overall_status(results: list[CapabilityResult]) -> tuple[str, str, list[str]]:
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
        return "open", "No capability evidence detected yet.", [r.id for r in results if r.hard]

    return "partial", "Capabilities are partially implemented.", hard_gaps


def render_report(results: list[CapabilityResult], overall: str, reason: str, hard_gaps: list[str]) -> str:
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

    for result in results:
        evidence = ", ".join(f"`{item}`" for item in result.evidence) if result.evidence else "-"
        missing = ", ".join(f"`{item}`" for item in result.missing) if result.missing else "-"
        hard = "yes" if result.hard else "no"
        lines.append(
            f"| {result.id} | {result.status} | {hard} | {evidence} | {missing} | {result.rationale} |"
        )

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
