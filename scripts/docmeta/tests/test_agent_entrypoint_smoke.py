"""
Tests for scripts/docmeta/agent_entrypoint_smoke.py.

All tests build a temporary fixture repo in an isolated repo_root; the real
repository files are never used as the sole test basis and are never written to.
"""
import hashlib
import os
import tempfile
import unittest
import unittest.mock

import scripts.docmeta.agent_entrypoint_smoke as smoke

CONSISTENT = {
    "README.md": (
        "# Demo\n\n"
        "Wahrheit folgt `repo.meta.yaml` und dem Agent Reading Protocol. "
        "`docs/index.md` ist Navigation, keine Wahrheitsschicht. "
        "`docs/_generated/*` ist Diagnose, nicht Ursprung.\n\n"
        "## Für Agents\n\n"
        "Verbindliche Leseordnung vor jedem Patch:\n\n"
        "1. `repo.meta.yaml`\n"
        "2. `AGENTS.md`\n"
        "3. `agent-policy.yaml`\n"
        "4. `docs/policies/agent-reading-protocol.md`\n"
        "5. `docs/index.md`\n\n"
        "## Task-Control\n\n"
        "Task-Index-Check-Modus (`generate_task_index.py --check`) und CI-Guard "
        "(`.github/workflows/task-index.yml`) sind vorhanden.\n\n"
        "Offen bleiben ein echter Schreibgenerator bzw. Bot-PRs und der "
        "Implementierungs-Mapping-Ausbau.\n"
    ),
    "AGENTS.md": (
        "---\nid: repo.agents\ntitle: AGENTS\nstatus: active\nsummary: test\n---\n\n"
        "# AGENTS\n\n"
        "All agents MUST follow the Agent Reading Protocol "
        "(docs/policies/agent-reading-protocol.md).\n\n"
        "Reading Order: `repo.meta.yaml` -> `AGENTS.md` -> `agent-policy.yaml` -> "
        "`docs/policies/agent-reading-protocol.md`.\n"
    ),
    "docs/index.md": (
        "---\nid: docs.index\ntitle: Index\nstatus: active\nsummary: test\n---\n\n"
        "# Index\n\n"
        "Dieser Index ist kanonische Navigation, keine eigenständige Wahrheitsschicht.\n"
    ),
    "docs/roadmap.md": (
        "---\nid: docs.roadmap\ntitle: Roadmap\nstatus: active\nsummary: test\n---\n\n"
        "# Roadmap\n\n"
        "| Thema | Sub-Roadmap | Statusbeleg |\n"
        "|---|---|---|\n"
        "| Dokumentationsstruktur & Task-Steuerung | [roadmap](blueprints/x.md) | "
        "Phase 2 vorhanden; Phase 4 Check-Modus + CI-Guard vorhanden; "
        "Schreibgenerator und Implementierungs-Mapping offen |\n"
    ),
    "docs/policies/agent-reading-protocol.md": (
        "---\nid: docs.policies.arp\ntitle: Agent Reading Protocol\nstatus: canonical\n"
        "summary: test\n---\n\n"
        "# Agent Reading Protocol\n\n"
        "## Lesereihenfolge\n\n"
        "1. `repo.meta.yaml`\n2. `AGENTS.md`\n3. `agent-policy.yaml`\n\n"
        "## _generated\n\n"
        "`docs/_generated/*` ist Diagnose, nicht Ursprung.\n"
    ),
    "docs/tasks/README.md": (
        "---\nid: tasks.readme\ntitle: Task-Control\nstatus: active\nsummary: test\n---\n\n"
        "# Task-Control\n\n"
        "`docs/tasks/` ist die Arbeitssteuerungs-Schicht, aber keine zweite "
        "Wahrheitsschicht.\n\n"
        "`generate_task_index.py --check` ist ein reiner Drift-Prüfmechanismus "
        "ohne Schreibzugriff.\n"
    ),
    "scripts/docmeta/generate_task_index.py": "# fixture\n",
    ".github/workflows/task-index.yml": "# fixture\n",
}


class TestAgentEntrypointSmoke(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self._write_all(CONSISTENT)

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, rel, content):
        full = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)

    def _write_all(self, files):
        for rel, content in files.items():
            self._write(rel, content)

    def _snapshot(self):
        snap = {}
        for dirpath, _dirs, files in os.walk(self.root):
            for name in files:
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, self.root)
                with open(full, "rb") as f:
                    snap[rel] = hashlib.sha256(f.read()).hexdigest()
        return snap

    # -------------------------------------------------------------------------
    # Passing case
    # -------------------------------------------------------------------------

    def test_consistent_minimal_fixture_passes(self):
        self.assertEqual(smoke.run_checks(self.root), [])

    # -------------------------------------------------------------------------
    # Drift cases
    # -------------------------------------------------------------------------

    def test_stale_readme_task_control_fails(self):
        self._write(
            "README.md",
            CONSISTENT["README.md"].replace(
                "Task-Index-Check-Modus (`generate_task_index.py --check`) und CI-Guard "
                "(`.github/workflows/task-index.yml`) sind vorhanden.",
                "Offen bleiben Folgephasen: Task-Index-Generator, CI-Guard und "
                "Implementierungs-Mapping.",
            ),
        )
        errors = smoke.run_checks(self.root)
        self.assertTrue(
            any("README.md: stale Task-Control statement" in e for e in errors), errors
        )

    def test_stale_readme_next_priority_fails(self):
        self._write(
            "README.md",
            CONSISTENT["README.md"]
            + "\nNächste Priorität: Task-Index-Generator und CI-Guard (TASK-CTL-003).\n",
        )
        errors = smoke.run_checks(self.root)
        self.assertTrue(
            any("README.md: stale Task-Control statement" in e for e in errors), errors
        )

    def test_present_both_without_openness_passes(self):
        # "Task-Index-Generator und CI-Guard sind vorhanden" is NOT stale.
        self._write(
            "README.md",
            CONSISTENT["README.md"]
            + "\nTask-Index-Generator und CI-Guard sind vorhanden und getestet.\n",
        )
        errors = smoke.run_checks(self.root)
        self.assertFalse(
            any("stale Task-Control statement" in e for e in errors), errors
        )

    def test_readme_stale_skipped_when_machinery_absent(self):
        os.remove(os.path.join(self.root, "scripts/docmeta/generate_task_index.py"))
        self._write(
            "README.md",
            CONSISTENT["README.md"].replace(
                "Task-Index-Check-Modus (`generate_task_index.py --check`) und CI-Guard "
                "(`.github/workflows/task-index.yml`) sind vorhanden.",
                "Offen bleiben Folgephasen: Task-Index-Generator, CI-Guard und "
                "Implementierungs-Mapping.",
            ),
        )
        errors = smoke.run_checks(self.root)
        self.assertFalse(
            any("stale Task-Control statement" in e for e in errors), errors
        )

    def test_stale_roadmap_status_proof_fails(self):
        self._write(
            "docs/roadmap.md",
            CONSISTENT["docs/roadmap.md"].replace(
                "Phase 2 vorhanden; Phase 4 Check-Modus + CI-Guard vorhanden; "
                "Schreibgenerator und Implementierungs-Mapping offen",
                "Statusbeleg ausstehend — noch kein Eintrag in "
                "`reports/optimierungsstatus.md`",
            ),
        )
        errors = smoke.run_checks(self.root)
        self.assertTrue(
            any("docs/roadmap.md: stale Task-Control status proof statement" in e for e in errors),
            errors,
        )

    def test_missing_index_navigation_marker_fails(self):
        self._write(
            "docs/index.md",
            "---\nid: docs.index\ntitle: Index\nstatus: active\nsummary: test\n---\n\n"
            "# Index\n\nEinfach nur Inhalt ohne Markierung.\n",
        )
        errors = smoke.run_checks(self.root)
        self.assertIn("docs/index.md: missing navigation-not-truth marker", errors)

    def test_missing_reading_order_entry_fails(self):
        self._write(
            "README.md",
            CONSISTENT["README.md"].replace("4. `docs/policies/agent-reading-protocol.md`\n", ""),
        )
        errors = smoke.run_checks(self.root)
        self.assertTrue(
            any("missing reading-order entry" in e for e in errors), errors
        )

    def test_tasks_readme_missing_check_description_fails(self):
        self._write(
            "docs/tasks/README.md",
            "---\nid: tasks.readme\ntitle: Task-Control\nstatus: active\nsummary: test\n---\n\n"
            "# Task-Control\n\n"
            "`docs/tasks/` ist die Arbeitssteuerungs-Schicht, aber keine zweite "
            "Wahrheitsschicht.\n",
        )
        errors = smoke.run_checks(self.root)
        self.assertTrue(
            any("write-free '--check' drift-mechanism" in e for e in errors), errors
        )

    def test_generated_without_diagnostic_marker_fails(self):
        self._write(
            "README.md",
            CONSISTENT["README.md"].replace(
                "`docs/_generated/*` ist Diagnose, nicht Ursprung.",
                "`docs/_generated/*` enthält die maßgeblichen Statusdaten.",
            ),
        )
        errors = smoke.run_checks(self.root)
        self.assertTrue(
            any("docs/_generated/* is mentioned without a diagnostic" in e for e in errors),
            errors,
        )

    def test_missing_file_reported(self):
        os.remove(os.path.join(self.root, "docs/index.md"))
        errors = smoke.run_checks(self.root)
        self.assertTrue(any("docs/index.md: file not found" in e for e in errors), errors)

    def test_readme_missing_entry_in_order_block_fails_even_if_token_exists_elsewhere(self):
        """Missing entry in order block should fail even if token exists elsewhere in README."""
        self._write(
            "README.md",
            CONSISTENT["README.md"].replace(
                "4. `docs/policies/agent-reading-protocol.md`\n",
                "",
            )
            + "\nQuick link: `docs/policies/agent-reading-protocol.md`\n",
        )
        errors = smoke.run_checks(self.root)
        self.assertTrue(
            any(
                "README.md: missing reading-order entry: docs/policies/agent-reading-protocol.md" in e
                for e in errors
            ),
            errors,
        )

    def test_readme_reading_order_sequence_fails(self):
        """Out-of-sequence reading order should fail."""
        self._write(
            "README.md",
            CONSISTENT["README.md"].replace(
                "2. `AGENTS.md`\n3. `agent-policy.yaml`\n",
                "2. `agent-policy.yaml`\n3. `AGENTS.md`\n",
            ),
        )
        errors = smoke.run_checks(self.root)
        self.assertTrue(
            any("README.md: reading order is out of sequence" in e for e in errors),
            errors,
        )

    # -------------------------------------------------------------------------
    # No-write guarantee
    # -------------------------------------------------------------------------

    def test_run_writes_no_files(self):
        before = self._snapshot()
        with unittest.mock.patch.object(smoke, "REPO_ROOT", self.root):
            rc = smoke.main([])
        after = self._snapshot()
        self.assertEqual(rc, 0)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
