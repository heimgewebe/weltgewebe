"""
validate_opt_arc_001_db_proof_matrix.py — Blocking truth guard for OPT-ARC-001.

OPT-ARC-001 (JSONL → PostgreSQL) has five prepared DB proof jobs in
.github/workflows/api.yml but no PR-CI evidence yet. This validator pins that
truth machine-readably and blocks drift toward false completion claims:

  - docs/reports/opt-arc-001-db-proof-matrix.json must describe exactly the
    five expected proofs (state="prepared", ci_evidence=null), no cutover,
    JSONL as default domain read and write truth, no dual write.
  - A proof may only ever claim state="ci_proven" together with a concrete
    ci_evidence object (run_url, run_id, commit, job). In the current matrix
    version every proof must remain "prepared", so any "ci_proven" entry is
    rejected either way.
  - Task-control and status artifacts (docs/tasks/board.md,
    docs/tasks/index.json, docs/reports/optimierungsstatus.md,
    docs/reports/optimierungsstatus.json) must keep OPT-ARC-001 at status
    "partial", keep the missing PR-CI evidence explicit, reference the matrix
    and this validator, and must not use "CI PROVEN" wording for OPT-ARC-001.
    All checks are scoped to OPT-ARC-001; legitimately proven rows of other
    tasks are out of scope and never blocked.

Usage:
    python3 -m scripts.docmeta.validate_opt_arc_001_db_proof_matrix

Exit codes:
    0  all checks pass
    1  matrix, status or evidence violations found
    2  broken input (mandatory file missing/unreadable, invalid JSON,
       unexpected top-level structure)

No files are written. Violations are printed to stderr.
"""
import json
import os
import re
import sys

from scripts.docmeta.docmeta import REPO_ROOT

MATRIX_PATH = "docs/reports/opt-arc-001-db-proof-matrix.json"
VALIDATOR_PATH = "scripts/docmeta/validate_opt_arc_001_db_proof_matrix.py"
WORKFLOW_PATH = ".github/workflows/api.yml"
BOARD_PATH = "docs/tasks/board.md"
TASK_INDEX_PATH = "docs/tasks/index.json"
STATUS_MD_PATH = "docs/reports/optimierungsstatus.md"
STATUS_JSON_PATH = "docs/reports/optimierungsstatus.json"

EXPECTED_SCHEMA = "weltgewebe.opt_arc_001_db_proof_matrix.v1"
TASK_ID = "OPT-ARC-001"
EXPECTED_OVERALL_STATUS = "partial"
EXPECTED_CUTOVER_STATUS = "not_cutover"
EXPECTED_DEFAULT_TRUTH = "jsonl"
EXPECTED_CI_POLICY = "github_pr_ci_required"

REQUIRED_NON_GOALS = (
    "edge_writes",
    "step_up_email_persistence",
    "webauthn_user_id_writeback",
    "jsonl_removal",
    "production_cutover",
    "dual_write",
)

# A proof may only ever carry state="ci_proven" together with a ci_evidence
# object holding all of these keys. The current matrix version maps prepared
# proofs only, so "ci_proven" is additionally rejected outright (see below).
CI_EVIDENCE_REQUIRED_KEYS = ("run_url", "run_id", "commit", "job")

FORBIDDEN_WORDINGS = ("CI PROVEN", "ci_proven")

EXPECTED_PROOFS = {
    "db-domain-schema-migrations-proof": {
        "phase": "B",
        "test": "apps/api/tests/db_domain_schema_migrations.rs",
        "report": None,
        "command_test_name": "db_domain_schema_migrations",
    },
    "db-domain-backfill-proof": {
        "phase": "C",
        "test": "apps/api/tests/db_domain_backfill.rs",
        "report": "docs/reports/domain-backfill-proof.md",
        "command_test_name": "db_domain_backfill",
    },
    "db-domain-read-path-proof": {
        "phase": "D",
        "test": "apps/api/tests/db_domain_read_path.rs",
        "report": "docs/reports/domain-read-path-proof.md",
        "command_test_name": "db_domain_read_path",
    },
    "db-domain-account-write-path-proof": {
        "phase": "E-A",
        "test": "apps/api/tests/db_domain_account_write_path.rs",
        "report": "docs/reports/domain-account-write-path-proof.md",
        "command_test_name": "db_domain_account_write_path",
    },
    "db-domain-node-write-path-proof": {
        "phase": "E-B",
        "test": "apps/api/tests/db_domain_node_write_path.rs",
        "report": "docs/reports/domain-node-write-path-proof.md",
        "command_test_name": "db_domain_node_write_path",
    },
}

REQUIRED_TEST_EVIDENCE = tuple(spec["test"] for spec in EXPECTED_PROOFS.values())
REQUIRED_REPORT_EVIDENCE = tuple(
    spec["report"] for spec in EXPECTED_PROOFS.values() if spec["report"] is not None
)
REQUIRED_CI_JOB_EVIDENCE = tuple(f"CI-Job: {proof_id}" for proof_id in EXPECTED_PROOFS)

BOARD_REQUIRED_MENTIONS = (
    "apps/api/src/routes/nodes.rs",
    "apps/api/tests/db_domain_node_write_path.rs",
    "docs/reports/domain-node-write-path-proof.md",
    "db-domain-node-write-path-proof",
    MATRIX_PATH,
    VALIDATOR_PATH,
)


class BrokenInputError(Exception):
    """Raised for unreadable mandatory files, invalid JSON, or broken top-level structure (exit 2)."""


def _read_text(repo_root, rel_path):
    path = os.path.join(repo_root, rel_path)
    if not os.path.isfile(path):
        raise BrokenInputError(f"mandatory file missing: {rel_path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError) as e:
        raise BrokenInputError(f"cannot read mandatory file {rel_path}: {e}")


def _load_json_object(repo_root, rel_path):
    text = _read_text(repo_root, rel_path)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise BrokenInputError(f"invalid JSON in {rel_path}: {e}")
    if not isinstance(data, dict):
        raise BrokenInputError(
            f"unexpected structure in {rel_path}: top level must be a JSON object, "
            f"got {type(data).__name__}"
        )
    return data


def _file_exists(repo_root, rel_path):
    return os.path.isfile(os.path.join(repo_root, rel_path))


def _contains_forbidden_wording(text):
    return [w for w in FORBIDDEN_WORDINGS if w in text]


def _check_command(command, proof_id, expected_test_name, errors):
    if not isinstance(command, str):
        errors.append(f"{MATRIX_PATH}: proof '{proof_id}': command must be a string")
        return
    tokens = command.split()
    test_positions = [i for i, tok in enumerate(tokens) if tok == "--test"]
    if (
        len(test_positions) != 1
        or test_positions[0] + 1 >= len(tokens)
        or tokens[test_positions[0] + 1] != expected_test_name
    ):
        errors.append(
            f"{MATRIX_PATH}: proof '{proof_id}': command must contain exactly "
            f"'--test {expected_test_name}'"
        )
    if "--include-ignored" not in tokens:
        errors.append(
            f"{MATRIX_PATH}: proof '{proof_id}': command must contain '--include-ignored'"
        )
    if "--test-threads=1" not in tokens:
        errors.append(
            f"{MATRIX_PATH}: proof '{proof_id}': command must contain '--test-threads=1'"
        )


def _check_ci_evidence_object(value):
    """Return True when value is a complete ci_evidence object (future ci_proven rule)."""
    if not isinstance(value, dict):
        return False
    for key in CI_EVIDENCE_REQUIRED_KEYS:
        v = value.get(key)
        if isinstance(v, str):
            if not v.strip():
                return False
        elif not isinstance(v, int) or isinstance(v, bool):
            return False
    return True


def _validate_proof(proof, expected, repo_root, errors):
    proof_id = proof["id"]
    spec = expected[proof_id]

    phase = proof.get("phase")
    if phase != spec["phase"]:
        errors.append(
            f"{MATRIX_PATH}: proof '{proof_id}': phase must be '{spec['phase']}', got '{phase}'"
        )

    state = proof.get("state")
    ci_evidence = proof.get("ci_evidence")
    if state != "prepared":
        errors.append(
            f"{MATRIX_PATH}: proof '{proof_id}': state must be 'prepared' "
            f"(matrix currently maps prepared proofs only, no PR-CI evidence exists), got '{state}'"
        )
    if state == "ci_proven" and not _check_ci_evidence_object(ci_evidence):
        errors.append(
            f"{MATRIX_PATH}: proof '{proof_id}': state 'ci_proven' requires a ci_evidence "
            f"object with {', '.join(CI_EVIDENCE_REQUIRED_KEYS)}"
        )
    if ci_evidence is not None:
        errors.append(
            f"{MATRIX_PATH}: proof '{proof_id}': ci_evidence must be null "
            f"(no PR-CI evidence exists yet)"
        )

    workflow = proof.get("workflow")
    if workflow != WORKFLOW_PATH:
        errors.append(
            f"{MATRIX_PATH}: proof '{proof_id}': workflow must be '{WORKFLOW_PATH}', got '{workflow}'"
        )

    workflow_job = proof.get("workflow_job")
    if workflow_job != proof_id:
        errors.append(
            f"{MATRIX_PATH}: proof '{proof_id}': workflow_job must equal the proof id, "
            f"got '{workflow_job}'"
        )

    test = proof.get("test")
    if test != spec["test"]:
        errors.append(
            f"{MATRIX_PATH}: proof '{proof_id}': test must be '{spec['test']}', got '{test}'"
        )
    elif not _file_exists(repo_root, test):
        errors.append(f"{MATRIX_PATH}: proof '{proof_id}': test file '{test}' does not exist")

    report = proof.get("report")
    if report != spec["report"]:
        errors.append(
            f"{MATRIX_PATH}: proof '{proof_id}': report must be "
            f"{spec['report']!r}, got {report!r}"
        )
    elif report is not None and not _file_exists(repo_root, report):
        errors.append(f"{MATRIX_PATH}: proof '{proof_id}': report file '{report}' does not exist")

    _check_command(proof.get("command"), proof_id, spec["command_test_name"], errors)


def _validate_matrix(repo_root, errors):
    if not _file_exists(repo_root, MATRIX_PATH):
        errors.append(f"{MATRIX_PATH}: matrix file does not exist")
        return

    matrix = _load_json_object(repo_root, MATRIX_PATH)

    if matrix.get("schema") != EXPECTED_SCHEMA:
        errors.append(
            f"{MATRIX_PATH}: schema must be '{EXPECTED_SCHEMA}', got '{matrix.get('schema')}'"
        )
    if matrix.get("task") != TASK_ID:
        errors.append(f"{MATRIX_PATH}: task must be '{TASK_ID}', got '{matrix.get('task')}'")
    if matrix.get("overall_status") != EXPECTED_OVERALL_STATUS:
        errors.append(
            f"{MATRIX_PATH}: overall_status must be '{EXPECTED_OVERALL_STATUS}', "
            f"got '{matrix.get('overall_status')}'"
        )
    if matrix.get("cutover_status") != EXPECTED_CUTOVER_STATUS:
        errors.append(
            f"{MATRIX_PATH}: cutover_status must be '{EXPECTED_CUTOVER_STATUS}', "
            f"got '{matrix.get('cutover_status')}' (no cutover happened)"
        )
    if matrix.get("default_domain_read_truth") != EXPECTED_DEFAULT_TRUTH:
        errors.append(
            f"{MATRIX_PATH}: default_domain_read_truth must be '{EXPECTED_DEFAULT_TRUTH}', "
            f"got '{matrix.get('default_domain_read_truth')}' (JSONL remains default read source)"
        )
    if matrix.get("default_domain_write_truth") != EXPECTED_DEFAULT_TRUTH:
        errors.append(
            f"{MATRIX_PATH}: default_domain_write_truth must be '{EXPECTED_DEFAULT_TRUTH}', "
            f"got '{matrix.get('default_domain_write_truth')}' (JSONL remains write truth)"
        )
    if matrix.get("ci_evidence_policy") != EXPECTED_CI_POLICY:
        errors.append(
            f"{MATRIX_PATH}: ci_evidence_policy must be '{EXPECTED_CI_POLICY}', "
            f"got '{matrix.get('ci_evidence_policy')}'"
        )

    non_goals = matrix.get("non_goals")
    if not isinstance(non_goals, list):
        errors.append(f"{MATRIX_PATH}: non_goals must be an array")
    else:
        for goal in REQUIRED_NON_GOALS:
            if goal not in non_goals:
                errors.append(f"{MATRIX_PATH}: non_goals must contain '{goal}'")

    proofs = matrix.get("proofs")
    if not isinstance(proofs, list):
        errors.append(f"{MATRIX_PATH}: proofs must be an array")
        return

    seen_ids = []
    for i, proof in enumerate(proofs):
        if not isinstance(proof, dict):
            errors.append(f"{MATRIX_PATH}: proofs[{i}] must be an object")
            continue
        proof_id = proof.get("id")
        if not isinstance(proof_id, str):
            errors.append(f"{MATRIX_PATH}: proofs[{i}] is missing a string 'id'")
            continue
        if proof_id not in EXPECTED_PROOFS:
            errors.append(f"{MATRIX_PATH}: unexpected proof id '{proof_id}'")
            continue
        if proof_id in seen_ids:
            errors.append(f"{MATRIX_PATH}: duplicate proof id '{proof_id}'")
            continue
        seen_ids.append(proof_id)
        _validate_proof(proof, EXPECTED_PROOFS, repo_root, errors)

    for proof_id in EXPECTED_PROOFS:
        if proof_id not in seen_ids:
            errors.append(f"{MATRIX_PATH}: missing expected proof id '{proof_id}'")


def _validate_workflow(repo_root, errors):
    workflow_text = _read_text(repo_root, WORKFLOW_PATH)
    for proof_id, spec in EXPECTED_PROOFS.items():
        if not re.search(rf"^[ \t]*{re.escape(proof_id)}\s*:", workflow_text, re.MULTILINE):
            errors.append(f"{WORKFLOW_PATH}: workflow job '{proof_id}' not found")
        test_name = spec["command_test_name"]
        if not re.search(rf"--test\s+{re.escape(test_name)}\b", workflow_text):
            errors.append(
                f"{WORKFLOW_PATH}: '--test {test_name}' not found for job '{proof_id}'"
            )


def _task_rows(text):
    """Return all table rows of the OPT-ARC-001 task (scoped; other tasks' rows are ignored)."""
    return [
        line
        for line in text.splitlines()
        if line.strip().startswith(f"| {TASK_ID} |")
    ]


def _validate_status_md(repo_root, errors):
    text = _read_text(repo_root, STATUS_MD_PATH)
    rows = _task_rows(text)
    if not rows:
        errors.append(f"{STATUS_MD_PATH}: no '| {TASK_ID} |' table row found")
        return
    combined = "\n".join(rows)

    has_partial_cell = any(
        any(cell.strip() == EXPECTED_OVERALL_STATUS for cell in row.strip().strip("|").split("|"))
        for row in rows
    )
    if not has_partial_cell:
        errors.append(
            f"{STATUS_MD_PATH}: {TASK_ID} row must keep status cell '{EXPECTED_OVERALL_STATUS}'"
        )
    for wording in _contains_forbidden_wording(combined):
        errors.append(f"{STATUS_MD_PATH}: {TASK_ID} row must not contain '{wording}'")
    for required in (MATRIX_PATH, VALIDATOR_PATH):
        if required not in combined:
            errors.append(f"{STATUS_MD_PATH}: {TASK_ID} row must reference '{required}'")


def _validate_board(repo_root, errors):
    text = _read_text(repo_root, BOARD_PATH)
    rows = _task_rows(text)
    if not rows:
        errors.append(f"{BOARD_PATH}: no '| {TASK_ID} |' table row found")
        return
    combined = "\n".join(rows)

    if EXPECTED_OVERALL_STATUS not in combined:
        errors.append(
            f"{BOARD_PATH}: {TASK_ID} row(s) must keep status '{EXPECTED_OVERALL_STATUS}'"
        )
    for wording in _contains_forbidden_wording(combined):
        errors.append(f"{BOARD_PATH}: {TASK_ID} row(s) must not contain '{wording}'")
    for required in BOARD_REQUIRED_MENTIONS:
        if required not in combined:
            errors.append(f"{BOARD_PATH}: {TASK_ID} row(s) must reference '{required}'")


def _find_entry(entries, rel_path):
    for entry in entries:
        if isinstance(entry, dict) and entry.get("id") == TASK_ID:
            return entry
    return None


def _check_missing_evidence_kept(missing_evidence, rel_path, errors):
    is_kept = (
        isinstance(missing_evidence, list)
        and any(isinstance(m, str) and m.strip() for m in missing_evidence)
    )
    if not is_kept:
        errors.append(
            f"{rel_path}: {TASK_ID} missing_evidence must not become empty "
            f"(missing PR-CI evidence must stay explicit)"
        )


def _check_no_forbidden_wording_in_entry(entry, rel_path, errors):
    dumped = json.dumps(entry, ensure_ascii=False)
    for wording in _contains_forbidden_wording(dumped):
        errors.append(f"{rel_path}: {TASK_ID} entry must not contain '{wording}'")


def _validate_task_index(repo_root, errors):
    index = _load_json_object(repo_root, TASK_INDEX_PATH)
    tasks = index.get("tasks")
    if not isinstance(tasks, list):
        raise BrokenInputError(
            f"unexpected structure in {TASK_INDEX_PATH}: 'tasks' must be an array"
        )

    task = _find_entry(tasks, TASK_INDEX_PATH)
    if task is None:
        errors.append(f"{TASK_INDEX_PATH}: task '{TASK_ID}' not found")
        return

    if task.get("status") != EXPECTED_OVERALL_STATUS:
        errors.append(
            f"{TASK_INDEX_PATH}: {TASK_ID} status must be '{EXPECTED_OVERALL_STATUS}', "
            f"got '{task.get('status')}'"
        )
    _check_missing_evidence_kept(task.get("missing_evidence"), TASK_INDEX_PATH, errors)
    _check_no_forbidden_wording_in_entry(task, TASK_INDEX_PATH, errors)

    evidence = task.get("evidence")
    evidence = evidence if isinstance(evidence, list) else []
    required_evidence = (
        REQUIRED_TEST_EVIDENCE
        + REQUIRED_REPORT_EVIDENCE
        + REQUIRED_CI_JOB_EVIDENCE
        + (MATRIX_PATH, VALIDATOR_PATH)
    )
    for required in required_evidence:
        if required not in evidence:
            errors.append(f"{TASK_INDEX_PATH}: {TASK_ID} evidence must contain '{required}'")

    links = task.get("links")
    docs_links = links.get("docs") if isinstance(links, dict) else None
    if not isinstance(docs_links, list) or MATRIX_PATH not in docs_links:
        errors.append(f"{TASK_INDEX_PATH}: {TASK_ID} links.docs must contain '{MATRIX_PATH}'")


def _validate_status_json(repo_root, errors):
    status = _load_json_object(repo_root, STATUS_JSON_PATH)
    items = status.get("items")
    if not isinstance(items, list):
        raise BrokenInputError(
            f"unexpected structure in {STATUS_JSON_PATH}: 'items' must be an array"
        )

    item = _find_entry(items, STATUS_JSON_PATH)
    if item is None:
        errors.append(f"{STATUS_JSON_PATH}: item '{TASK_ID}' not found")
        return

    if item.get("status") != EXPECTED_OVERALL_STATUS:
        errors.append(
            f"{STATUS_JSON_PATH}: {TASK_ID} status must be '{EXPECTED_OVERALL_STATUS}', "
            f"got '{item.get('status')}'"
        )
    _check_missing_evidence_kept(item.get("missing_evidence"), STATUS_JSON_PATH, errors)
    _check_no_forbidden_wording_in_entry(item, STATUS_JSON_PATH, errors)

    evidence = item.get("evidence")
    evidence = evidence if isinstance(evidence, list) else []
    for required in (MATRIX_PATH, VALIDATOR_PATH):
        if required not in evidence:
            errors.append(f"{STATUS_JSON_PATH}: {TASK_ID} evidence must contain '{required}'")


def validate(repo_root=REPO_ROOT):
    """
    Validate the OPT-ARC-001 DB proof matrix and its task-control twins.

    Returns a list of violation strings (empty list means valid).
    Raises BrokenInputError for unreadable mandatory files, invalid JSON,
    or unexpected top-level structure. Does not write any files.
    """
    errors = []
    _validate_matrix(repo_root, errors)
    _validate_workflow(repo_root, errors)
    _validate_status_md(repo_root, errors)
    _validate_board(repo_root, errors)
    _validate_task_index(repo_root, errors)
    _validate_status_json(repo_root, errors)
    return errors


def main(argv=None):
    del argv  # no CLI options; module is invoked bare via python3 -m
    try:
        errors = validate(REPO_ROOT)
    except BrokenInputError as e:
        print(f"{TASK_ID} DB proof matrix validation aborted (broken input): {e}", file=sys.stderr)
        return 2

    if errors:
        print(f"{TASK_ID} DB proof matrix validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"{TASK_ID} DB proof matrix validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
