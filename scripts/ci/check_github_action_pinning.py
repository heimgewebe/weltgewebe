#!/usr/bin/env python3
"""Audit GitHub Actions `uses:` references for SHA pinning readiness.

The scanner is dependency-free and intentionally conservative. It classifies
workflow `uses:` entries; it does not modify workflow files and it does not
prove the runtime semantics of external actions or reusable workflows.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

USES_RE = re.compile(r"^\s*-?\s*uses\s*:\s*(?P<uses>[^#\s]+)")
JOB_RE = re.compile(r"^  (?P<job>[A-Za-z0-9_-]+)\s*:\s*(?:#.*)?$")
HEX40_RE = re.compile(r"^[0-9a-fA-F]{40}$")
MUTABLE_DEFAULT_BRANCHES = {"main", "master", "trunk"}
BLOCKING_POLICIES = {"named-ref", "mutable-default-branch", "missing-ref"}


@dataclass(frozen=True)
class ActionRef:
    workflow: Path
    job: str
    uses: str
    kind: str
    ref_type: str
    ref_value: str
    policy: str


def clean_uses(raw_uses: str) -> str:
    return raw_uses.strip().strip('"\'')


def workflow_paths(workflows_dir: Path) -> list[Path]:
    return sorted({*workflows_dir.glob("*.yml"), *workflows_dir.glob("*.yaml")})


def split_ref(uses: str) -> tuple[str, str]:
    target, sep, ref = uses.partition("@")
    return target, ref if sep else ""


def ref_type_for(ref_value: str) -> str:
    if not ref_value:
        return "no-ref"
    if HEX40_RE.fullmatch(ref_value):
        return "sha"
    return "named-ref"


def kind_for(target: str) -> str:
    if target.startswith("./") or target.startswith("../"):
        return "local-action"
    if target.startswith("docker://"):
        return "docker-image"
    if ".github/workflows/" in target:
        return "reusable-workflow"
    return "github-action"


def policy_for(kind: str, ref_type: str, ref_value: str) -> str:
    if kind == "local-action":
        return "local"
    if kind == "docker-image":
        return "docker-ref"
    if ref_type == "sha":
        return "pinned-sha"
    if ref_type == "no-ref":
        return "missing-ref"
    if ref_value in MUTABLE_DEFAULT_BRANCHES:
        return "mutable-default-branch"
    return "named-ref"


def scan_workflow(path: Path) -> list[ActionRef]:
    refs: list[ActionRef] = []
    current_job = "unknown"
    in_jobs = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("jobs:"):
            in_jobs = True
            current_job = "unknown"
            continue
        if in_jobs and line and not line.startswith((" ", "#")):
            in_jobs = False
            current_job = "unknown"
        if in_jobs:
            job_match = JOB_RE.match(line)
            if job_match:
                current_job = job_match.group("job")
        uses_match = USES_RE.match(line)
        if not uses_match:
            continue
        uses = clean_uses(uses_match.group("uses"))
        target, ref_value = split_ref(uses)
        kind = kind_for(target)
        ref_type = ref_type_for(ref_value)
        refs.append(
            ActionRef(
                workflow=path,
                job=current_job,
                uses=uses,
                kind=kind,
                ref_type=ref_type,
                ref_value=ref_value,
                policy=policy_for(kind, ref_type, ref_value),
            )
        )
    return refs


def scan(workflows_dir: Path) -> list[ActionRef]:
    refs: list[ActionRef] = []
    for path in workflow_paths(workflows_dir):
        refs.extend(scan_workflow(path))
    return refs


def print_report(refs: list[ActionRef]) -> None:
    by_policy: dict[str, int] = {}
    by_kind: dict[str, int] = {}
    for ref in refs:
        by_policy[ref.policy] = by_policy.get(ref.policy, 0) + 1
        by_kind[ref.kind] = by_kind.get(ref.kind, 0) + 1
    print("GitHub Actions reference pinning audit:")
    print(f"total={len(refs)}")
    for key in sorted(by_kind):
        print(f"kind.{key}={by_kind[key]}")
    for key in sorted(by_policy):
        print(f"policy.{key}={by_policy[key]}")
    for ref in refs:
        print(
            f"- {ref.workflow} {ref.job} -> {ref.uses} "
            f"kind={ref.kind} ref={ref.ref_type} policy={ref.policy}"
        )


def main() -> int:
    refs = scan(Path(".github/workflows"))
    print_report(refs)
    blocked = [
        ref
        for ref in refs
        if ref.kind in {"github-action", "reusable-workflow"}
        and ref.policy in BLOCKING_POLICIES
    ]
    if blocked:
        print()
        print("ERROR: external GitHub Actions and reusable workflows must be pinned to 40-character commit SHAs.")
        print("Allowed without a GitHub SHA: local actions (./ or ../) and docker:// image actions.")
        for ref in blocked:
            print(f"- {ref.workflow} {ref.job}: {ref.uses} policy={ref.policy}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
