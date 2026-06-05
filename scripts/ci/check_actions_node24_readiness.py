#!/usr/bin/env python3
"""Heuristically check known GitHub JavaScript Actions for Node-24 readiness."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

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
    "extractions/setup-just",
)


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


def force_env_enabled(env: object) -> bool:
    if not isinstance(env, dict):
        return False
    value = env.get(FORCE_ENV_KEY)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() == "true"
    return False


def ref_type_for(uses: str) -> str:
    parts = uses.split("@", 1)
    is_sha = len(parts) == 2 and len(parts[1]) == 40
    if is_sha:
        return "sha"
    if len(parts) == 2:
        return "named-ref"
    return "no-ref"


def is_known_javascript_action(uses: str) -> bool:
    action_name = uses.split("@", 1)[0]
    return any(
        action_name == prefix or action_name.startswith(f"{prefix}/")
        for prefix in KNOWN_JAVASCRIPT_ACTION_PREFIXES
    )


def workflow_paths(workflows_dir: Path) -> list[Path]:
    yml_paths = workflows_dir.glob("*.yml")
    yaml_paths = workflows_dir.glob("*.yaml")
    return sorted({*yml_paths, *yaml_paths})


def env_coverage(workflow_env: object, job_env: object) -> str:
    if force_env_enabled(job_env):
        return "job"
    if force_env_enabled(workflow_env):
        return "workflow"
    return "missing"


def scan_workflow(path: Path) -> tuple[list[DirectActionUse], list[ReusableWorkflowCall]]:
    with path.open("r", encoding="utf-8") as handle:
        workflow = yaml.safe_load(handle) or {}

    if not isinstance(workflow, dict):
        return [], []

    workflow_env = workflow.get("env")
    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict):
        return [], []

    direct_actions: list[DirectActionUse] = []
    reusable_workflows: list[ReusableWorkflowCall] = []

    for job_name, job in jobs.items():
        if not isinstance(job, dict):
            continue

        job_uses = job.get("uses")
        if isinstance(job_uses, str):
            reusable_workflows.append(
                ReusableWorkflowCall(workflow=path, job=str(job_name), uses=job_uses)
            )

        steps = job.get("steps")
        if not isinstance(steps, list):
            continue

        for step in steps:
            if not isinstance(step, dict):
                continue
            step_uses = step.get("uses")
            if not isinstance(step_uses, str):
                continue
            if not is_known_javascript_action(step_uses):
                continue
            direct_actions.append(
                DirectActionUse(
                    workflow=path,
                    job=str(job_name),
                    uses=step_uses,
                    ref_type=ref_type_for(step_uses),
                    env_coverage=env_coverage(workflow_env, job.get("env")),
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
