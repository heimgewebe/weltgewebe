"""
Tests for scripts/docmeta/generate_task_index.py (task-control drift check).

All tests build temporary fixtures in an isolated repo_root; the real repository
files are never used as the sole test basis and are never written to.
"""
import hashlib
import json
import os
import tempfile
import unittest
from unittest import mock

import scripts.docmeta.generate_task_index as gen
from scripts.docmeta.generate_task_index import parse_board, run_check


def _task(**overrides):
    task = {
        "id": "OPT-API-001",
        "title": "Beispiel",
        "area": "api",
        "status": "partial",
        "priority": "medium",
        "effort": "M",
        "risk": "medium",
        "owner": "unknown",
        "evidence": [],
        "missing_evidence": [],
        "acceptance": [],
        "links": {"issues": [], "prs": [], "docs": []},
        "updated_at": "2026-05-28",
    }
    task.update(overrides)
    return task


def _index(tasks):
    return {
        "schema_version": "1.0.0",
        "generated_at": None,
        "curation": "manual_phase2_seed",
        "source_files": [],
        "tasks": tasks,
    }


def _status(items):
    return {
        "schema_version": "1.0.0",
        "source_markdown": "docs/reports/optimierungsstatus.md",
        "curation": "manual_phase2_seed",
        "generated_at": None,
        "items": items,
    }


def _board(active=(), blocker=(), candidates=(), deferred=(), done=()):
    def table(ids):
        rows = ["| ID | Info |", "|---|---|"]
        rows.extend(f"| {tid} | x |" for tid in ids)
        return "\n".join(rows)

    return (
        "\n".join(
            [
                "---",
                "id: tasks.board",
                "title: Board",
                "status: active",
                "summary: test fixture",
                "---",
                "",
                "# Board",
                "",
                "## Aktive Prioritäten",
                table(active),
                "",
                "## Blocker",
                table(blocker),
                "",
                "## Nächste PR-Kandidaten",
                table(candidates),
                "",
                "## Zurückgestellte / optionale Tasks",
                table(deferred),
                "",
                "## Erledigte Tasks",
                table(done),
                "",
            ]
        )
        + "\n"
    )


class TestGenerateTaskIndex(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self.index_path = os.path.join(self.root, "index.json")
        self.board_path = os.path.join(self.root, "board.md")
        self.status_path = os.path.join(self.root, "status.json")

    def tearDown(self):
        self._tmp.cleanup()

    def _touch(self, rel):
        full = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write("// fixture\n")

    def _write(self, index, board_text, status):
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False)
        with open(self.board_path, "w", encoding="utf-8") as f:
            f.write(board_text)
        with open(self.status_path, "w", encoding="utf-8") as f:
            json.dump(status, f, ensure_ascii=False)

    def _run(self):
        return run_check(self.index_path, self.board_path, self.status_path, self.root)

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
    # Passing cases
    # -------------------------------------------------------------------------

    def test_consistent_minimal_fixture_passes(self):
        self._touch("apps/api/x.rs")
        self._write(
            _index([_task(evidence=["apps/api/x.rs"])]),
            _board(active=["OPT-API-001"]),
            _status([{"id": "OPT-API-001", "status": "partial"}]),
        )
        self.assertEqual(self._run(), [])

    def test_wgx_evidence_path_is_existence_checked(self):
        self._write(
            _index(
                [
                    _task(
                        priority="medium",
                        evidence=[".wgx/generated-artifacts.yml"],
                    )
                ]
            ),
            _board(active=["OPT-API-001"]),
            _status([{"id": "OPT-API-001", "status": "partial"}]),
        )
        errors = self._run()
        self.assertTrue(
            any(".wgx/generated-artifacts.yml" in error for error in errors), errors
        )
        self._touch(".wgx/generated-artifacts.yml")
        self.assertEqual(self._run(), [])

    def test_nonexistent_evidence_path_explained_passes(self):
        self._write(
            _index(
                [
                    _task(
                        priority="medium",
                        evidence=["apps/api/missing.rs"],
                        missing_evidence=["apps/api/missing.rs noch nicht vorhanden"],
                    )
                ]
            ),
            _board(active=["OPT-API-001"]),
            _status([{"id": "OPT-API-001", "status": "partial"}]),
        )
        self.assertEqual(self._run(), [])

    def test_deferred_task_002_documented_passes(self):
        self._touch("apps/api/x.rs")
        self._write(
            _index(
                [
                    _task(evidence=["apps/api/x.rs"]),
                    _task(
                        id="TASK-CTL-002",
                        area="governance",
                        status="open",
                        priority="low",
                        acceptance=["Entscheidung dokumentiert"],
                        missing_evidence=["Issue Forms bewusst zurückgestellt"],
                    ),
                ]
            ),
            _board(active=["OPT-API-001"], deferred=["TASK-CTL-002"]),
            _status([{"id": "OPT-API-001", "status": "partial"}]),
        )
        self.assertEqual(self._run(), [])

    # -------------------------------------------------------------------------
    # Drift cases
    # -------------------------------------------------------------------------

    def test_board_task_missing_from_index_fails(self):
        self._touch("apps/api/x.rs")
        self._write(
            _index([_task(evidence=["apps/api/x.rs"])]),
            _board(active=["OPT-API-001", "OPT-API-099"]),
            _status([{"id": "OPT-API-001", "status": "partial"}]),
        )
        errors = self._run()
        self.assertTrue(
            any("OPT-API-099" in e and "index.json" in e for e in errors), errors
        )

    def test_index_task_missing_from_board_fails(self):
        self._touch("apps/api/x.rs")
        self._write(
            _index(
                [
                    _task(evidence=["apps/api/x.rs"]),
                    _task(id="OPT-CON-001", priority="medium"),
                ]
            ),
            _board(active=["OPT-API-001"]),
            _status([{"id": "OPT-API-001", "status": "partial"}]),
        )
        errors = self._run()
        self.assertTrue(
            any("OPT-CON-001" in e and "board.md" in e for e in errors), errors
        )

    def test_low_priority_task_not_in_board_passes(self):
        # low-priority done/open tasks need not appear in board.md
        self._write(
            _index([_task(id="OPT-API-001", priority="low", status="open", evidence=[])]),
            _board(),  # board is empty
            _status([]),
        )
        errors = self._run()
        self.assertFalse(any("board.md" in e for e in errors), errors)

    def test_done_without_evidence_fails(self):
        self._write(
            _index([_task(status="done", priority="medium", evidence=[])]),
            _board(done=["OPT-API-001"]),
            _status([{"id": "OPT-API-001", "status": "done"}]),
        )
        errors = self._run()
        self.assertTrue(any("done" in e and "evidence" in e for e in errors), errors)

    def test_high_priority_without_acceptance_fails(self):
        self._touch("apps/api/x.rs")
        self._write(
            _index([_task(priority="high", acceptance=[], evidence=["apps/api/x.rs"])]),
            _board(active=["OPT-API-001"]),
            _status([{"id": "OPT-API-001", "status": "partial"}]),
        )
        errors = self._run()
        self.assertTrue(
            any("high priority" in e and "acceptance" in e for e in errors), errors
        )

    def test_nonexistent_evidence_path_fails(self):
        self._write(
            _index([_task(priority="medium", evidence=["apps/api/missing.rs"])]),
            _board(active=["OPT-API-001"]),
            _status([{"id": "OPT-API-001", "status": "partial"}]),
        )
        errors = self._run()
        self.assertTrue(any("apps/api/missing.rs" in e for e in errors), errors)

    def test_generated_evidence_target_fails(self):
        self._write(
            _index([_task(priority="medium", evidence=["docs/_generated/impl-index.md"])]),
            _board(active=["OPT-API-001"]),
            _status([{"id": "OPT-API-001", "status": "partial"}]),
        )
        errors = self._run()
        self.assertTrue(any("_generated" in e for e in errors), errors)

    def test_status_mismatch_fails(self):
        self._touch("apps/api/x.rs")
        self._write(
            _index([_task(status="done", priority="medium", evidence=["apps/api/x.rs"])]),
            _board(done=["OPT-API-001"]),
            _status([{"id": "OPT-API-001", "status": "partial"}]),
        )
        errors = self._run()
        self.assertTrue(any("mismatch" in e for e in errors), errors)

    def test_task_003_open_not_candidate_fails(self):
        self._touch("apps/api/x.rs")
        self._write(
            _index(
                [
                    _task(evidence=["apps/api/x.rs"]),
                    _task(
                        id="TASK-CTL-003",
                        area="ci",
                        status="open",
                        priority="medium",
                        acceptance=["Deterministischer Check"],
                    ),
                ]
            ),
            # TASK-CTL-003 is visible but NOT a candidate/active item -> drift.
            _board(active=["OPT-API-001"], done=["TASK-CTL-003"]),
            _status([{"id": "OPT-API-001", "status": "partial"}]),
        )
        errors = self._run()
        self.assertTrue(
            any("TASK-CTL-003" in e and "open" in e for e in errors), errors
        )

    def test_deferred_task_002_as_candidate_fails(self):
        self._touch("apps/api/x.rs")
        self._write(
            _index(
                [
                    _task(evidence=["apps/api/x.rs"]),
                    _task(
                        id="TASK-CTL-002",
                        area="governance",
                        status="open",
                        priority="low",
                        acceptance=["Entscheidung dokumentiert"],
                        missing_evidence=["bewusst zurückgestellt"],
                    ),
                ]
            ),
            _board(active=["OPT-API-001"], candidates=["TASK-CTL-002"]),
            _status([{"id": "OPT-API-001", "status": "partial"}]),
        )
        errors = self._run()
        self.assertTrue(
            any("TASK-CTL-002" in e and "deferred" in e for e in errors), errors
        )

    # -------------------------------------------------------------------------
    # No-write guarantee and invocation
    # -------------------------------------------------------------------------

    def test_check_writes_no_files(self):
        self._touch("apps/api/x.rs")
        self._write(
            _index([_task(evidence=["apps/api/x.rs"])]),
            _board(active=["OPT-API-001"]),
            _status([{"id": "OPT-API-001", "status": "partial"}]),
        )
        before = self._snapshot()
        with mock.patch.multiple(
            gen,
            INDEX_PATH=self.index_path,
            BOARD_PATH=self.board_path,
            STATUS_PATH=self.status_path,
            REPO_ROOT=self.root,
        ):
            rc = gen.main(["--check"])
        after = self._snapshot()
        self.assertEqual(rc, 0)
        self.assertEqual(before, after)

    def test_main_without_check_refuses(self):
        self.assertEqual(gen.main([]), 2)

    # -------------------------------------------------------------------------
    # Parser
    # -------------------------------------------------------------------------

    def test_parse_board_sections(self):
        text = _board(
            active=["OPT-API-001"],
            candidates=["TASK-CTL-003"],
            deferred=["TASK-CTL-002"],
            done=["TASK-CTL-001", "OPT-MAP-001"],
        )
        sections = parse_board(text)
        self.assertEqual(sections["active"], {"OPT-API-001"})
        self.assertEqual(sections["candidates"], {"TASK-CTL-003"})
        self.assertEqual(sections["deferred"], {"TASK-CTL-002"})
        self.assertEqual(sections["done"], {"TASK-CTL-001", "OPT-MAP-001"})

    def test_parse_board_ignores_task_ids_outside_first_cell(self):
        # Only the ID column drives board visibility; task ids mentioned in
        # evidence / next-action columns must not count as board entries.
        text = "\n".join(
            [
                "# Board",
                "## Aktive Prioritäten",
                "| ID | Info |",
                "|---|---|",
                "| OPT-API-001 | Mentions TASK-CTL-003 only as related work |",
                "",
            ]
        )
        sections = parse_board(text)
        self.assertEqual(sections["active"], {"OPT-API-001"})
        self.assertNotIn("TASK-CTL-003", sections["active"])


if __name__ == "__main__":
    unittest.main()
