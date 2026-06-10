"""
Tests for scripts/docmeta/validate_opt_arc_001_db_proof_matrix.py.

All tests build temporary fixtures in an isolated repo root; the real
repository files are never written to. The only test touching the real
repository is test_real_repo_matrix_validates, which is read-only.
"""
import contextlib
import copy
import io
import json
import os
import tempfile
import unittest
from unittest import mock

import scripts.docmeta.validate_opt_arc_001_db_proof_matrix as guard

NODE_WRITE_PROOF_ID = "db-domain-node-write-path-proof"
NODE_WRITE_TEST = "apps/api/tests/db_domain_node_write_path.rs"
NODE_WRITE_REPORT = "docs/reports/domain-node-write-path-proof.md"
NODE_WRITE_JOB_EVIDENCE = f"CI-Job: {NODE_WRITE_PROOF_ID}"

DEFAULT_BOARD_ARC_ROW = (
    "| OPT-ARC-001 | api | JSONL → PostgreSQL | partial | high | "
    "`apps/api/src/routes/nodes.rs`, "
    "`apps/api/tests/db_domain_node_write_path.rs`, "
    "`docs/reports/domain-node-write-path-proof.md`, "
    "`.github/workflows/api.yml` (`db-domain-node-write-path-proof`), "
    "`docs/reports/opt-arc-001-db-proof-matrix.json`, "
    "`scripts/docmeta/validate_opt_arc_001_db_proof_matrix.py` | "
    "PR-CI-Belege für alle fünf DB-Jobs stehen aus; kein Cutover; kein Dual-Write |"
)


def _valid_matrix():
    proofs = []
    for proof_id, spec in guard.EXPECTED_PROOFS.items():
        proofs.append(
            {
                "id": proof_id,
                "phase": spec["phase"],
                "claim": f"Fixture claim for {proof_id}.",
                "state": "prepared",
                "workflow": guard.WORKFLOW_PATH,
                "workflow_job": proof_id,
                "test": spec["test"],
                "report": spec["report"],
                "ci_evidence": None,
                "command": (
                    "cargo test --locked -p weltgewebe-api "
                    f"--test {spec['command_test_name']} "
                    "-- --include-ignored --test-threads=1"
                ),
            }
        )
    return {
        "schema": guard.EXPECTED_SCHEMA,
        "task": guard.TASK_ID,
        "status_source": guard.STATUS_MD_PATH,
        "overall_status": "partial",
        "cutover_status": "not_cutover",
        "default_domain_read_truth": "jsonl",
        "default_domain_write_truth": "jsonl",
        "ci_evidence_policy": "github_pr_ci_required",
        "non_goals": list(guard.REQUIRED_NON_GOALS),
        "proofs": proofs,
    }


def _workflow_text(drop_job_key=None, drop_test_command=None):
    lines = ["name: API CI", "jobs:"]
    for proof_id, spec in guard.EXPECTED_PROOFS.items():
        if proof_id != drop_job_key:
            lines.append(f"  {proof_id}:")
            lines.append("    runs-on: ubuntu-latest")
            lines.append("    steps:")
        if proof_id != drop_test_command:
            lines.append(
                "      - run: cargo test --locked -p weltgewebe-api "
                f"--test {spec['command_test_name']} -- --include-ignored --test-threads=1"
            )
    return "\n".join(lines) + "\n"


def _board_text(arc_row=DEFAULT_BOARD_ARC_ROW):
    # The done section deliberately carries legitimate CI PROVEN rows of other
    # tasks: the guard must stay scoped to OPT-ARC-001 rows only.
    return (
        "\n".join(
            [
                "# Board",
                "",
                "## Aktive Prioritäten",
                "",
                "| ID | Bereich | Titel | Status | Priorität | Evidenz | Nächste Aktion |",
                "|---|---|---|---|---|---|---|",
                arc_row,
                "",
                "## Erledigte Tasks",
                "",
                "| ID | Bereich | Titel | Evidenz |",
                "|---|---|---|---|",
                "| OPT-API-002 | api | Session-Persistenz PostgreSQL | "
                "`apps/api/src/auth/session_db.rs`, CI PROVEN, Commit `00a43a00` |",
                "| OPT-MAP-001 | map | Basemap Runtime Proof | "
                "CI-Job `basemap-range-delivery-proof` PROVEN, Commit `14feefd6` |",
                "",
            ]
        )
        + "\n"
    )


def _status_md_text(arc_status="partial", arc_extra=""):
    arc_row = (
        f"| OPT-ARC-001 | Architektur | JSONL → PostgreSQL | {arc_status} | code+test "
        "| hoch | hoch | hoch | "
        "`docs/reports/opt-arc-001-db-proof-matrix.json`, "
        "`scripts/docmeta/validate_opt_arc_001_db_proof_matrix.py` | "
        f"PR-CI-Belege ausstehend{arc_extra} | offen | 2026-06-10 |"
    )
    return (
        "\n".join(
            [
                "# Optimierungsstatus",
                "",
                "| id | bereich | maßnahme | status | befund | risiko | aufwand "
                "| priorität | nachweis | test | restlücke | stand |",
                "|---|---|---|---|---|---|---|---|---|---|---|---|",
                "| OPT-API-002 | API | Session-Persistenz | done | ci | hoch | mittel | hoch | "
                "`apps/api/src/auth/session_db.rs` | CI PROVEN (Run 26394569642) | keine | 2026-05-27 |",
                arc_row,
                "",
            ]
        )
        + "\n"
    )


def _index_data():
    evidence = (
        list(guard.REQUIRED_TEST_EVIDENCE)
        + list(guard.REQUIRED_REPORT_EVIDENCE)
        + list(guard.REQUIRED_CI_JOB_EVIDENCE)
        + ["apps/api/src/routes/nodes.rs", guard.MATRIX_PATH, guard.VALIDATOR_PATH]
    )
    return {
        "tasks": [
            {
                "id": guard.TASK_ID,
                "title": "JSONL-Datenquelle zu PostgreSQL migrieren",
                "status": "partial",
                "evidence": evidence,
                "missing_evidence": [
                    "Grüner PR-CI-Laufbeleg für alle fünf DB-Jobs ausstehend",
                ],
                "links": {"issues": [], "prs": [], "docs": [guard.MATRIX_PATH]},
            }
        ]
    }


def _status_json_data():
    return {
        "items": [
            {
                "id": guard.TASK_ID,
                "title": "JSONL → PostgreSQL",
                "status": "partial",
                "evidence": [guard.MATRIX_PATH, guard.VALIDATOR_PATH],
                "missing_evidence": [
                    "Grüner PR-CI-Laufbeleg für alle fünf DB-Jobs ausstehend",
                ],
            }
        ]
    }


class ValidateOptArc001DbProofMatrixTests(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = tmp.name
        self._build_valid_repo()

    def _path(self, rel):
        return os.path.join(self.root, rel)

    def _write(self, rel, text):
        full = self._path(rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(text)

    def _write_json(self, rel, data):
        self._write(rel, json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    def _build_valid_repo(self):
        for spec in guard.EXPECTED_PROOFS.values():
            self._write(spec["test"], "// fixture test file\n")
            if spec["report"] is not None:
                self._write(spec["report"], "# fixture proof report\n")
        self._write(guard.WORKFLOW_PATH, _workflow_text())
        self._write_json(guard.MATRIX_PATH, _valid_matrix())
        self._write(guard.BOARD_PATH, _board_text())
        self._write(guard.STATUS_MD_PATH, _status_md_text())
        self._write_json(guard.TASK_INDEX_PATH, _index_data())
        self._write_json(guard.STATUS_JSON_PATH, _status_json_data())

    def assert_error_containing(self, fragment):
        errors = guard.validate(self.root)
        self.assertTrue(
            any(fragment in e for e in errors),
            f"expected an error containing {fragment!r}, got: {errors}",
        )
        return errors

    def _run_main(self):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(guard, "REPO_ROOT", self.root):
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = guard.main([])
        return code, out.getvalue(), err.getvalue()

    # --- baseline -----------------------------------------------------------

    def test_real_repo_matrix_validates(self):
        self.assertEqual(guard.validate(guard.REPO_ROOT), [])

    def test_fixture_repo_validates(self):
        self.assertEqual(guard.validate(self.root), [])

    # --- matrix -------------------------------------------------------------

    def test_missing_matrix_file_fails(self):
        os.remove(self._path(guard.MATRIX_PATH))
        self.assert_error_containing("matrix file does not exist")

    def test_missing_expected_proof_id_fails(self):
        matrix = _valid_matrix()
        matrix["proofs"] = [p for p in matrix["proofs"] if p["id"] != NODE_WRITE_PROOF_ID]
        self._write_json(guard.MATRIX_PATH, matrix)
        self.assert_error_containing(f"missing expected proof id '{NODE_WRITE_PROOF_ID}'")

    def test_extra_proof_id_fails(self):
        matrix = _valid_matrix()
        extra = copy.deepcopy(matrix["proofs"][0])
        extra["id"] = "db-domain-edge-write-path-proof"
        matrix["proofs"].append(extra)
        self._write_json(guard.MATRIX_PATH, matrix)
        self.assert_error_containing("unexpected proof id 'db-domain-edge-write-path-proof'")

    def test_duplicate_proof_id_fails(self):
        matrix = _valid_matrix()
        matrix["proofs"].append(copy.deepcopy(matrix["proofs"][0]))
        self._write_json(guard.MATRIX_PATH, matrix)
        self.assert_error_containing("duplicate proof id")

    def test_ci_proven_without_ci_evidence_fails(self):
        matrix = _valid_matrix()
        matrix["proofs"][0]["state"] = "ci_proven"
        self._write_json(guard.MATRIX_PATH, matrix)
        errors = self.assert_error_containing("requires a ci_evidence object")
        self.assertTrue(any("state must be 'prepared'" in e for e in errors), errors)

    def test_prepared_with_ci_evidence_fails(self):
        matrix = _valid_matrix()
        matrix["proofs"][0]["ci_evidence"] = {
            "run_url": "https://github.com/heimgewebe/weltgewebe/actions/runs/1",
            "run_id": 1,
            "commit": "deadbeef",
            "job": NODE_WRITE_PROOF_ID,
        }
        self._write_json(guard.MATRIX_PATH, matrix)
        self.assert_error_containing("ci_evidence must be null")

    def test_matrix_cutover_status_cutover_fails(self):
        matrix = _valid_matrix()
        matrix["cutover_status"] = "cutover"
        self._write_json(guard.MATRIX_PATH, matrix)
        self.assert_error_containing("cutover_status must be 'not_cutover'")

    def test_matrix_default_truth_postgres_fails(self):
        matrix = _valid_matrix()
        matrix["default_domain_read_truth"] = "postgres"
        matrix["default_domain_write_truth"] = "postgres"
        self._write_json(guard.MATRIX_PATH, matrix)
        errors = self.assert_error_containing("default_domain_read_truth must be 'jsonl'")
        self.assertTrue(
            any("default_domain_write_truth must be 'jsonl'" in e for e in errors), errors
        )

    def test_invalid_matrix_json_raises_broken_input(self):
        self._write(guard.MATRIX_PATH, "{ this is not json\n")
        with self.assertRaises(guard.BrokenInputError):
            guard.validate(self.root)

    # --- referenced files ---------------------------------------------------

    def test_missing_test_file_fails(self):
        os.remove(self._path(NODE_WRITE_TEST))
        self.assert_error_containing(f"test file '{NODE_WRITE_TEST}' does not exist")

    def test_missing_report_file_fails(self):
        os.remove(self._path(NODE_WRITE_REPORT))
        self.assert_error_containing(f"report file '{NODE_WRITE_REPORT}' does not exist")

    # --- workflow -----------------------------------------------------------

    def test_missing_workflow_job_fails(self):
        self._write(guard.WORKFLOW_PATH, _workflow_text(drop_job_key=NODE_WRITE_PROOF_ID))
        self.assert_error_containing(f"workflow job '{NODE_WRITE_PROOF_ID}' not found")

    def test_missing_workflow_test_command_fails(self):
        self._write(guard.WORKFLOW_PATH, _workflow_text(drop_test_command=NODE_WRITE_PROOF_ID))
        self.assert_error_containing("'--test db_domain_node_write_path' not found")

    # --- status wording, scoped to OPT-ARC-001 ------------------------------

    def test_opt_arc_ci_proven_wording_fails_when_prepared(self):
        self._write(guard.STATUS_MD_PATH, _status_md_text(arc_extra="; CI PROVEN"))
        self.assert_error_containing("must not contain 'CI PROVEN'")

    def test_other_proven_rows_do_not_fail(self):
        # The default fixture carries CI PROVEN rows for OPT-API-002 and a
        # PROVEN row for OPT-MAP-001 in board.md and optimierungsstatus.md.
        # Only OPT-ARC-001 rows are guarded, so validation must stay clean.
        self.assertIn("CI PROVEN", _board_text())
        self.assertIn("CI PROVEN", _status_md_text())
        self.assertEqual(guard.validate(self.root), [])

    # --- task index ---------------------------------------------------------

    def _write_index_without_evidence(self, entry):
        index = _index_data()
        index["tasks"][0]["evidence"].remove(entry)
        self._write_json(guard.TASK_INDEX_PATH, index)

    def test_task_index_missing_node_write_test_evidence_fails(self):
        self._write_index_without_evidence(NODE_WRITE_TEST)
        self.assert_error_containing(f"evidence must contain '{NODE_WRITE_TEST}'")

    def test_task_index_missing_node_write_report_evidence_fails(self):
        self._write_index_without_evidence(NODE_WRITE_REPORT)
        self.assert_error_containing(f"evidence must contain '{NODE_WRITE_REPORT}'")

    def test_task_index_missing_node_write_job_evidence_fails(self):
        self._write_index_without_evidence(NODE_WRITE_JOB_EVIDENCE)
        self.assert_error_containing(f"evidence must contain '{NODE_WRITE_JOB_EVIDENCE}'")

    # --- board --------------------------------------------------------------

    def test_board_missing_node_write_evidence_fails(self):
        row = DEFAULT_BOARD_ARC_ROW.replace(
            "`apps/api/tests/db_domain_node_write_path.rs`, ", ""
        )
        self.assertNotIn(NODE_WRITE_TEST, row)
        self._write(guard.BOARD_PATH, _board_text(arc_row=row))
        self.assert_error_containing(f"must reference '{NODE_WRITE_TEST}'")

    # --- status twins -------------------------------------------------------

    def test_status_json_done_fails(self):
        status = _status_json_data()
        status["items"][0]["status"] = "done"
        self._write_json(guard.STATUS_JSON_PATH, status)
        self.assert_error_containing(f"{guard.STATUS_JSON_PATH}: OPT-ARC-001 status must be 'partial'")

    def test_status_md_done_fails(self):
        self._write(guard.STATUS_MD_PATH, _status_md_text(arc_status="done"))
        self.assert_error_containing("must keep status cell 'partial'")

    # --- CLI ----------------------------------------------------------------

    def test_main_exit_codes(self):
        code, out, err = self._run_main()
        self.assertEqual(code, 0)
        self.assertIn("validation passed", out)
        self.assertEqual(err, "")

        matrix = _valid_matrix()
        matrix["overall_status"] = "done"
        self._write_json(guard.MATRIX_PATH, matrix)
        code, out, err = self._run_main()
        self.assertEqual(code, 1)
        self.assertIn("validation failed", err)

        self._write(guard.MATRIX_PATH, "{ this is not json\n")
        code, out, err = self._run_main()
        self.assertEqual(code, 2)
        self.assertIn("broken input", err)


if __name__ == "__main__":
    unittest.main()
