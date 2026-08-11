from __future__ import annotations

import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github" / "workflows" / "security.yml"
PINNED_TRIVY_ACTION = re.compile(r"^aquasecurity/trivy-action@[0-9a-f]{40}$")


def load_workflow() -> tuple[dict, dict]:
    payload = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    triggers = payload.get("on", payload.get(True))
    assert isinstance(triggers, dict)
    return payload, triggers


def test_trivy_scans_the_production_api_image_and_blocks_high_severity_findings() -> None:
    payload, triggers = load_workflow()
    image_scan = payload["jobs"]["image-scan"]
    steps = image_scan["steps"]

    build_step = next(step for step in steps if step.get("name") == "Build production API image")
    build_command = build_step["run"]
    assert "--file apps/api/Dockerfile" in build_command
    assert 'GIT_COMMIT_SHA=${GITHUB_SHA}' in build_command
    assert "BUILD_TIMESTAMP=" in build_command
    assert "weltgewebe-api:trivy-scan" in build_command

    trivy_step = next(
        step
        for step in steps
        if str(step.get("uses", "")).startswith("aquasecurity/trivy-action@")
    )
    assert PINNED_TRIVY_ACTION.fullmatch(trivy_step["uses"])
    inputs = trivy_step["with"]
    assert inputs["scan-type"] == "image"
    assert inputs["image-ref"] == "weltgewebe-api:trivy-scan"
    assert inputs["scanners"] == "vuln"
    assert inputs["vuln-type"] == "os,library"
    assert inputs["severity"] == "HIGH,CRITICAL"
    assert inputs["ignore-unfixed"] is True
    assert str(inputs["exit-code"]) == "1"
    assert inputs["format"] == "json"
    assert inputs["output"] == "trivy-image-report.json"

    trigger_paths = set(triggers["pull_request"]["paths"])
    assert {
        ".github/workflows/security.yml",
        "apps/api/Dockerfile",
        "apps/api/entrypoint.sh",
        "Cargo.lock",
    } <= trigger_paths


def test_weekly_security_jobs_compare_the_schedule_string_directly() -> None:
    payload, _ = load_workflow()
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "github.event.schedule.cron" not in raw
    assert "github.event.schedule == '10 3 * * 0'" in payload["jobs"]["deny"]["if"]
    assert "github.event.schedule == '25 3 * * 0'" in payload["jobs"]["sbom"]["if"]
    assert "github.event.schedule == '25 3 * * 0'" in payload["jobs"]["image-scan"]["if"]
