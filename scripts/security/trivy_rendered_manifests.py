#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "build/security/trivy"
DEFAULT_CACHE = ROOT / ".cache/weltgewebe-trivy"


class TrivyProductionError(RuntimeError):
    pass


def _run(command: Sequence[str], *, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(command),
            cwd=cwd,
            text=True,
            check=True,
            capture_output=True,
            timeout=300,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise TrivyProductionError(f"command failed: {command[0]}") from exc


def canonical_render_targets() -> list[str]:
    completed = _run([sys.executable, "scripts/platform/validate_platform.py", "--render"])
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise TrivyProductionError("platform validator returned invalid JSON") from exc
    rendered = payload.get("rendered_documents")
    if payload.get("status") != "pass" or not isinstance(rendered, dict) or not rendered:
        raise TrivyProductionError("platform validator did not return canonical rendered targets")
    targets = list(rendered)
    if any(not isinstance(target, str) or not target.startswith("platform/") for target in targets):
        raise TrivyProductionError("platform validator returned an invalid render target")
    return targets


def bootstrap_security_tools() -> dict[str, str]:
    completed = _run(
        [
            sys.executable,
            "scripts/platform/bootstrap_tools.py",
            "--json",
            "--tool",
            "kustomize",
            "--tool",
            "trivy",
            "--skip-artifacts",
        ]
    )
    try:
        payload = json.loads(completed.stdout)
        tools = payload["tools"]
        selected = {name: tools[name] for name in ("kustomize", "trivy")}
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise TrivyProductionError("tool bootstrap returned an invalid receipt") from exc
    return selected


def _target_slug(target: str) -> str:
    return target.replace("/", "__")


def render_targets(kustomize: str, targets: Sequence[str], destination: Path) -> dict[str, str]:
    destination.mkdir(parents=True, exist_ok=True)
    rendered_paths: dict[str, str] = {}
    for target in targets:
        completed = _run([kustomize, "build", target])
        if not completed.stdout.strip():
            raise TrivyProductionError(f"empty Kustomize output for {target}")
        output = destination / f"{_target_slug(target)}.yaml"
        output.write_text(completed.stdout, encoding="utf-8")
        rendered_paths[target] = str(output)
    return rendered_paths


def summarize_misconfig_report(report: dict[str, Any]) -> dict[str, Any]:
    results = report.get("Results", [])
    if results is None:
        results = []
    if not isinstance(results, list):
        raise TrivyProductionError("Trivy report Results must be a list")
    severities: Counter[str] = Counter()
    rule_ids: set[str] = set()
    total = 0
    for result in results:
        if not isinstance(result, dict):
            raise TrivyProductionError("Trivy report contains an invalid result")
        findings = result.get("Misconfigurations") or []
        if not isinstance(findings, list):
            raise TrivyProductionError("Trivy report Misconfigurations must be a list")
        for finding in findings:
            if not isinstance(finding, dict):
                raise TrivyProductionError("Trivy report contains an invalid misconfiguration")
            total += 1
            severity = finding.get("Severity")
            severities[str(severity).upper() if severity else "UNKNOWN"] += 1
            rule_id = finding.get("ID") or finding.get("AVDID")
            if rule_id:
                rule_ids.add(str(rule_id))
    return {
        "finding_count": total,
        "rule_id_count": len(rule_ids),
        "rule_ids": sorted(rule_ids),
        "severity_counts": dict(sorted(severities.items())),
    }


def trivy_config_command(trivy: str, cache: Path, report: Path, rendered_dir: Path) -> list[str]:
    return [
        trivy,
        "--cache-dir",
        str(cache),
        "config",
        "--skip-check-update",
        "--format",
        "json",
        "--output",
        str(report),
        str(rendered_dir),
    ]


def trivy_sbom_command(trivy: str, cache: Path, output: Path) -> list[str]:
    return [
        trivy,
        "--cache-dir",
        str(cache),
        "fs",
        "--format",
        "cyclonedx",
        "--output",
        str(output),
        str(ROOT),
    ]


def produce(output: Path = DEFAULT_OUTPUT, cache: Path = DEFAULT_CACHE) -> dict[str, Any]:
    targets = canonical_render_targets()
    tools = bootstrap_security_tools()
    output.parent.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="weltgewebe-trivy-") as tmp:
        stage = Path(tmp)
        rendered_dir = stage / "rendered"
        rendered_paths = render_targets(tools["kustomize"], targets, rendered_dir)
        misconfig_report = stage / "misconfigurations.json"
        sbom = stage / "sbom.cdx.json"

        _run(trivy_config_command(tools["trivy"], cache, misconfig_report, rendered_dir))
        try:
            report = json.loads(misconfig_report.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise TrivyProductionError("Trivy did not produce a valid misconfiguration report") from exc
        finding_summary = summarize_misconfig_report(report)

        _run(trivy_sbom_command(tools["trivy"], cache, sbom))
        try:
            sbom_payload = json.loads(sbom.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise TrivyProductionError("Trivy did not produce a valid CycloneDX SBOM") from exc
        if sbom_payload.get("bomFormat") != "CycloneDX":
            raise TrivyProductionError("Trivy SBOM is not CycloneDX")

        summary: dict[str, Any] = {
            "schema_version": 1,
            "status": "pass",
            "policy": "advisory-findings-fail-closed-on-execution-error",
            "canonical_target_count": len(targets),
            "canonical_targets": targets,
            "rendered_file_count": len(rendered_paths),
            "trivy_findings": finding_summary,
            "sbom_format": "CycloneDX",
        }
        summary_path = stage / "summary.json"
        summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        if output.is_symlink():
            raise TrivyProductionError("refusing symlinked output directory")
        if output.exists() and not output.is_dir():
            raise TrivyProductionError("output path is not a directory")
        output.mkdir(parents=True, exist_ok=True)
        shutil.copy2(misconfig_report, output / misconfig_report.name)
        shutil.copy2(sbom, output / sbom.name)
        shutil.copy2(summary_path, output / summary_path.name)

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan canonical rendered Kubernetes manifests with pinned Trivy and emit a CycloneDX SBOM.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    args = parser.parse_args()
    try:
        result = produce(args.output.expanduser().absolute(), args.cache.expanduser().absolute())
    except TrivyProductionError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
