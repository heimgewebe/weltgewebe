#!/usr/bin/env python3
"""Heuristically check known GitHub JavaScript Actions for Node-24 readiness.

This is intentionally not a full YAML parser. It is a dependency-free,
repo-specific scanner for the workflow shapes used here. If workflows start
using more complex YAML constructs, Stage B should either extend this scanner
or add and declare a real YAML dependency explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

FORCE_ENV_KEY = "FORCE_JAVASCRIPT_ACTIONS_TO_NODE24"
KNOWN_JAVASCRIPT_ACTION_PREFIXES = (
    "actions/checkout",
    "actions/setup-node",
    "actions/cache",
    "actions/upload-artifact",
    "actions/download-artifact",
    "actions/setup-python",
    "pnpm/action-setup",
    "astral-sh/setup-uv",
    "dorny/paths-filter",
    "docker/setup-buildx-action",
    "extractions/setup-just",
    "lycheeverse/lychee-action",
    "softprops/action-gh-release",
)
USES_RE = re.compile(r"^\s*-?\s*uses\s*:\s*(?P<uses>[^#\s]+)")
ENV_RE = re.compile(r"^(?P<indent>\s*)env\s*:\s*(?:#.*)?$")
FORCE_ENV_RE = re.compile(
    rf"^(?P<indent>\s*){re.escape(FORCE_ENV_KEY)}\s*:\s*(?P<value>[^#\s]+)"
)
JOB_RE = re.compile(r"^  (?P<job>[A-Za-z0-9_-]+)\s*:\s*(?:#.*)?$")


@dataclass(frozen=True)
class DirectActionUse:
    workflow: Path
    job: str
    uses: str
    ref_type: str
    env_coverage: str


@dataclass(frozen=True)
class ReusableWorkflowCall:
    workflow: Path
    job: str
    uses: str


def truthy_env_value(value: str) -> bool:
    return value.strip().strip('"\'').lower() == "true"


def ref_type_for(uses: str) -> str:
    parts = uses.split("@", 1)
    is_sha = len(parts) == 2 and len(parts[1]) == 40
    if is_sha:
        return "sha"
    if len(parts) == 2:
        return "named-ref"
    return "no-ref"


def is_known_javascript_action(uses: str) -> bool:
    action_name = uses.split("@", 1)[0].strip('"\'')
    return any(
        action_name == prefix or action_name.startswith(f"{prefix}/")
        for prefix in KNOWN_JAVASCRIPT_ACTION_PREFIXES
    )


def workflow_paths(workflows_dir: Path) -> list[Path]:
    yml_paths = workflows_dir.glob("*.yml")
    yaml_paths = workflows_dir.glob("*.yaml")
    return sorted({*yml_paths, *yaml_paths})


def clean_uses(raw_uses: str) -> str:
    return raw_uses.strip().strip('"\'')


def detect_force_env(lines: list[str]) -> bool:
    """Return true when the force key appears as true inside any env block."""
    env_indent: int | None = None
    for line in lines:
        env_match = ENV_RE.match(line)
        if env_match:
            env_indent = len(env_match.group("indent"))
            continue

        if env_indent is not None:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            current_indent = len(line) - len(line.lstrip(" "))
            if current_indent <= env_indent:
                env_indent = None
            else:
                force_match = FORCE_ENV_RE.match(line)
                if force_match and truthy_env_value(force_match.group("value")):
                    return True
    return False


def scan_workflow(path: Path) -> tuple[list[DirectActionUse], list[ReusableWorkflowCall]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    env_status = "present" if detect_force_env(lines) else "missing"
    direct_actions: list[DirectActionUse] = []
    reusable_workflows: list[ReusableWorkflowCall] = []
    current_job = "unknown"
    in_jobs = False

    for line in lines:
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
        if ".github/workflows/" in uses:
            reusable_workflows.append(
                ReusableWorkflowCall(workflow=path, job=current_job, uses=uses)
            )
            continue
        if not is_known_javascript_action(uses):
            continue
        direct_actions.append(
            DirectActionUse(
                workflow=path,
                job=current_job,
                uses=uses,
                ref_type=ref_type_for(uses),
                env_coverage=env_status,
            )
        )

    return direct_actions, reusable_workflows


def scan(workflows_dir: Path) -> tuple[list[DirectActionUse], list[ReusableWorkflowCall]]:
    direct_actions: list[DirectActionUse] = []
    reusable_workflows: list[ReusableWorkflowCall] = []
    for path in workflow_paths(workflows_dir):
        workflow_actions, workflow_reusable = scan_workflow(path)
        direct_actions.extend(workflow_actions)
        reusable_workflows.extend(workflow_reusable)
    return direct_actions, reusable_workflows


def print_report(
    direct_actions: list[DirectActionUse], reusable_workflows: list[ReusableWorkflowCall]
) -> None:
    if direct_actions:
        print("Direct JavaScript GitHub Actions detected:")
        for action in direct_actions:
            print(
                "- "
                f"{action.workflow} {action.job} -> {action.uses} "
                f"ref={action.ref_type} env={action.env_coverage}"
            )

    missing = [action for action in direct_actions if action.env_coverage == "missing"]
    if missing:
        print("Missing FORCE_JAVASCRIPT_ACTIONS_TO_NODE24 for directly executed JavaScript actions:")
        for action in missing:
            print(f"- {action.workflow} {action.job} -> {action.uses}")

    if reusable_workflows:
        print(
            "Reusable workflow calls detected; caller env does not prove called workflow "
            "Node-24 readiness:"
        )
        for reusable in reusable_workflows:
            print(f"- {reusable.workflow} {reusable.job} -> {reusable.uses}")


def main() -> int:
    direct_actions, reusable_workflows = scan(Path(".github/workflows"))
    print_report(direct_actions, reusable_workflows)
    if any(action.env_coverage == "missing" for action in direct_actions):
        return 1
    print("All good!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
