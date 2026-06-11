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
FIRST_PROOF_ID = "db-domain-schema-migrations-proof"

UPDATED_AT = "2026-06-10"

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

DEFAULT_BOARD_BLOCKER_ROW = (
    "| OPT-ARC-001 | PR-CI-Laufbeleg für alle DB-Jobs ausstehend | "
    "Grünen CI-Lauf der DB-Jobs belegen | "
    "JSONL bleibt Default-Lesequelle und Write-Truth bis vollständiger Cutover |"
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


def _workflow_text(drop_job_key=None, drop_test_command=None, decorated=False):
    lines = ["name: API CI", "jobs:"]
    for proof_id, spec in guard.EXPECTED_PROOFS.items():
        if proof_id != drop_job_key:
            lines.append(f"  {proof_id}:")
            if decorated:
                lines.append("    # proof job fixture comment")
                lines.append("    if: github.event_name == 'pull_request'")
                lines.append("    continue-on-error: false")
            lines.append("    runs-on: ubuntu-latest")
            lines.append("    steps:")
            if decorated:
                lines.append("      # step-level fixture comment")
        if proof_id != drop_test_command:
            lines.append(
                "      - run: cargo test --locked -p weltgewebe-api "
                f"--test {spec['command_test_name']} -- --include-ignored --test-threads=1"
            )
    return "\n".join(lines) + "\n"


def _workflow_text_cross_job(proof_id_to_steal, steal_to_job_id):
    """Workflow where proof_id_to_steal's --test command appears in steal_to_job_id, not its own job."""
    stolen_spec = guard.EXPECTED_PROOFS[proof_id_to_steal]
    lines = ["name: API CI", "jobs:"]
    for proof_id, spec in guard.EXPECTED_PROOFS.items():
        lines.append(f"  {proof_id}:")
        lines.append("    runs-on: ubuntu-latest")
        lines.append("    steps:")
        if proof_id == steal_to_job_id:
            # Add the stolen test command into this job's block
            lines.append(
                f"      - run: cargo test --locked -p weltgewebe-api "
                f"--test {stolen_spec['command_test_name']} -- --include-ignored --test-threads=1"
            )
        if proof_id != proof_id_to_steal:
            lines.append(
                "      - run: cargo test --locked -p weltgewebe-api "
                f"--test {spec['command_test_name']} -- --include-ignored --test-threads=1"
            )
        # proof_id_to_steal gets no test command in its own block
    return "\n".join(lines) + "\n"


def _workflow_text_toplevel_comment_after_target(target_id):
    """Target job lacks its proof command; a top-level (indent 0) comment right
    after it carries the full command. A correct sibling job follows. A naive
    block extractor would attribute the comment to the target job."""
    spec = guard.EXPECTED_PROOFS[target_id]
    lines = ["name: API CI", "jobs:"]
    # Target job first, WITHOUT its proof test command.
    lines.append(f"  {target_id}:")
    lines.append("    runs-on: ubuntu-latest")
    lines.append("    steps:")
    lines.append('      - run: echo "placeholder, no proof test here"')
    # Top-level comment (indent 0) carrying the full required command.
    lines.append(
        "# - run: cargo test --locked -p weltgewebe-api "
        f"--test {spec['command_test_name']} -- --include-ignored --test-threads=1"
    )
    # All other jobs, correct, so only the target is in question.
    for proof_id, s in guard.EXPECTED_PROOFS.items():
        if proof_id == target_id:
            continue
        lines.append(f"  {proof_id}:")
        lines.append("    runs-on: ubuntu-latest")
        lines.append("    steps:")
        lines.append(
            "      - run: cargo test --locked -p weltgewebe-api "
            f"--test {s['command_test_name']} -- --include-ignored --test-threads=1"
        )
    return "\n".join(lines) + "\n"


def _workflow_text_job_level_comment_with_command(target_id):
    """Target job has the full cargo test only as an indented YAML comment; real run is echo."""
    spec = guard.EXPECTED_PROOFS[target_id]
    lines = ["name: API CI", "jobs:"]
    lines.append(f"  {target_id}:")
    lines.append("    runs-on: ubuntu-latest")
    lines.append("    steps:")
    lines.append(
        f"      # cargo test --locked -p weltgewebe-api "
        f"--test {spec['command_test_name']} -- --include-ignored --test-threads=1"
    )
    lines.append('      - run: echo "no proof test"')
    for proof_id, s in guard.EXPECTED_PROOFS.items():
        if proof_id == target_id:
            continue
        lines.append(f"  {proof_id}:")
        lines.append("    runs-on: ubuntu-latest")
        lines.append("    steps:")
        lines.append(
            "      - run: cargo test --locked -p weltgewebe-api "
            f"--test {s['command_test_name']} -- --include-ignored --test-threads=1"
        )
    return "\n".join(lines) + "\n"


def _workflow_text_split_flags(target_id):
    """Target job: correct --test in one step; --include-ignored and --test-threads=1 only in another echo step."""
    spec = guard.EXPECTED_PROOFS[target_id]
    lines = ["name: API CI", "jobs:"]
    lines.append(f"  {target_id}:")
    lines.append("    runs-on: ubuntu-latest")
    lines.append("    steps:")
    lines.append(
        f"      - run: cargo test --locked -p weltgewebe-api "
        f"--test {spec['command_test_name']}"
    )
    lines.append('      - run: echo "--include-ignored --test-threads=1"')
    for proof_id, s in guard.EXPECTED_PROOFS.items():
        if proof_id == target_id:
            continue
        lines.append(f"  {proof_id}:")
        lines.append("    runs-on: ubuntu-latest")
        lines.append("    steps:")
        lines.append(
            "      - run: cargo test --locked -p weltgewebe-api "
            f"--test {s['command_test_name']} -- --include-ignored --test-threads=1"
        )
    return "\n".join(lines) + "\n"


def _workflow_text_run_block_comment_command(target_id):
    """Target job: full cargo test only as a shell comment inside run: |; real cmd is echo."""
    spec = guard.EXPECTED_PROOFS[target_id]
    lines = ["name: API CI", "jobs:"]
    lines.append(f"  {target_id}:")
    lines.append("    runs-on: ubuntu-latest")
    lines.append("    steps:")
    lines.append("      - run: |")
    lines.append(
        f"          # cargo test --locked -p weltgewebe-api "
        f"--test {spec['command_test_name']} -- --include-ignored --test-threads=1"
    )
    lines.append('          echo "no proof test"')
    for proof_id, s in guard.EXPECTED_PROOFS.items():
        if proof_id == target_id:
            continue
        lines.append(f"  {proof_id}:")
        lines.append("    runs-on: ubuntu-latest")
        lines.append("    steps:")
        lines.append(
            "      - run: cargo test --locked -p weltgewebe-api "
            f"--test {s['command_test_name']} -- --include-ignored --test-threads=1"
        )
    return "\n".join(lines) + "\n"


def _workflow_text_multiline_run_block(target_id):
    """Full workflow; target job uses a multiline run: |- block with backslash continuations."""
    spec = guard.EXPECTED_PROOFS[target_id]
    test_name = spec["command_test_name"]
    lines = ["name: API CI", "jobs:"]
    for proof_id, s in guard.EXPECTED_PROOFS.items():
        lines.append(f"  {proof_id}:")
        lines.append("    runs-on: ubuntu-latest")
        lines.append("    steps:")
        if proof_id == target_id:
            lines.append("      - run: |-")
            lines.append(
                '          DATABASE_URL="postgres://welt:gewebe@localhost:5432/weltgewebe" \\'
            )
            lines.append("            cargo test --locked -p weltgewebe-api \\")
            lines.append(f"              --test {test_name} \\")
            lines.append("              -- --include-ignored --test-threads=1")
        else:
            lines.append(
                "      - run: cargo test --locked -p weltgewebe-api "
                f"--test {s['command_test_name']} -- --include-ignored --test-threads=1"
            )
    return "\n".join(lines) + "\n"


def _workflow_text_folded_run_block(target_id):
    """Full workflow; target job uses a folded run: >- block."""
    spec = guard.EXPECTED_PROOFS[target_id]
    test_name = spec["command_test_name"]
    lines = ["name: API CI", "jobs:"]
    for proof_id, s in guard.EXPECTED_PROOFS.items():
        lines.append(f"  {proof_id}:")
        lines.append("    runs-on: ubuntu-latest")
        lines.append("    steps:")
        if proof_id == target_id:
            lines.append("      - run: >-")
            lines.append(f"          cargo test --locked -p weltgewebe-api")
            lines.append(f"          --test {test_name}")
            lines.append("          -- --include-ignored --test-threads=1")
        else:
            lines.append(
                "      - run: cargo test --locked -p weltgewebe-api "
                f"--test {s['command_test_name']} -- --include-ignored --test-threads=1"
            )
    return "\n".join(lines) + "\n"


def _board_text(arc_row=DEFAULT_BOARD_ARC_ROW, blocker_row=DEFAULT_BOARD_BLOCKER_ROW):
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
                "## Blocker",
                "",
                "| ID | Blocker | Fehlt | Folge |",
                "|---|---|---|---|",
                blocker_row,
                "",
                "## Erledigte Tasks",
                "",
                "| ID | Bereich | Titel | Evidenz |",
                "|---|---|---|---|",
                (
                    "| OPT-API-002 | api | Session-Persistenz PostgreSQL | "
                    + "`apps/api/src/auth/session_db.rs`, CI PROVEN, Commit `00a43a00` |"
                ),
                (
                    "| OPT-MAP-001 | map | Basemap Runtime Proof | "
                    + "CI-Job `basemap-range-delivery-proof` PROVEN, Commit `14feefd6` |"
                ),
                "",
            ]
        )
        + "\n"
    )


def _status_md_text(arc_status="partial", arc_extra="", arc_date=UPDATED_AT, extra_arc_row=None):
    arc_row = (
        f"| OPT-ARC-001 | Architektur | JSONL → PostgreSQL | {arc_status} | code+test "
        "| hoch | hoch | hoch | "
        "`docs/reports/opt-arc-001-db-proof-matrix.json`, "
        "`scripts/docmeta/validate_opt_arc_001_db_proof_matrix.py` | "
        f"PR-CI-Belege ausstehend{arc_extra} | offen | {arc_date} |"
    )
    lines = [
        "# Optimierungsstatus",
        "",
        (
            "| id | bereich | maßnahme | status | befund | risiko | aufwand "
            + "| priorität | nachweis | test | restlücke | stand |"
        ),
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
        (
            "| OPT-API-002 | API | Session-Persistenz | done | ci | hoch | mittel | hoch | "
            + "`apps/api/src/auth/session_db.rs` | CI PROVEN (Run 26394569642) | keine | 2026-05-27 |"
        ),
        arc_row,
    ]
    if extra_arc_row is not None:
        lines.append(extra_arc_row)
    lines.append("")
    return "\n".join(lines) + "\n"


def _index_data():
    evidence = list(guard.ALL_REQUIRED_EVIDENCE)
    return {
        "tasks": [
            {
                "id": guard.TASK_ID,
                "title": "JSONL-Datenquelle zu PostgreSQL migrieren",
                "status": "partial",
                "updated_at": UPDATED_AT,
                "evidence": evidence,
                "missing_evidence": [
                    "Grüner PR-CI-Laufbeleg für alle fünf DB-Jobs ausstehend",
                ],
                "links": {"issues": [], "prs": [], "docs": [guard.MATRIX_PATH]},
            }
        ]
    }


def _status_json_data():
    evidence = list(guard.ALL_REQUIRED_EVIDENCE)
    return {
        "items": [
            {
                "id": guard.TASK_ID,
                "title": "JSONL → PostgreSQL",
                "status": "partial",
                "evidence": evidence,
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

    def assert_no_errors(self):
        errors = guard.validate(self.root)
        self.assertEqual(errors, [], f"expected no errors, got: {errors}")

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
        self.assert_no_errors()

    # --- matrix: field set --------------------------------------------------

    def test_matrix_unexpected_top_level_field_fails(self):
        matrix = _valid_matrix()
        matrix["extra_field"] = "surprise"
        self._write_json(guard.MATRIX_PATH, matrix)
        self.assert_error_containing("unexpected top-level field 'extra_field'")

    def test_matrix_missing_top_level_field_fails(self):
        matrix = _valid_matrix()
        del matrix["status_source"]
        self._write_json(guard.MATRIX_PATH, matrix)
        self.assert_error_containing("missing required top-level field 'status_source'")

    def test_matrix_wrong_status_source_fails(self):
        matrix = _valid_matrix()
        matrix["status_source"] = "docs/reports/other.md"
        self._write_json(guard.MATRIX_PATH, matrix)
        self.assert_error_containing("status_source must be")

    def test_matrix_unexpected_proof_field_fails(self):
        matrix = _valid_matrix()
        matrix["proofs"][0]["extra"] = "x"
        self._write_json(guard.MATRIX_PATH, matrix)
        self.assert_error_containing("unexpected field 'extra'")

    def test_matrix_missing_proof_field_fails(self):
        matrix = _valid_matrix()
        del matrix["proofs"][0]["claim"]
        self._write_json(guard.MATRIX_PATH, matrix)
        self.assert_error_containing("missing required field 'claim'")

    def test_matrix_empty_claim_fails(self):
        matrix = _valid_matrix()
        matrix["proofs"][0]["claim"] = "   "
        self._write_json(guard.MATRIX_PATH, matrix)
        self.assert_error_containing("claim must be a non-empty string")

    def test_matrix_wrong_proof_order_fails(self):
        matrix = _valid_matrix()
        matrix["proofs"] = list(reversed(matrix["proofs"]))
        self._write_json(guard.MATRIX_PATH, matrix)
        self.assert_error_containing("canonical order")

    # --- matrix: existing checks -------------------------------------------

    def test_missing_matrix_raises_broken_input(self):
        os.remove(self._path(guard.MATRIX_PATH))
        with self.assertRaises(guard.BrokenInputError):
            guard.validate(self.root)

    def test_missing_matrix_main_exit_2(self):
        os.remove(self._path(guard.MATRIX_PATH))
        code, _out, err = self._run_main()
        self.assertEqual(code, 2)
        self.assertIn("broken input", err)

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

    # --- ci_evidence strict typing (direct helper tests) --------------------

    @staticmethod
    def _ci_evidence(**overrides):
        obj = {
            "run_url": "https://github.com/heimgewebe/weltgewebe/actions/runs/1",
            "run_id": 1,
            "commit": "deadbeef",
            "job": NODE_WRITE_PROOF_ID,
        }
        obj.update(overrides)
        return obj

    def test_ci_evidence_object_valid(self):
        self.assertTrue(guard._check_ci_evidence_object(self._ci_evidence()))

    def test_ci_evidence_object_not_a_dict(self):
        self.assertFalse(guard._check_ci_evidence_object("nope"))

    def test_ci_evidence_run_id_as_string_invalid(self):
        self.assertFalse(guard._check_ci_evidence_object(self._ci_evidence(run_id="1")))

    def test_ci_evidence_commit_as_int_invalid(self):
        self.assertFalse(guard._check_ci_evidence_object(self._ci_evidence(commit=123)))

    def test_ci_evidence_run_id_as_bool_invalid(self):
        self.assertFalse(guard._check_ci_evidence_object(self._ci_evidence(run_id=True)))

    def test_ci_evidence_empty_string_field_invalid(self):
        self.assertFalse(guard._check_ci_evidence_object(self._ci_evidence(commit="   ")))

    def test_ci_evidence_run_url_as_int_invalid(self):
        self.assertFalse(guard._check_ci_evidence_object(self._ci_evidence(run_url=42)))

    def test_ci_evidence_extra_key_tolerated(self):
        # Extra keys remain allowed (prior policy preserved).
        self.assertTrue(guard._check_ci_evidence_object(self._ci_evidence(branch="main")))

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

    # --- command check (regex) ----------------------------------------------

    def test_command_equals_form_passes(self):
        matrix = _valid_matrix()
        spec = guard.EXPECTED_PROOFS[FIRST_PROOF_ID]
        matrix["proofs"][0]["command"] = (
            f"cargo test --locked -p weltgewebe-api "
            f"--test={spec['command_test_name']} "
            "-- --include-ignored --test-threads=1"
        )
        self._write_json(guard.MATRIX_PATH, matrix)
        self.assert_no_errors()

    def test_command_wrong_test_name_fails(self):
        matrix = _valid_matrix()
        matrix["proofs"][0]["command"] = (
            "cargo test --locked -p weltgewebe-api "
            "--test db_domain_backfill "
            "-- --include-ignored --test-threads=1"
        )
        self._write_json(guard.MATRIX_PATH, matrix)
        spec = guard.EXPECTED_PROOFS[FIRST_PROOF_ID]
        self.assert_error_containing(f"--test {spec['command_test_name']}")

    def test_command_missing_include_ignored_fails(self):
        matrix = _valid_matrix()
        spec = guard.EXPECTED_PROOFS[FIRST_PROOF_ID]
        matrix["proofs"][0]["command"] = (
            f"cargo test --locked -p weltgewebe-api "
            f"--test {spec['command_test_name']} "
            "-- --test-threads=1"
        )
        self._write_json(guard.MATRIX_PATH, matrix)
        self.assert_error_containing("--include-ignored")

    def test_command_missing_test_threads_fails(self):
        matrix = _valid_matrix()
        spec = guard.EXPECTED_PROOFS[FIRST_PROOF_ID]
        matrix["proofs"][0]["command"] = (
            f"cargo test --locked -p weltgewebe-api "
            f"--test {spec['command_test_name']} "
            "-- --include-ignored"
        )
        self._write_json(guard.MATRIX_PATH, matrix)
        self.assert_error_containing("--test-threads=1")

    # --- workflow (job-scoped) ----------------------------------------------

    def test_missing_workflow_job_fails(self):
        self._write(guard.WORKFLOW_PATH, _workflow_text(drop_job_key=NODE_WRITE_PROOF_ID))
        self.assert_error_containing(f"workflow job '{NODE_WRITE_PROOF_ID}' not found")

    def test_missing_workflow_test_command_fails(self):
        self._write(guard.WORKFLOW_PATH, _workflow_text(drop_test_command=NODE_WRITE_PROOF_ID))
        self.assert_error_containing(
            f"not found in any run command of job '{NODE_WRITE_PROOF_ID}'"
        )

    def test_workflow_cross_job_command_not_accepted(self):
        # The node-write-path --test command appears in the backfill job's block,
        # not in the node-write-path job's block. Global search would pass; scoped fails.
        wf = _workflow_text_cross_job(NODE_WRITE_PROOF_ID, "db-domain-backfill-proof")
        self._write(guard.WORKFLOW_PATH, wf)
        self.assert_error_containing(
            f"not found in any run command of job '{NODE_WRITE_PROOF_ID}'"
        )

    def test_workflow_job_missing_include_ignored_fails(self):
        wf = _workflow_text().replace(
            "--test db_domain_node_write_path -- --include-ignored --test-threads=1",
            "--test db_domain_node_write_path -- --test-threads=1",
        )
        self.assertIn("--test db_domain_node_write_path -- --test-threads=1", wf)
        self._write(guard.WORKFLOW_PATH, wf)
        self.assert_error_containing(
            f"not found in any run command of job '{NODE_WRITE_PROOF_ID}'"
        )

    def test_workflow_job_missing_test_threads_fails(self):
        wf = _workflow_text().replace(
            "--test db_domain_node_write_path -- --include-ignored --test-threads=1",
            "--test db_domain_node_write_path -- --include-ignored",
        )
        self._write(guard.WORKFLOW_PATH, wf)
        self.assert_error_containing(
            f"not found in any run command of job '{NODE_WRITE_PROOF_ID}'"
        )

    def test_workflow_job_with_comments_and_keys_passes(self):
        # Comments, if: and continue-on-error: at correct indentation must not
        # terminate the job block.
        self._write(guard.WORKFLOW_PATH, _workflow_text(decorated=True))
        self.assert_no_errors()

    def test_workflow_toplevel_comment_does_not_rescue_target_job(self):
        # The target job has no proof command; a top-level comment directly
        # after it carries the full command. The comment must not be attributed
        # to the job, so the job-scoped search must fail.
        wf = _workflow_text_toplevel_comment_after_target(NODE_WRITE_PROOF_ID)
        self._write(guard.WORKFLOW_PATH, wf)
        self.assert_error_containing(
            f"not found in any run command of job '{NODE_WRITE_PROOF_ID}'"
        )

    def test_workflow_indented_comment_command_not_accepted(self):
        # Target job: full cargo test only as an indented YAML comment (# ...).
        # Actual run: step is echo. Comment must not count as proof.
        wf = _workflow_text_job_level_comment_with_command(NODE_WRITE_PROOF_ID)
        self._write(guard.WORKFLOW_PATH, wf)
        self.assert_error_containing(
            f"not found in any run command of job '{NODE_WRITE_PROOF_ID}'"
        )

    def test_workflow_split_flags_across_steps_not_accepted(self):
        # Target job: cargo test --test <name> in one step; --include-ignored and
        # --test-threads=1 only in a separate echo step. Split flags must not pass.
        wf = _workflow_text_split_flags(NODE_WRITE_PROOF_ID)
        self._write(guard.WORKFLOW_PATH, wf)
        self.assert_error_containing(
            f"not found in any run command of job '{NODE_WRITE_PROOF_ID}'"
        )

    def test_workflow_run_block_comment_command_not_accepted(self):
        # Target job: full cargo test as a shell comment (# ...) inside run: |.
        # The actual command in the block is only echo. Comment must not count.
        wf = _workflow_text_run_block_comment_command(NODE_WRITE_PROOF_ID)
        self._write(guard.WORKFLOW_PATH, wf)
        self.assert_error_containing(
            f"not found in any run command of job '{NODE_WRITE_PROOF_ID}'"
        )

    def test_workflow_multiline_run_block_command_passes(self):
        # Target job uses a run: |- block with DATABASE_URL and backslash
        # line-continuations. The assembled command must still pass validation.
        wf = _workflow_text_multiline_run_block(NODE_WRITE_PROOF_ID)
        self._write(guard.WORKFLOW_PATH, wf)
        self.assert_no_errors()

    def test_workflow_folded_run_block_command_passes(self):
        # Target job uses a run: >- folded block (newlines become spaces).
        # The assembled command must pass validation.
        wf = _workflow_text_folded_run_block(NODE_WRITE_PROOF_ID)
        self._write(guard.WORKFLOW_PATH, wf)
        self.assert_no_errors()

    # --- status wording, scoped to OPT-ARC-001 ------------------------------

    def test_opt_arc_ci_proven_wording_fails_when_prepared(self):
        self._write(guard.STATUS_MD_PATH, _status_md_text(arc_extra="; CI PROVEN"))
        self.assert_error_containing("must not contain 'CI PROVEN'")

    def test_opt_arc_ci_proven_case_insensitive_fails(self):
        self._write(guard.STATUS_MD_PATH, _status_md_text(arc_extra="; ci proven run xyz"))
        self.assert_error_containing("must not contain 'CI PROVEN'")

    def test_forbidden_wording_variants_fail(self):
        for variant in ("CI-Proven", "ci-proven", "ci proven", "CI_PROVEN"):
            with self.subTest(variant=variant):
                row = DEFAULT_BOARD_ARC_ROW.replace(
                    "PR-CI-Belege für alle fünf DB-Jobs stehen aus",
                    f"Statusmeldung {variant} eingetragen",
                )
                self._write(guard.BOARD_PATH, _board_text(arc_row=row))
                self.assert_error_containing("must not contain 'CI PROVEN'")

    def test_forbidden_variants_in_other_tasks_pass(self):
        # Hyphen/underscore variants in other tasks' rows must stay allowed.
        board = _board_text() + (
            "| OPT-API-003 | api | DB-Migrationen | Ci-Proven, Commit `00a43a00` |\n"
        )
        self._write(guard.BOARD_PATH, board)
        self.assert_no_errors()

    def test_other_proven_rows_do_not_fail(self):
        # The default fixture carries CI PROVEN rows for OPT-API-002 and OPT-MAP-001.
        # Only OPT-ARC-001 rows are guarded, so validation must stay clean.
        self.assertIn("CI PROVEN", _board_text())
        self.assertIn("CI PROVEN", _status_md_text())
        self.assert_no_errors()

    def test_forbidden_wording_regex_punctuation_embedding(self):
        # Direct helper test: markdown/punctuation wrappers must be caught,
        # alphanumeric embedding must not.
        must_block = [
            "_CI_PROVEN_",
            "_ci proven_",
            "`CI_PROVEN`",
            "(CI-PROVEN)",
            "CI_PROVEN",
            "ci proven",
            "ci-proven",
        ]
        must_not_block = [
            "XCI_PROVEN",
            "CI_PROVENX",
            "musician proven nothing",
        ]
        for text in must_block:
            with self.subTest(block=text):
                self.assertEqual(guard._contains_forbidden_wording(text), ["CI PROVEN"])
        for text in must_not_block:
            with self.subTest(allow=text):
                self.assertEqual(guard._contains_forbidden_wording(text), [])

    def test_forbidden_wording_markdown_embedded_in_arc_row_fails(self):
        # An end-to-end variant: `_CI_PROVEN_` embedded with underscores in the
        # active OPT-ARC-001 board row must block.
        row = DEFAULT_BOARD_ARC_ROW.replace(
            "PR-CI-Belege für alle fünf DB-Jobs stehen aus",
            "Status _CI_PROVEN_ vermerkt",
        )
        self._write(guard.BOARD_PATH, _board_text(arc_row=row))
        self.assert_error_containing("must not contain 'CI PROVEN'")

    # --- status MD (header-aware, unique row, date sync) ----------------------

    def test_status_md_done_fails(self):
        self._write(guard.STATUS_MD_PATH, _status_md_text(arc_status="done"))
        self.assert_error_containing("must be 'partial'")

    def test_status_md_status_cell_done_with_partial_text_fails(self):
        # cells[3] == "done"; the word "partial" appears only in another cell.
        text = _status_md_text(arc_status="done", arc_extra=" partial workflows pending")
        self._write(guard.STATUS_MD_PATH, text)
        errors = self.assert_error_containing("must be 'partial'")
        # Ensure at least one error is specifically about column 4
        self.assertTrue(any("column 4" in e for e in errors), errors)

    def test_status_md_duplicate_status_rows_fail(self):
        # One correct row plus one stale row: even a correct row must not mask
        # a stale duplicate.
        stale_row = (
            "| OPT-ARC-001 | Architektur | JSONL → PostgreSQL | partial | code+test "
            "| hoch | hoch | hoch | "
            "`docs/reports/opt-arc-001-db-proof-matrix.json`, "
            "`scripts/docmeta/validate_opt_arc_001_db_proof_matrix.py` | "
            "PR-CI-Belege ausstehend | offen | 2026-06-05 |"
        )
        self._write(guard.STATUS_MD_PATH, _status_md_text(extra_arc_row=stale_row))
        self.assert_error_containing("expected exactly one OPT-ARC-001 status row")

    def test_status_md_date_mismatch_fails(self):
        self._write(guard.STATUS_MD_PATH, _status_md_text(arc_date="2026-06-05"))
        self.assert_error_containing("zuletzt_geprüft cell must match")

    def test_status_md_date_correct_passes(self):
        # The default fixture has the correct date; baseline already checks this,
        # but this test makes the intent explicit.
        self._write(guard.STATUS_MD_PATH, _status_md_text(arc_date=UPDATED_AT))
        self.assert_no_errors()

    def test_status_md_missing_updated_at_in_index_fails(self):
        index = _index_data()
        del index["tasks"][0]["updated_at"]
        self._write_json(guard.TASK_INDEX_PATH, index)
        self.assert_error_containing("updated_at is missing")

    # --- board (header-aware: active row vs blocker row) ----------------------

    def test_board_active_plus_blocker_row_passes(self):
        self._write(guard.BOARD_PATH, _board_text())
        self.assert_no_errors()

    def test_board_active_done_blocker_partial_fails(self):
        # Active row says done; a blocker row carrying "partial" in its fourth
        # cell must not rescue the active status check.
        row = DEFAULT_BOARD_ARC_ROW.replace("| partial |", "| done |")
        blocker = DEFAULT_BOARD_BLOCKER_ROW.replace(
            "JSONL bleibt Default-Lesequelle und Write-Truth bis vollständiger Cutover |",
            "partial |",
        )
        self.assertIn("| partial |", blocker)
        self._write(guard.BOARD_PATH, _board_text(arc_row=row, blocker_row=blocker))
        self.assert_error_containing("active OPT-ARC-001 status cell must be 'partial'")

    def test_board_mentions_only_in_blocker_fails(self):
        # Matrix reference moved into the blocker row: the active row must
        # still carry it itself.
        row = DEFAULT_BOARD_ARC_ROW.replace(
            "`docs/reports/opt-arc-001-db-proof-matrix.json`, ", ""
        )
        self.assertNotIn(guard.MATRIX_PATH, row)
        blocker = DEFAULT_BOARD_BLOCKER_ROW.replace(
            "Grünen CI-Lauf der DB-Jobs belegen |",
            "Grünen CI-Lauf belegen, siehe `docs/reports/opt-arc-001-db-proof-matrix.json` |",
        )
        self._write(guard.BOARD_PATH, _board_text(arc_row=row, blocker_row=blocker))
        self.assert_error_containing(
            f"active OPT-ARC-001 row must reference '{guard.MATRIX_PATH}'"
        )

    def test_board_two_active_rows_fail(self):
        self._write(
            guard.BOARD_PATH,
            _board_text(arc_row=DEFAULT_BOARD_ARC_ROW + "\n" + DEFAULT_BOARD_ARC_ROW),
        )
        self.assert_error_containing("expected exactly one active OPT-ARC-001 row")

    def test_board_status_cell_done_with_partial_in_text_fails(self):
        # cells[3] = "done"; "partial" appears only in another cell.
        row = (
            "| OPT-ARC-001 | api | JSONL → PostgreSQL | done | high | "
            "`apps/api/src/routes/nodes.rs` partial, "
            "`apps/api/tests/db_domain_node_write_path.rs`, "
            "`docs/reports/domain-node-write-path-proof.md`, "
            "`db-domain-node-write-path-proof`, "
            "`docs/reports/opt-arc-001-db-proof-matrix.json`, "
            "`scripts/docmeta/validate_opt_arc_001_db_proof_matrix.py` | "
            "partial actions pending |"
        )
        self._write(guard.BOARD_PATH, _board_text(arc_row=row))
        self.assert_error_containing("status cell")

    def test_board_ci_proven_in_arc_row_fails(self):
        row = DEFAULT_BOARD_ARC_ROW.replace(
            "PR-CI-Belege für alle fünf DB-Jobs stehen aus",
            "CI PROVEN, Commit abc123",
        )
        self._write(guard.BOARD_PATH, _board_text(arc_row=row))
        self.assert_error_containing("must not contain 'CI PROVEN'")

    def test_board_ci_proven_case_insensitive_fails(self):
        row = DEFAULT_BOARD_ARC_ROW.replace(
            "PR-CI-Belege für alle fünf DB-Jobs stehen aus",
            "ci proven run 99999",
        )
        self._write(guard.BOARD_PATH, _board_text(arc_row=row))
        self.assert_error_containing("must not contain 'CI PROVEN'")

    def test_board_missing_node_write_evidence_fails(self):
        row = DEFAULT_BOARD_ARC_ROW.replace(
            "`apps/api/tests/db_domain_node_write_path.rs`, ", ""
        )
        self.assertNotIn(NODE_WRITE_TEST, row)
        self._write(guard.BOARD_PATH, _board_text(arc_row=row))
        self.assert_error_containing(f"must reference '{NODE_WRITE_TEST}'")

    def test_compact_table_row_recognised(self):
        # Cells without spaces around pipes should still be detected.
        compact = (
            "|OPT-ARC-001|api|JSONL → PostgreSQL|partial|high|"
            "`apps/api/src/routes/nodes.rs`,"
            "`apps/api/tests/db_domain_node_write_path.rs`,"
            "`docs/reports/domain-node-write-path-proof.md`,"
            "`db-domain-node-write-path-proof`,"
            "`docs/reports/opt-arc-001-db-proof-matrix.json`,"
            "`scripts/docmeta/validate_opt_arc_001_db_proof_matrix.py`|"
            "PR-CI pending|"
        )
        self._write(guard.BOARD_PATH, _board_text(arc_row=compact))
        # cells[0] == "OPT-ARC-001", cells[3] == "partial" → valid
        self.assert_no_errors()

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

    def test_task_index_missing_nodes_source_evidence_fails(self):
        self._write_index_without_evidence("apps/api/src/routes/nodes.rs")
        self.assert_error_containing("evidence must contain 'apps/api/src/routes/nodes.rs'")

    def test_task_index_missing_matrix_evidence_fails(self):
        self._write_index_without_evidence(guard.MATRIX_PATH)
        self.assert_error_containing(f"evidence must contain '{guard.MATRIX_PATH}'")

    def test_task_index_updated_at_empty_fails(self):
        index = _index_data()
        index["tasks"][0]["updated_at"] = "   "
        self._write_json(guard.TASK_INDEX_PATH, index)
        self.assert_error_containing("updated_at must be a non-empty string")

    # --- status JSON --------------------------------------------------------

    def _write_status_json_without_evidence(self, entry):
        status = _status_json_data()
        status["items"][0]["evidence"].remove(entry)
        self._write_json(guard.STATUS_JSON_PATH, status)

    def test_status_json_done_fails(self):
        status = _status_json_data()
        status["items"][0]["status"] = "done"
        self._write_json(guard.STATUS_JSON_PATH, status)
        self.assert_error_containing(
            f"{guard.STATUS_JSON_PATH}: OPT-ARC-001 status must be 'partial'"
        )

    def test_status_json_missing_node_test_evidence_fails(self):
        self._write_status_json_without_evidence(NODE_WRITE_TEST)
        self.assert_error_containing(f"evidence must contain '{NODE_WRITE_TEST}'")

    def test_status_json_missing_node_ci_job_evidence_fails(self):
        self._write_status_json_without_evidence(NODE_WRITE_JOB_EVIDENCE)
        self.assert_error_containing(f"evidence must contain '{NODE_WRITE_JOB_EVIDENCE}'")

    def test_status_json_missing_matrix_evidence_fails(self):
        self._write_status_json_without_evidence(guard.MATRIX_PATH)
        self.assert_error_containing(f"evidence must contain '{guard.MATRIX_PATH}'")

    def test_status_json_ci_proven_variant_in_entry_fails(self):
        status = _status_json_data()
        status["items"][0]["missing_evidence"].append("ci_proven Beleg folgt")
        self._write_json(guard.STATUS_JSON_PATH, status)
        self.assert_error_containing(
            f"{guard.STATUS_JSON_PATH}: OPT-ARC-001 entry must not contain 'CI PROVEN'"
        )

    # --- missing_evidence / additional evidence -------------------------------

    def test_missing_evidence_empty_fails_in_index(self):
        index = _index_data()
        index["tasks"][0]["missing_evidence"] = []
        self._write_json(guard.TASK_INDEX_PATH, index)
        self.assert_error_containing("missing_evidence must not become empty")

    def test_missing_evidence_empty_fails_in_status_json(self):
        status = _status_json_data()
        status["items"][0]["missing_evidence"] = []
        self._write_json(guard.STATUS_JSON_PATH, status)
        self.assert_error_containing("missing_evidence must not become empty")

    def test_additional_evidence_allowed(self):
        index = _index_data()
        index["tasks"][0]["evidence"].append("docs/blueprints/domain-data-postgres-cutover.md")
        self._write_json(guard.TASK_INDEX_PATH, index)
        status = _status_json_data()
        status["items"][0]["evidence"].append("apps/api/src/lib.rs")
        self._write_json(guard.STATUS_JSON_PATH, status)
        self.assert_no_errors()

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
