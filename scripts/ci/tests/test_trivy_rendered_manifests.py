from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "scripts/security/trivy_rendered_manifests.py"
SPEC = importlib.util.spec_from_file_location("trivy_rendered_manifests", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
trivy_scan = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(trivy_scan)


class TrivyRenderedManifestTests(unittest.TestCase):
    def test_canonical_targets_come_from_validator_readback(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["python"],
            returncode=0,
            stdout=json.dumps(
                {
                    "status": "pass",
                    "rendered_documents": {
                        "platform/a": 2,
                        "platform/b": 3,
                    },
                }
            ),
            stderr="",
        )
        with mock.patch.object(trivy_scan, "_run", return_value=completed) as run:
            targets = trivy_scan.canonical_render_targets()
        self.assertEqual(targets, ["platform/a", "platform/b"])
        self.assertIn("--render", run.call_args.args[0])

    def test_invalid_validator_readback_fails_closed(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["python"],
            returncode=0,
            stdout=json.dumps({"status": "pass", "rendered_documents": {"outside/a": 1}}),
            stderr="",
        )
        with mock.patch.object(trivy_scan, "_run", return_value=completed):
            with self.assertRaisesRegex(trivy_scan.TrivyProductionError, "invalid render target"):
                trivy_scan.canonical_render_targets()

    def test_misconfiguration_summary_counts_findings_and_unique_rules(self) -> None:
        summary = trivy_scan.summarize_misconfig_report(
            {
                "Results": [
                    {
                        "Misconfigurations": [
                            {"ID": "KSV-0001", "Severity": "HIGH"},
                            {"ID": "KSV-0001", "Severity": "LOW"},
                            {"AVDID": "KSV-0002", "Severity": "MEDIUM"},
                        ]
                    }
                ]
            }
        )
        self.assertEqual(summary["finding_count"], 3)
        self.assertEqual(summary["rule_id_count"], 2)
        self.assertEqual(summary["rule_ids"], ["KSV-0001", "KSV-0002"])
        self.assertEqual(summary["severity_counts"], {"HIGH": 1, "LOW": 1, "MEDIUM": 1})

    def test_findings_are_advisory_but_command_failure_is_not(self) -> None:
        command = trivy_scan.trivy_config_command("trivy", Path("cache"), Path("report.json"), Path("rendered"))
        self.assertIn("--skip-check-update", command)
        self.assertNotIn("--exit-code", command)
        with mock.patch.object(
            trivy_scan.subprocess,
            "run",
            side_effect=subprocess.CalledProcessError(1, ["trivy"]),
        ):
            with self.assertRaisesRegex(trivy_scan.TrivyProductionError, "command failed"):
                trivy_scan._run(["trivy", "config"])

    def test_bootstrap_requests_only_security_tools(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["python"],
            returncode=0,
            stdout=json.dumps({"tools": {"kustomize": "/kustomize", "trivy": "/trivy"}}),
            stderr="",
        )
        with mock.patch.object(trivy_scan, "_run", return_value=completed) as run:
            tools = trivy_scan.bootstrap_security_tools()
        self.assertEqual(tools, {"kustomize": "/kustomize", "trivy": "/trivy"})
        argv = run.call_args.args[0]
        self.assertEqual(argv.count("--tool"), 2)
        self.assertIn("--skip-artifacts", argv)
        self.assertNotIn("kind", argv)

    def test_render_targets_rejects_empty_output(self) -> None:
        completed = subprocess.CompletedProcess(args=["kustomize"], returncode=0, stdout="", stderr="")
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(trivy_scan, "_run", return_value=completed):
                with self.assertRaisesRegex(trivy_scan.TrivyProductionError, "empty Kustomize output"):
                    trivy_scan.render_targets("kustomize", ["platform/a"], Path(tmp))


if __name__ == "__main__":
    unittest.main()
