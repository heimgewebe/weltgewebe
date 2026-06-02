import io
import json
import os
import tempfile
import unittest
from unittest.mock import patch

import scripts.docmeta.check_planning_registration as check_plan


class TestCheckPlanningRegistration(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.repo_root = self.test_dir.name

        self.patcher = patch(
            "scripts.docmeta.check_planning_registration.REPO_ROOT",
            self.repo_root,
        )
        self.patcher.start()

        os.makedirs(os.path.join(self.repo_root, "docs/tasks"), exist_ok=True)
        os.makedirs(os.path.join(self.repo_root, "docs/blueprints"), exist_ok=True)
        os.makedirs(os.path.join(self.repo_root, "docs/_generated/reports"), exist_ok=True)
        os.makedirs(os.path.join(self.repo_root, "docs/proofs"), exist_ok=True)

        self.write_file("docs/tasks/index.json", "{}")
        self.write_file("docs/tasks/board.md", "")
        self.write_file("docs/roadmap.md", "")

    def tearDown(self):
        self.patcher.stop()
        self.test_dir.cleanup()

    def write_file(self, rel_path, content):
        full_path = os.path.join(self.repo_root, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

    # ── config tests ─────────────────────────────────────────────────────────

    def test_config_loads_successfully(self):
        config, finding = check_plan.load_config()
        self.assertIsNone(finding)
        self.assertIn("scan_patterns", config)
        self.assertIn("planning_doc_types", config)
        self.assertIn("terminal_statuses", config)
        self.assertIn("registration_sources", config)
        self.assertEqual(config["version"], 1)

    def test_missing_config_is_reported(self):
        with patch(
            "scripts.docmeta.check_planning_registration.CONFIG_PATH",
            "/nonexistent/planning_registration.yml",
        ):
            config, finding = check_plan.load_config()
        self.assertIsNotNone(finding)
        self.assertEqual(finding["code"], "CONFIG_MISSING")
        self.assertEqual(config, check_plan._DEFAULT_CONFIG)

    def test_invalid_config_is_reported(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False, encoding="utf-8"
        ) as f:
            f.write(": this is not valid yaml mapping root\n")
            tmp_path = f.name
        try:
            with patch(
                "scripts.docmeta.check_planning_registration.CONFIG_PATH",
                tmp_path,
            ):
                config, finding = check_plan.load_config()
        finally:
            os.unlink(tmp_path)
        self.assertIsNotNone(finding)
        self.assertEqual(finding["code"], "CONFIG_INVALID")
        self.assertEqual(config, check_plan._DEFAULT_CONFIG)

    def test_missing_config_produces_finding_in_main(self):
        self.write_file("docs/blueprints/unreg.md", "---\nstatus: active\n---\nBody")
        with patch(
            "scripts.docmeta.check_planning_registration.CONFIG_PATH",
            "/nonexistent/planning_registration.yml",
        ):
            with patch("sys.stderr", new_callable=io.StringIO):
                with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                    exit_code = check_plan.main(["--format", "json"])
        data = json.loads(mock_out.getvalue())
        codes = [f["code"] for f in data["findings"]]
        self.assertIn("CONFIG_MISSING", codes)
        self.assertEqual(exit_code, 0)

    def test_invalid_config_produces_finding_in_strict(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False, encoding="utf-8"
        ) as f:
            f.write("not_a_mapping\n")
            tmp_path = f.name
        try:
            with patch(
                "scripts.docmeta.check_planning_registration.CONFIG_PATH",
                tmp_path,
            ):
                with patch("sys.stderr", new_callable=io.StringIO):
                    exit_code = check_plan.main(["--mode", "strict"])
        finally:
            os.unlink(tmp_path)
        self.assertEqual(exit_code, 1)

    # ── mode tests ───────────────────────────────────────────────────────────

    def test_report_mode_exits_zero_with_findings(self):
        self.write_file("docs/blueprints/unreg.md", "---\nstatus: active\n---\nBody")
        with patch("sys.stderr", new_callable=io.StringIO):
            exit_code = check_plan.main(["--mode", "report"])
        self.assertEqual(exit_code, 0)

    def test_warn_mode_exits_zero_with_findings(self):
        self.write_file("docs/blueprints/unreg.md", "---\nstatus: active\n---\nBody")
        with patch("sys.stderr", new_callable=io.StringIO):
            with patch("sys.stdout", new_callable=io.StringIO):
                exit_code = check_plan.main(["--mode", "warn"])
        self.assertEqual(exit_code, 0)

    def test_warn_mode_emits_github_annotation(self):
        self.write_file("docs/blueprints/unreg.md", "---\nstatus: active\n---\nBody")
        with patch("sys.stderr", new_callable=io.StringIO):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                check_plan.main(["--mode", "warn"])
        self.assertIn("::warning", mock_out.getvalue())

    def test_strict_mode_exits_one_with_findings(self):
        self.write_file("docs/blueprints/unreg.md", "---\nstatus: active\n---\nBody")
        with patch("sys.stderr", new_callable=io.StringIO):
            exit_code = check_plan.main(["--mode", "strict"])
        self.assertEqual(exit_code, 1)

    def test_strict_mode_exits_zero_without_findings(self):
        with patch("sys.stdout", new_callable=io.StringIO):
            exit_code = check_plan.main(["--mode", "strict"])
        self.assertEqual(exit_code, 0)

    def test_no_mode_defaults_to_report(self):
        self.write_file("docs/blueprints/unreg.md", "---\nstatus: active\n---\nBody")
        with patch("sys.stderr", new_callable=io.StringIO):
            exit_code = check_plan.main([])
        self.assertEqual(exit_code, 0)

    def test_strict_alias_same_as_mode_strict(self):
        self.write_file("docs/blueprints/unreg.md", "---\nstatus: active\n---\nBody")
        with patch("sys.stderr", new_callable=io.StringIO):
            code_alias = check_plan.main(["--strict"])
            code_mode = check_plan.main(["--mode", "strict"])
        self.assertEqual(code_alias, 1)
        self.assertEqual(code_mode, 1)
        self.assertEqual(code_alias, code_mode)

    # ── JSON output tests ─────────────────────────────────────────────────────

    def test_json_output_valid_no_findings(self):
        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            exit_code = check_plan.main(["--format", "json"])
        data = json.loads(mock_out.getvalue())
        self.assertTrue(data["ok"])
        self.assertEqual(data["finding_count"], 0)
        self.assertEqual(data["findings"], [])
        self.assertEqual(data["format"], "json")
        self.assertEqual(data["mode"], "report")
        self.assertEqual(exit_code, 0)

    def test_json_output_valid_with_findings(self):
        self.write_file("docs/blueprints/unreg.md", "---\nstatus: active\n---\nBody")
        with patch("sys.stderr", new_callable=io.StringIO):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                exit_code = check_plan.main(["--format", "json"])
        data = json.loads(mock_out.getvalue())
        self.assertFalse(data["ok"])
        self.assertGreater(data["finding_count"], 0)
        self.assertIsInstance(data["findings"], list)
        self.assertEqual(data["format"], "json")
        self.assertEqual(data["mode"], "report")
        self.assertEqual(exit_code, 0)

    def test_json_output_deterministic(self):
        self.write_file("docs/blueprints/b.md", "---\nstatus: active\n---\nBody")
        self.write_file("docs/blueprints/a.md", "---\nstatus: active\n---\nBody")

        results = []
        for _ in range(2):
            with patch("sys.stderr", new_callable=io.StringIO):
                with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                    check_plan.main(["--format", "json"])
            results.append(mock_out.getvalue())

        self.assertEqual(results[0], results[1])
        data = json.loads(results[0])
        paths = [f["path"] for f in data["findings"]]
        self.assertEqual(paths, sorted(paths))

    def test_json_output_strict_exits_one(self):
        self.write_file("docs/blueprints/unreg.md", "---\nstatus: active\n---\nBody")
        with patch("sys.stderr", new_callable=io.StringIO):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                exit_code = check_plan.main(["--format", "json", "--mode", "strict"])
        data = json.loads(mock_out.getvalue())
        self.assertEqual(data["mode"], "strict")
        self.assertFalse(data["ok"])
        self.assertEqual(exit_code, 1)

    def test_json_output_warn_mode(self):
        self.write_file("docs/blueprints/unreg.md", "---\nstatus: active\n---\nBody")
        with patch("sys.stderr", new_callable=io.StringIO):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                exit_code = check_plan.main(["--format", "json", "--mode", "warn"])
        data = json.loads(mock_out.getvalue())
        self.assertEqual(data["mode"], "warn")
        self.assertEqual(exit_code, 0)

    def test_json_finding_has_required_fields(self):
        self.write_file("docs/blueprints/unreg.md", "---\nstatus: active\n---\nBody")
        with patch("sys.stderr", new_callable=io.StringIO):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                check_plan.main(["--format", "json"])
        data = json.loads(mock_out.getvalue())
        unreg = [f for f in data["findings"] if f["code"] == "UNREGISTERED_PLANNING_ARTIFACT"]
        self.assertEqual(len(unreg), 1)
        for field in ("code", "path", "reason", "suggestion", "source"):
            self.assertIn(field, unreg[0])
        self.assertEqual(unreg[0]["source"], "planning-registration")

    # ── registration behavior tests ───────────────────────────────────────────

    def test_active_blueprint_in_index_json_passes(self):
        self.write_file("docs/tasks/index.json", json.dumps({
            "tasks": [{"id": "T1", "evidence": ["docs/blueprints/active-bp.md"]}]
        }))
        self.write_file("docs/blueprints/active-bp.md", "---\nid: active\nstatus: active\n---\nBody")

        findings = check_plan.run_checks()
        self.assertEqual(len(findings), 0)

    def test_active_blueprint_in_roadmap_passes(self):
        self.write_file("docs/roadmap.md", "Here is my [roadmap doc](blueprints/active-bp.md).")
        self.write_file("docs/blueprints/active-bp.md", "---\nid: active\nstatus: active\n---\nBody")

        findings = check_plan.run_checks()
        self.assertEqual(len(findings), 0)

    def test_active_blueprint_in_board_passes(self):
        self.write_file("docs/tasks/board.md", "| T1 | `docs/blueprints/active-bp.md` |")
        self.write_file("docs/blueprints/active-bp.md", "---\nid: active\nstatus: active\n---\nBody")

        findings = check_plan.run_checks()
        self.assertEqual(len(findings), 0)

    def test_active_blueprint_with_frontmatter_relation_to_tasks_passes(self):
        self.write_file(
            "docs/blueprints/related.md",
            "---\nrelations:\n  - type: relates_to\n    target: docs/tasks/index.json\n---\nBody",
        )

        findings = check_plan.run_checks()
        unregistered = [f for f in findings if f["code"] == "UNREGISTERED_PLANNING_ARTIFACT"]
        self.assertEqual(unregistered, [])

    def test_active_blueprint_with_frontmatter_relation_to_roadmap_passes(self):
        self.write_file(
            "docs/blueprints/related.md",
            "---\nrelations:\n  - type: relates_to\n    target: docs/roadmap.md\n---\nBody",
        )

        findings = check_plan.run_checks()
        unregistered = [f for f in findings if f["code"] == "UNREGISTERED_PLANNING_ARTIFACT"]
        self.assertEqual(unregistered, [])

    def test_unregistered_active_blueprint_is_reported(self):
        self.write_file(
            "docs/blueprints/unregistered.md", "---\nid: unreg\nstatus: active\n---\nBody"
        )

        findings = check_plan.run_checks()
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["code"], "UNREGISTERED_PLANNING_ARTIFACT")
        self.assertEqual(findings[0]["path"], "docs/blueprints/unregistered.md")

    def test_deprecated_or_superseded_blueprint_is_ignored(self):
        self.write_file("docs/blueprints/dep.md", "---\nstatus: deprecated\n---\nBody")
        self.write_file("docs/blueprints/sup.md", "---\nstatus: superseded\n---\nBody")

        findings = check_plan.run_checks()
        unregistered = [f for f in findings if f["code"] == "UNREGISTERED_PLANNING_ARTIFACT"]
        self.assertEqual(unregistered, [])

    def test_archived_and_deferred_blueprint_is_ignored(self):
        self.write_file("docs/blueprints/arch.md", "---\nstatus: archived\n---\nBody")
        self.write_file("docs/blueprints/def.md", "---\nstatus: deferred\n---\nBody")

        findings = check_plan.run_checks()
        unregistered = [f for f in findings if f["code"] == "UNREGISTERED_PLANNING_ARTIFACT"]
        self.assertEqual(unregistered, [])

    def test_generated_and_proofs_files_are_ignored(self):
        self.write_file("docs/_generated/reports/my-status-1.md", "---\nstatus: active\n---\nBody")
        self.write_file("docs/proofs/blueprint2.md", "---\nstatus: active\n---\nBody")

        findings = check_plan.run_checks()
        unregistered = [f for f in findings if f["code"] == "UNREGISTERED_PLANNING_ARTIFACT"]
        self.assertEqual(unregistered, [])

    def test_draft_spec_without_planning_doc_type_is_not_reported(self):
        self.write_file(
            "docs/specs/auth-api.md", "---\nstatus: draft\ndoc_type: spec\n---\nBody"
        )
        os.makedirs(os.path.join(self.repo_root, "docs/specs"), exist_ok=True)

        findings = check_plan.run_checks()
        unregistered = [f for f in findings if f["code"] == "UNREGISTERED_PLANNING_ARTIFACT"]
        self.assertEqual(unregistered, [])

    def test_spec_with_plan_doc_type_is_reported_when_unregistered(self):
        os.makedirs(os.path.join(self.repo_root, "docs/specs"), exist_ok=True)
        self.write_file(
            "docs/specs/auth-next-step.md",
            "---\ndoc_type: plan\nstatus: active\n---\nBody",
        )

        findings = check_plan.run_checks()
        unreg = [f for f in findings if f["code"] == "UNREGISTERED_PLANNING_ARTIFACT"]
        self.assertEqual(len(unreg), 1)
        self.assertEqual(unreg[0]["path"], "docs/specs/auth-next-step.md")

    def test_quoted_scalar_frontmatter_plan_is_reported(self):
        os.makedirs(os.path.join(self.repo_root, "docs/specs"), exist_ok=True)
        self.write_file(
            "docs/specs/quoted-plan.md",
            '---\ndoc_type: "plan"\nstatus: "active"\n---\nBody',
        )

        findings = check_plan.run_checks()
        unreg = [
            f for f in findings
            if f["code"] == "UNREGISTERED_PLANNING_ARTIFACT" and "quoted-plan" in f["path"]
        ]
        self.assertEqual(len(unreg), 1)

    def test_quoted_scalar_frontmatter_spec_is_ignored(self):
        os.makedirs(os.path.join(self.repo_root, "docs/specs"), exist_ok=True)
        self.write_file(
            "docs/specs/quoted-spec.md",
            '---\ndoc_type: "spec"\nstatus: "draft"\n---\nBody',
        )

        findings = check_plan.run_checks()
        unreg = [
            f for f in findings
            if f["code"] == "UNREGISTERED_PLANNING_ARTIFACT" and "quoted-spec" in f["path"]
        ]
        self.assertEqual(unreg, [])

    # ── control-file error tests ──────────────────────────────────────────────

    def test_invalid_control_file_errors(self):
        self.write_file("docs/tasks/index.json", "{invalid_json}")
        self.write_file(
            "docs/blueprints/unregistered.md", "---\nid: unreg\nstatus: active\n---\nBody"
        )

        findings = check_plan.run_checks()
        parse_errors = [f for f in findings if f["code"] == "CONTROL_FILE_PARSE_ERROR"]
        self.assertEqual(len(parse_errors), 1)
        self.assertEqual(parse_errors[0]["path"], "docs/tasks/index.json")

    def test_missing_control_file_errors(self):
        os.remove(os.path.join(self.repo_root, "docs/tasks/index.json"))

        findings = check_plan.run_checks()
        missing_errors = [f for f in findings if f["code"] == "CONTROL_FILE_MISSING"]
        self.assertEqual(len(missing_errors), 1)
        self.assertEqual(missing_errors[0]["path"], "docs/tasks/index.json")

    # ── backwards compatibility ───────────────────────────────────────────────

    def test_strict_flag_exits_non_zero_when_findings_exist(self):
        self.write_file("docs/blueprints/unregistered.md", "---\nstatus: active\n---\nBody")

        with patch("sys.stderr", new_callable=io.StringIO):
            exit_code_report = check_plan.main([])
        self.assertEqual(exit_code_report, 0)

        with patch("sys.stderr", new_callable=io.StringIO):
            exit_code_strict = check_plan.main(["--strict"])
        self.assertEqual(exit_code_strict, 1)


if __name__ == "__main__":
    unittest.main()
