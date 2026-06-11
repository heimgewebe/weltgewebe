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

# Exact field sets — unknown or missing fields are rejected.
MATRIX_REQUIRED_FIELDS = frozenset({
    "schema", "task", "status_source", "overall_status", "cutover_status",
    "default_domain_read_truth", "default_domain_write_truth",
    "ci_evidence_policy", "non_goals", "proofs",
})

PROOF_REQUIRED_FIELDS = frozenset({
    "id", "phase", "claim", "state", "workflow", "workflow_job",
    "test", "report", "ci_evidence", "command",
})

REQUIRED_NON_GOALS = (
    "edge_writes",
    "step_up_email_persistence",
    "webauthn_user_id_writeback",
    "jsonl_removal",
    "production_cutover",
    "dual_write",
)

# A proof may only carry state="ci_proven" together with a ci_evidence object
# holding all of these keys. The current matrix maps prepared proofs only,
# so "ci_proven" is rejected outright (see _validate_proof).
CI_EVIDENCE_REQUIRED_KEYS = ("run_url", "run_id", "commit", "job")

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
REQUIRED_SOURCE_EVIDENCE = ("apps/api/src/routes/nodes.rs",)
REQUIRED_GUARD_EVIDENCE = (MATRIX_PATH, VALIDATOR_PATH)

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


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Markdown table helpers
# ---------------------------------------------------------------------------

def _table_cells(line):
    """Parse a Markdown table line into a list of stripped cell strings."""
    if "|" not in line:
        return []
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _task_rows(text):
    """Return (line, cells) tuples for all OPT-ARC-001 rows (cells[0] == TASK_ID)."""
    rows = []
    for line in text.splitlines():
        cells = _table_cells(line)
        if cells and cells[0] == TASK_ID:
            rows.append((line, cells))
    return rows


# ---------------------------------------------------------------------------
# Forbidden wording (scoped to OPT-ARC-001 rows/entries)
# ---------------------------------------------------------------------------

def _contains_forbidden_wording(text):
    """Return list of forbidden wordings found in text (CI PROVEN case-insensitive)."""
    result = []
    if "ci proven" in text.lower():
        result.append("CI PROVEN")
    if "ci_proven" in text:
        result.append("ci_proven")
    return result


# ---------------------------------------------------------------------------
# Command check (regex-based)
# ---------------------------------------------------------------------------

def _check_command(command, proof_id, expected_test_name, errors):
    if not isinstance(command, str):
        errors.append(f"{MATRIX_PATH}: proof '{proof_id}': command must be a string")
        return
    # Accept --test <name> or --test=<name>; exclude --test-threads via (?!-)
    test_targets = re.findall(r'--test(?!-)(?:[=\s]+)(\S+)', command)
    if len(test_targets) != 1 or test_targets[0] != expected_test_name:
        errors.append(
            f"{MATRIX_PATH}: proof '{proof_id}': command must contain exactly "
            f"'--test {expected_test_name}' (one occurrence, correct name); "
            f"found {test_targets}"
        )
    if not re.search(r'--include-ignored', command):
        errors.append(
            f"{MATRIX_PATH}: proof '{proof_id}': command must contain '--include-ignored'"
        )
    if not re.search(r'--test-threads(?:[=\s]+)1\b', command):
        errors.append(
            f"{MATRIX_PATH}: proof '{proof_id}': command must contain '--test-threads=1'"
        )


# ---------------------------------------------------------------------------
# Workflow job-block extractor
# ---------------------------------------------------------------------------

def _extract_workflow_job_block(workflow_text, job_id):
    """Return the text block for the named workflow job, or None if not found.

    Collects the job key line and all subsequent lines that are strictly more
    indented, stopping at the first line whose indentation is <= the job key's.
    Empty lines are kept within the block.
    """
    lines = workflow_text.splitlines()
    start_idx = None
    job_indent = None

    for i, line in enumerate(lines):
        m = re.match(rf'^([ \t]*){re.escape(job_id)}\s*:', line)
        if m:
            start_idx = i
            job_indent = len(m.group(1))
            break

    if start_idx is None:
        return None

    block = [lines[start_idx]]
    for line in lines[start_idx + 1:]:
        if not line.strip():
            block.append(line)
            continue
        current_indent = len(line) - len(line.lstrip())
        if current_indent <= job_indent:
            break
        block.append(line)

    return "\n".join(block)


# ---------------------------------------------------------------------------
# CI evidence object check (future ci_proven rule)
# ---------------------------------------------------------------------------

def _check_ci_evidence_object(value):
    """Return True when value is a complete ci_evidence object."""
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


# ---------------------------------------------------------------------------
# Proof validation
# ---------------------------------------------------------------------------

def _validate_proof(proof, repo_root, errors):
    proof_id = proof["id"]
    spec = EXPECTED_PROOFS[proof_id]

    extra_fields = set(proof.keys()) - PROOF_REQUIRED_FIELDS
    missing_fields = PROOF_REQUIRED_FIELDS - set(proof.keys())
    for f in sorted(extra_fields):
        errors.append(f"{MATRIX_PATH}: proof '{proof_id}': unexpected field '{f}'")
    for f in sorted(missing_fields):
        errors.append(f"{MATRIX_PATH}: proof '{proof_id}': missing required field '{f}'")

    claim = proof.get("claim")
    if not isinstance(claim, str) or not claim.strip():
        errors.append(f"{MATRIX_PATH}: proof '{proof_id}': claim must be a non-empty string")

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


# ---------------------------------------------------------------------------
# Matrix validation
# ---------------------------------------------------------------------------

def _validate_matrix(repo_root, errors):
    if not _file_exists(repo_root, MATRIX_PATH):
        raise BrokenInputError(f"mandatory file missing: {MATRIX_PATH}")

    matrix = _load_json_object(repo_root, MATRIX_PATH)

    extra_fields = set(matrix.keys()) - MATRIX_REQUIRED_FIELDS
    missing_fields = MATRIX_REQUIRED_FIELDS - set(matrix.keys())
    for f in sorted(extra_fields):
        errors.append(f"{MATRIX_PATH}: unexpected top-level field '{f}'")
    for f in sorted(missing_fields):
        errors.append(f"{MATRIX_PATH}: missing required top-level field '{f}'")

    if matrix.get("schema") != EXPECTED_SCHEMA:
        errors.append(
            f"{MATRIX_PATH}: schema must be '{EXPECTED_SCHEMA}', got '{matrix.get('schema')}'"
        )
    if matrix.get("task") != TASK_ID:
        errors.append(f"{MATRIX_PATH}: task must be '{TASK_ID}', got '{matrix.get('task')}'")
    if matrix.get("status_source") != STATUS_MD_PATH:
        errors.append(
            f"{MATRIX_PATH}: status_source must be '{STATUS_MD_PATH}', "
            f"got '{matrix.get('status_source')}'"
        )
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
        _validate_proof(proof, repo_root, errors)

    for proof_id in EXPECTED_PROOFS:
        if proof_id not in seen_ids:
            errors.append(f"{MATRIX_PATH}: missing expected proof id '{proof_id}'")

    expected_order = list(EXPECTED_PROOFS.keys())
    expected_subset = [e for e in expected_order if e in seen_ids]
    if seen_ids != expected_subset:
        errors.append(
            f"{MATRIX_PATH}: proofs must appear in the canonical order: {expected_order}"
        )


# ---------------------------------------------------------------------------
# Workflow validation (job-scoped)
# ---------------------------------------------------------------------------

def _validate_workflow(repo_root, errors):
    workflow_text = _read_text(repo_root, WORKFLOW_PATH)
    for proof_id, spec in EXPECTED_PROOFS.items():
        job_block = _extract_workflow_job_block(workflow_text, proof_id)
        if job_block is None:
            errors.append(f"{WORKFLOW_PATH}: workflow job '{proof_id}' not found")
            continue
        test_name = spec["command_test_name"]
        if not re.search(rf'--test(?!-)(?:[=\s]+){re.escape(test_name)}\b', job_block):
            errors.append(
                f"{WORKFLOW_PATH}: '--test {test_name}' not found in job '{proof_id}'"
            )


# ---------------------------------------------------------------------------
# Task index: read updated_at for date-sync check
# ---------------------------------------------------------------------------

def _find_entry(entries):
    """Return the OPT-ARC-001 dict from a list of task/item dicts, or None."""
    for entry in entries:
        if isinstance(entry, dict) and entry.get("id") == TASK_ID:
            return entry
    return None


def _get_task_updated_at(repo_root):
    """Return updated_at string for OPT-ARC-001 from task index, or None."""
    try:
        index = _load_json_object(repo_root, TASK_INDEX_PATH)
    except BrokenInputError:
        return None
    tasks = index.get("tasks", [])
    task = _find_entry(tasks)
    if task is None:
        return None
    val = task.get("updated_at")
    return val if isinstance(val, str) and val.strip() else None


# ---------------------------------------------------------------------------
# Status MD validation (cell-based, date sync)
# ---------------------------------------------------------------------------

def _validate_status_md(repo_root, errors):
    text = _read_text(repo_root, STATUS_MD_PATH)
    rows = _task_rows(text)
    if not rows:
        errors.append(f"{STATUS_MD_PATH}: no OPT-ARC-001 table row found")
        return

    combined = "\n".join(line for line, _ in rows)

    # Status cell (index 3): every OPT-ARC-001 row must have cells[3] == "partial".
    for line, cells in rows:
        if len(cells) < 4:
            errors.append(
                f"{STATUS_MD_PATH}: OPT-ARC-001 row has fewer than 4 cells: {line[:80]!r}"
            )
            continue
        if cells[3] != EXPECTED_OVERALL_STATUS:
            errors.append(
                f"{STATUS_MD_PATH}: {TASK_ID} status cell (column 4) must be "
                f"'{EXPECTED_OVERALL_STATUS}', got '{cells[3]}'"
            )

    # Date sync: last cell of the status matrix row must match index.json updated_at.
    task_updated_at = _get_task_updated_at(repo_root)
    if task_updated_at is None:
        errors.append(
            f"{STATUS_MD_PATH}: {TASK_ID} updated_at is missing, empty, or not a string "
            f"in {TASK_INDEX_PATH}"
        )
    else:
        date_found = any(cells[-1] == task_updated_at for _, cells in rows if len(cells) >= 4)
        if not date_found:
            errors.append(
                f"{STATUS_MD_PATH}: {TASK_ID} zuletzt_geprüft cell must match "
                f"{TASK_INDEX_PATH} updated_at '{task_updated_at}'"
            )

    for wording in _contains_forbidden_wording(combined):
        errors.append(f"{STATUS_MD_PATH}: {TASK_ID} row must not contain '{wording}'")
    for required in (MATRIX_PATH, VALIDATOR_PATH):
        if required not in combined:
            errors.append(f"{STATUS_MD_PATH}: {TASK_ID} row must reference '{required}'")


# ---------------------------------------------------------------------------
# Board validation (cell-based)
# ---------------------------------------------------------------------------

def _validate_board(repo_root, errors):
    text = _read_text(repo_root, BOARD_PATH)
    rows = _task_rows(text)
    if not rows:
        errors.append(f"{BOARD_PATH}: no OPT-ARC-001 table row found")
        return

    combined = "\n".join(line for line, _ in rows)

    for line, cells in rows:
        if len(cells) < 4:
            errors.append(
                f"{BOARD_PATH}: OPT-ARC-001 row has fewer than 4 cells: {line[:80]!r}"
            )

    # At least one row (the active section row) must carry cells[3] == "partial".
    # Blocker-section rows use column 4 for a different purpose and are not status cells.
    if not any(cells[3] == EXPECTED_OVERALL_STATUS for _, cells in rows if len(cells) >= 4):
        errors.append(
            f"{BOARD_PATH}: {TASK_ID} must have at least one row with status cell "
            f"'{EXPECTED_OVERALL_STATUS}' at column 4"
        )

    for wording in _contains_forbidden_wording(combined):
        errors.append(f"{BOARD_PATH}: {TASK_ID} row(s) must not contain '{wording}'")
    for required in BOARD_REQUIRED_MENTIONS:
        if required not in combined:
            errors.append(f"{BOARD_PATH}: {TASK_ID} row(s) must reference '{required}'")


# ---------------------------------------------------------------------------
# Common checks for task-control entries
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Task index validation
# ---------------------------------------------------------------------------

def _validate_task_index(repo_root, errors):
    index = _load_json_object(repo_root, TASK_INDEX_PATH)
    tasks = index.get("tasks")
    if not isinstance(tasks, list):
        raise BrokenInputError(
            f"unexpected structure in {TASK_INDEX_PATH}: 'tasks' must be an array"
        )

    task = _find_entry(tasks)
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
        + REQUIRED_SOURCE_EVIDENCE
        + REQUIRED_GUARD_EVIDENCE
    )
    for required in required_evidence:
        if required not in evidence:
            errors.append(f"{TASK_INDEX_PATH}: {TASK_ID} evidence must contain '{required}'")

    links = task.get("links")
    docs_links = links.get("docs") if isinstance(links, dict) else None
    if not isinstance(docs_links, list) or MATRIX_PATH not in docs_links:
        errors.append(f"{TASK_INDEX_PATH}: {TASK_ID} links.docs must contain '{MATRIX_PATH}'")


# ---------------------------------------------------------------------------
# Status JSON validation
# ---------------------------------------------------------------------------

def _validate_status_json(repo_root, errors):
    status = _load_json_object(repo_root, STATUS_JSON_PATH)
    items = status.get("items")
    if not isinstance(items, list):
        raise BrokenInputError(
            f"unexpected structure in {STATUS_JSON_PATH}: 'items' must be an array"
        )

    item = _find_entry(items)
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
    required_evidence = (
        REQUIRED_TEST_EVIDENCE
        + REQUIRED_REPORT_EVIDENCE
        + REQUIRED_CI_JOB_EVIDENCE
        + REQUIRED_SOURCE_EVIDENCE
        + REQUIRED_GUARD_EVIDENCE
    )
    for required in required_evidence:
        if required not in evidence:
            errors.append(f"{STATUS_JSON_PATH}: {TASK_ID} evidence must contain '{required}'")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

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
