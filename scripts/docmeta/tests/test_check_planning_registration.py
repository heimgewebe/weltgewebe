import json
import os
import tempfile
import unittest
from io import StringIO
from unittest.mock import patch
import scripts.docmeta.check_planning_registration as check_plan

class TestCheckPlanningRegistration(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.repo_root = self.test_dir.name

        self.patcher = patch("scripts.docmeta.check_planning_registration.REPO_ROOT", self.repo_root)
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

    def test_active_blueprint_without_registration_is_reported(self):
        self.write_file("docs/blueprints/unregistered.md", "---\nid: unreg\nstatus: active\n---\nBody")

        findings = check_plan.run_checks()
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["code"], "UNREGISTERED_PLANNING_ARTIFACT")
        self.assertEqual(findings[0]["path"], "docs/blueprints/unregistered.md")

    def test_deprecated_or_superseded_blueprint_is_ignored(self):
        self.write_file("docs/blueprints/dep.md", "---\nstatus: deprecated\n---\nBody")
        self.write_file("docs/blueprints/sup.md", "---\nstatus: superseded\n---\nBody")

        findings = check_plan.run_checks()
        unregistered = [f for f in findings if f["code"] == "UNREGISTERED_PLANNING_ARTIFACT"]
        self.assertEqual(len(unregistered), 0)

    def test_generated_and_proofs_files_are_ignored(self):
        self.write_file("docs/_generated/reports/my-status-1.md", "---\nstatus: active\n---\nBody")
        self.write_file("docs/proofs/blueprint2.md", "---\nstatus: active\n---\nBody")

        findings = check_plan.run_checks()
        unregistered = [f for f in findings if f["code"] == "UNREGISTERED_PLANNING_ARTIFACT"]
        self.assertEqual(len(unregistered), 0)


    def test_active_blueprint_with_frontmatter_relation_passes(self):
        # Even without explicit registration in the control file, if the frontmatter has a relation
        # to a control file, it should pass.
        self.write_file("docs/blueprints/related.md", "---\nrelations:\n  - type: relates_to\n    target: docs/tasks/index.json\n---\nBody")

        findings = check_plan.run_checks()
        # Ensure it doesn't appear in the unregistered list
        unregistered = [f for f in findings if f["code"] == "UNREGISTERED_PLANNING_ARTIFACT"]
        self.assertEqual(len(unregistered), 0)

    def test_archived_and_deferred_blueprint_is_ignored(self):
        self.write_file("docs/blueprints/arch.md", "---\nstatus: archived\n---\nBody")
        self.write_file("docs/blueprints/def.md", "---\nstatus: deferred\n---\nBody")

        findings = check_plan.run_checks()
        unregistered = [f for f in findings if f["code"] == "UNREGISTERED_PLANNING_ARTIFACT"]
        self.assertEqual(len(unregistered), 0)

    def test_invalid_control_file_errors(self):
        # We start with valid control files in setUp, let's break one
        self.write_file("docs/tasks/index.json", "{invalid_json}")
        self.write_file("docs/blueprints/unregistered.md", "---\nid: unreg\nstatus: active\n---\nBody")

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


    def test_draft_spec_without_planning_doc_type_is_not_reported(self):
        self.write_file(
            "docs/specs/auth-api.md",
            "---\nstatus: draft\ndoc_type: spec\n---\nBody"
        )

        findings = check_plan.run_checks()
        unregistered = [
            f for f in findings
            if f["code"] == "UNREGISTERED_PLANNING_ARTIFACT"
        ]
        self.assertEqual(unregistered, [])

    def test_spec_with_plan_doc_type_is_reported_when_unregistered(self):
        self.write_file(
            "docs/specs/auth-next-step.md",
            "---\ndoc_type: plan\nstatus: active\n---\nBody"
        )

        findings = check_plan.run_checks()

        parse_errors = [f for f in findings if f["code"] == "UNREGISTERED_PLANNING_ARTIFACT"]
        self.assertEqual(len(parse_errors), 1)
        self.assertEqual(parse_errors[0]["code"], "UNREGISTERED_PLANNING_ARTIFACT")
        self.assertEqual(parse_errors[0]["path"], "docs/specs/auth-next-step.md")

    @patch("sys.stderr", new_callable=StringIO)
    def test_strict_exits_non_zero_when_findings_exist(self, mock_stderr):
        self.write_file("docs/blueprints/unregistered.md", "---\nstatus: active\n---\nBody")

        exit_code = check_plan.main([])
        self.assertEqual(exit_code, 0)

        exit_code = check_plan.main(["--strict"])
        self.assertEqual(exit_code, 1)

if __name__ == "__main__":
    unittest.main()
