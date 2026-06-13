"""
validate_opt_arc_001_db_proof_matrix.py — Blocking truth guard for OPT-ARC-001.

OPT-ARC-001 (JSONL → PostgreSQL) has six DB proof jobs in
.github/workflows/api.yml. This validator pins that truth machine-readably and
blocks stale evidence or drift toward false completion claims:

  - docs/reports/opt-arc-001-db-proof-matrix.json must describe exactly the
    six expected proofs, no cutover, JSONL as default domain read and write
    truth, no dual write.
  - Each proof is either state="prepared" with ci_evidence=null, or
    state="ci_proven" with a concrete ci_evidence object (run_url, run_id,
    commit, job). For a ci_proven proof the evidence job must equal the proof
    id, and run_url must be a github.com/heimgewebe/weltgewebe Actions run URL
    whose trailing run id matches run_id. The proof's own workflow job block in
    the API workflow and the proof's test file must also be unchanged since the
    evidence commit (job-scoped: adding an unrelated job to the shared workflow
    file does not stale other proofs' evidence; changing a proof's own job
    does). ci_proven only records that the prepared DB jobs ran green in real
    PR-CI with a fresh proof harness; it is NOT a cutover — overall_status
    stays "partial" and JSONL stays read/write truth.
  - Each proof job must contain a real run command that invokes the expected cargo test with --include-ignored and --test-threads=1.
  - Task-control and status artifacts (docs/tasks/board.md,
    docs/tasks/index.json, docs/reports/optimierungsstatus.md,
    docs/reports/optimierungsstatus.json) must keep OPT-ARC-001 at status
    "partial", keep the missing PR-CI evidence explicit, reference the matrix
    and this validator, and must not use "CI PROVEN" wording (any variant:
    CI PROVEN, ci-proven, CI_Proven, ...) for OPT-ARC-001. Status cells are
    located via table headers: the board must carry exactly one active
    OPT-ARC-001 row in a table with a status column, and
    docs/reports/optimierungsstatus.md exactly one OPT-ARC-001 status row
    whose last (date) cell matches docs/tasks/index.json updated_at.
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
import shlex
import subprocess
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

# edge_writes left this list with OPT-ARC-001 Phase E-C (opt-in PostgreSQL
# write path for POST /edges); the remaining non-goals stay binding.
REQUIRED_NON_GOALS = (
    "step_up_email_persistence",
    "webauthn_credential_writeback",
    "legacy_webauthn_user_id_backfill",
    "webauthn_user_id_not_null",
    "jsonl_removal",
    "production_cutover",
    "dual_write",
)

# A proof may only carry state="ci_proven" together with a ci_evidence object
# whose fields have exactly these types. bool is an int subclass; exact type
# equality prevents it from passing as run_id.
CI_EVIDENCE_FIELD_TYPES = {
    "run_url": str,
    "run_id": int,
    "commit": str,
    "job": str,
}
CI_EVIDENCE_REQUIRED_KEYS = tuple(CI_EVIDENCE_FIELD_TYPES)
CI_EVIDENCE_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")

# A ci_proven proof's run_url must be a real GitHub Actions run URL for this
# repository; the trailing path segment of the URL must equal run_id.
GITHUB_ACTIONS_RUN_URL_PREFIX = "https://github.com/heimgewebe/weltgewebe/actions/runs/"

# All spelling variants of the forbidden completion claim: CI PROVEN,
# ci proven, CI-Proven, ci-proven, ci_proven, CI_PROVEN, ...
# Word boundaries (\b) treat '_' as a word char, so '_CI_PROVEN_' would slip
# through. Lookarounds reject alphanumeric embedding (XCI_PROVEN, CI_PROVENX)
# while allowing markdown/punctuation wrappers (backticks, '_', '(', ')').
FORBIDDEN_WORDING_RE = re.compile(
    r"(?<![A-Za-z0-9])ci[\s_-]proven(?![A-Za-z0-9])",
    re.IGNORECASE,
)

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
    "db-domain-edge-write-path-proof": {
        "phase": "E-C",
        "test": "apps/api/tests/db_domain_edge_write_path.rs",
        "report": "docs/reports/domain-edge-write-path-proof.md",
        "command_test_name": "db_domain_edge_write_path",
    },
}

REQUIRED_TEST_EVIDENCE = tuple(spec["test"] for spec in EXPECTED_PROOFS.values())
REQUIRED_REPORT_EVIDENCE = tuple(
    spec["report"] for spec in EXPECTED_PROOFS.values() if spec["report"] is not None
)
REQUIRED_CI_JOB_EVIDENCE = tuple(f"CI-Job: {proof_id}" for proof_id in EXPECTED_PROOFS)
REQUIRED_SOURCE_EVIDENCE = (
    "apps/api/src/routes/nodes.rs",
    "apps/api/src/routes/edges.rs",
)
REQUIRED_GUARD_EVIDENCE = (MATRIX_PATH, VALIDATOR_PATH)

# Single source of truth for the evidence every OPT-ARC-001 task-control entry
# (index.json task, optimierungsstatus.json item) must carry. Additional
# legitimate evidence stays allowed; no exact-set equality is enforced.
ALL_REQUIRED_EVIDENCE = (
    REQUIRED_TEST_EVIDENCE
    + REQUIRED_REPORT_EVIDENCE
    + REQUIRED_CI_JOB_EVIDENCE
    + REQUIRED_SOURCE_EVIDENCE
    + REQUIRED_GUARD_EVIDENCE
)

BOARD_REQUIRED_MENTIONS = (
    "apps/api/src/routes/nodes.rs",
    "apps/api/tests/db_domain_node_write_path.rs",
    "docs/reports/domain-node-write-path-proof.md",
    "db-domain-node-write-path-proof",
    "apps/api/src/routes/edges.rs",
    "apps/api/tests/db_domain_edge_write_path.rs",
    "docs/reports/domain-edge-write-path-proof.md",
    "db-domain-edge-write-path-proof",
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
# Markdown table helpers (header-aware)
# ---------------------------------------------------------------------------

def _table_cells(line):
    """Parse a Markdown table line into a list of stripped cell strings."""
    if "|" not in line:
        return []
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_separator_row(cells):
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def _normalize_header_cell(cell):
    return cell.replace("`", "").replace("*", "").strip().lower()


def _annotated_task_rows(text):
    """Return (line, cells, status_col) tuples for all OPT-ARC-001 table rows.

    status_col is the index of the 'status' column taken from the table header
    above the row (header line directly followed by a |---| separator), or
    None when that table has no status column (e.g. the board blocker table).
    """
    rows = []
    pending_header = None
    current_status_col = None
    for line in text.splitlines():
        cells = _table_cells(line)
        if not cells:
            # Table ended; the next table starts with its own header.
            pending_header = None
            current_status_col = None
            continue
        if _is_separator_row(cells):
            if pending_header is not None:
                normalized = [_normalize_header_cell(c) for c in pending_header]
                current_status_col = (
                    normalized.index("status") if "status" in normalized else None
                )
                pending_header = None
            continue
        if cells[0] == TASK_ID:
            rows.append((line, cells, current_status_col))
        pending_header = cells
    return rows


# ---------------------------------------------------------------------------
# Forbidden wording (scoped to OPT-ARC-001 rows/entries)
# ---------------------------------------------------------------------------

def _contains_forbidden_wording(text):
    """Return ['CI PROVEN'] if any forbidden completion-claim variant occurs, else [].

    Variants (CI PROVEN, ci proven, CI-Proven, ci-proven, ci_proven, ...) are
    reported under the single canonical label to avoid duplicate findings.
    """
    if FORBIDDEN_WORDING_RE.search(text):
        return ["CI PROVEN"]
    return []


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
    if "--include-ignored" not in command:
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
    indented, stopping at the first content line whose indentation is <= the
    job key's. Blank lines are tolerated inside the block. Comments are only
    kept while indented deeper than the job key; a comment at or below the job
    key's indentation (e.g. a top-level comment between two jobs) terminates
    the block, so it cannot lend its text to the preceding job. Job-internal
    keys (if:, continue-on-error:, services:, steps:, ...) are more indented
    than the job key and therefore never terminate it.
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
        stripped = line.strip()
        if not stripped:
            block.append(line)
            continue
        current_indent = len(line) - len(line.lstrip())
        if current_indent <= job_indent:
            # A sibling job key or a top-level/sibling-level comment ends the
            # block. Comments at this depth must not be attributed to the job.
            break
        block.append(line)

    return "\n".join(block)


# ---------------------------------------------------------------------------
# Workflow run-command extraction (per-step, not job-wide)
# ---------------------------------------------------------------------------

def _strip_unquoted_shell_comment(line):
    in_single = False
    in_double = False
    escaped = False

    for i, ch in enumerate(line):
        if escaped:
            escaped = False
            continue

        if ch == "\\" and not in_single:
            escaped = True
            continue

        if ch == "'" and not in_double:
            in_single = not in_single
            continue

        if ch == '"' and not in_single:
            in_double = not in_double
            continue

        if ch == "#" and not in_single and not in_double:
            return line[:i]

    return line


def _normalize_run_command(raw_text):
    """Normalize a run-command body for flag checking.

    Strips shell comment lines, joins backslash-line-continuations, and
    collapses whitespace. The result is a single comparable string that can
    be checked for the presence of specific flags without false positives
    from commented-out commands.
    """
    lines = raw_text.splitlines()
    lines = [_strip_unquoted_shell_comment(l) for l in lines]
    lines = [l for l in lines if l.strip()]
    joined = '\n'.join(lines)
    # Backslash-newline continuations (optional surrounding whitespace) → space.
    joined = re.sub(r'\\\s*\n\s*', ' ', joined)
    return re.sub(r'\s+', ' ', joined).strip()


def _extract_workflow_run_commands(job_block):
    """Return a list of normalized run-command strings from a job block.

    Handles inline values (`- run: cargo test ...`) and block scalars
    (`run: |`, `run: |-`, `run: >-`, etc.). Shell comment lines are stripped
    from block bodies so that commented-out commands cannot satisfy checks.
    """
    lines = job_block.splitlines()
    commands = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r'^([ \t]*)(?:-[ \t]+)?run\s*:\s*(.*)', line)
        if not m:
            i += 1
            continue

        run_indent = len(m.group(1))
        value = m.group(2).strip()
        i += 1

        if re.fullmatch(r'[|>][+-]?', value) or value == '':
            # Block scalar — collect body lines.
            is_folded = value.startswith('>')
            block_lines = []
            body_indent = None
            while i < len(lines):
                bl = lines[i]
                if not bl.strip():
                    block_lines.append('')
                    i += 1
                    continue
                current_indent = len(bl) - len(bl.lstrip())
                if body_indent is None:
                    if current_indent <= run_indent:
                        break
                    body_indent = current_indent
                
                if current_indent < body_indent:
                    break
                block_lines.append(bl)
                i += 1
            # Strip common leading indent so comment-stripping works on bare text.
            non_empty = [l for l in block_lines if l.strip()]
            min_indent = min((len(l) - len(l.lstrip()) for l in non_empty), default=0)
            stripped = [
                l[min_indent:] if len(l) >= min_indent else l.lstrip()
                for l in block_lines
            ]
            if is_folded:
                # Folded style: newlines become spaces (simplified).
                raw_text = ' '.join(s for s in stripped if s.strip())
            else:
                raw_text = '\n'.join(stripped)
        else:
            raw_text = value

        commands.append(_normalize_run_command(raw_text))

    return commands


SHELL_COMMAND_SEPARATORS = {";", "&&", "||", "|", "&"}
_ENV_ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$")


def _shell_tokens(command):
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        lexer.commenters = ""
        return list(lexer)
    except ValueError:
        return []


def _split_shell_segments(tokens):
    segments = []
    current_segment = []
    for token in tokens:
        if token in SHELL_COMMAND_SEPARATORS or all(c in ';&|' for c in token):
            segments.append(current_segment)
            current_segment = []
        else:
            current_segment.append(token)
    segments.append(current_segment)
    return segments


def _command_has_required_cargo_test_invocation(command, test_name):
    tokens = _shell_tokens(command)
    segments = _split_shell_segments(tokens)
    
    if len(segments) != 1:
        return False
        
    segment = segments[0]
    
    if not segment:
        return False
    
    idx = 0
    while idx < len(segment):
        t = segment[idx]
        if _ENV_ASSIGNMENT_RE.match(t) or t in ("time", "env"):
            idx += 1
        else:
            break
    if idx + 1 < len(segment) and segment[idx] == "cargo" and segment[idx+1] == "test":
        has_locked = "--locked" in segment
        has_include_ignored = "--include-ignored" in segment
        
        has_package = False
        for i, t in enumerate(segment):
            if t in ("-p", "--package") and i + 1 < len(segment) and segment[i+1] == "weltgewebe-api":
                has_package = True
                break
            if t in ("-pweltgewebe-api", "--package=weltgewebe-api"):
                has_package = True
                break
                
        has_test = False
        for i, t in enumerate(segment):
            if t == "--test" and i + 1 < len(segment) and segment[i+1] == test_name:
                has_test = True
                break
            if t == f"--test={test_name}":
                has_test = True
                break
                
        has_threads = False
        for i, t in enumerate(segment):
            if t == "--test-threads" and i + 1 < len(segment) and segment[i+1] == "1":
                has_threads = True
                break
            if t == "--test-threads=1":
                has_threads = True
                break
                
        if has_locked and has_include_ignored and has_package and has_test and has_threads:
            return True
    return False


# ---------------------------------------------------------------------------
# CI evidence object and proof-harness freshness checks (ci_proven rule)
# ---------------------------------------------------------------------------

class GitFreshnessError(RuntimeError):
    """Raised when Git cannot complete a proof-harness freshness check."""


def _ci_evidence_freshness_paths(proof_id):
    """Return the narrowly scoped non-workflow proof-harness paths for one proof.

    The shared API workflow file is checked separately and job-scoped (see
    _workflow_job_changed_since): adding an unrelated proof job to the file
    must not stale the evidence of the other proofs, while any change to the
    proof's own job block still does.
    """
    spec = EXPECTED_PROOFS[proof_id]
    return (spec["test"],)


def _run_git(repo_root, args):
    """Run a deterministic Git command without invoking a shell."""
    try:
        return subprocess.run(
            ["git", "-C", os.fspath(repo_root), *args],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitFreshnessError(str(exc)) from exc


def _git_commit_exists(repo_root, commit):
    """Return whether commit resolves locally to a Git commit object."""
    result = _run_git(repo_root, ["cat-file", "-e", f"{commit}^{{commit}}"])
    return result.returncode == 0


def _git_commit_is_ancestor_of_head(repo_root, commit):
    """Return whether commit belongs to the current HEAD history."""
    result = _run_git(repo_root, ["merge-base", "--is-ancestor", commit, "HEAD"])
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    detail = result.stderr.strip() or result.stdout.strip() or "unknown Git error"
    raise GitFreshnessError(detail)


def _git_changed_paths_since(repo_root, commit, paths):
    """Return proof-harness paths changed between commit and HEAD."""
    result = _run_git(
        repo_root,
        ["diff", "--name-only", f"{commit}..HEAD", "--", *paths],
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown Git error"
        raise GitFreshnessError(detail)
    return [line for line in result.stdout.splitlines() if line]


def _git_show_file(repo_root, rev, rel_path):
    """Return the file content at the given revision via `git show`."""
    result = _run_git(repo_root, ["show", f"{rev}:{rel_path}"])
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown Git error"
        raise GitFreshnessError(detail)
    return result.stdout


def _workflow_job_changed_since(repo_root, commit, proof_id):
    """Return whether the proof's own workflow job block changed since commit.

    Job-scoped on purpose: the six proofs share one workflow file, so adding a
    later phase's job must not invalidate the recorded PR-CI evidence of the
    earlier proofs. Any textual change to the proof's own job block (or its
    removal) still counts as a harness change and stales the evidence.
    """
    old_text = _git_show_file(repo_root, commit, WORKFLOW_PATH)
    new_text = _git_show_file(repo_root, "HEAD", WORKFLOW_PATH)
    old_block = _extract_workflow_job_block(old_text, proof_id)
    new_block = _extract_workflow_job_block(new_text, proof_id)
    return old_block != new_block


def _check_ci_evidence_object(value):
    """Return True when value is a complete, strictly typed ci_evidence object.

    Each required field must match its declared type exactly (no swapped
    types): run_url/commit/job non-empty strings, run_id a real int (bool
    rejected). Extra keys remain tolerated, matching the prior policy.
    """
    if not isinstance(value, dict):
        return False
    for key, expected_type in CI_EVIDENCE_FIELD_TYPES.items():
        v = value.get(key)
        if expected_type is int:
            # bool is an int subclass; exact type equality prevents it from passing as run_id.
            if type(v) is not int:
                return False
        else:  # str fields
            if not isinstance(v, str) or not v.strip():
                return False
    return True


def _validate_ci_evidence(proof_id, ci_evidence, errors):
    """Append structural evidence errors and return whether evidence is valid."""
    if not _check_ci_evidence_object(ci_evidence):
        errors.append(
            f"{MATRIX_PATH}: proof '{proof_id}': state 'ci_proven' requires a ci_evidence "
            f"object with {', '.join(CI_EVIDENCE_REQUIRED_KEYS)} "
            f"(run_url/commit/job non-empty strings, run_id a real int)"
        )
        return False

    valid = True
    job = ci_evidence["job"]
    if job != proof_id:
        errors.append(
            f"{MATRIX_PATH}: proof '{proof_id}': ci_evidence.job must equal the proof id, "
            f"got '{job}'"
        )
        valid = False

    run_url = ci_evidence["run_url"]
    run_id = ci_evidence["run_id"]
    if not run_url.startswith(GITHUB_ACTIONS_RUN_URL_PREFIX):
        errors.append(
            f"{MATRIX_PATH}: proof '{proof_id}': ci_evidence.run_url must start with "
            f"'{GITHUB_ACTIONS_RUN_URL_PREFIX}', got '{run_url}'"
        )
        valid = False
    else:
        url_run_id = run_url[len(GITHUB_ACTIONS_RUN_URL_PREFIX):].split("/")[0].split("?")[0]
        if url_run_id != str(run_id):
            errors.append(
                f"{MATRIX_PATH}: proof '{proof_id}': ci_evidence.run_id ({run_id}) "
                f"must match the run id in run_url ('{url_run_id}')"
            )
            valid = False
    return valid


def _validate_ci_evidence_freshness(proof_id, repo_root, ci_evidence, errors):
    """Require a ci_proven proof's narrow harness to be unchanged since evidence."""
    commit = ci_evidence["commit"].strip()
    if not CI_EVIDENCE_COMMIT_RE.fullmatch(commit):
        errors.append(
            f"{MATRIX_PATH}: proof '{proof_id}': ci_evidence.commit must be a full "
            f"40-character lowercase hex Git SHA, got '{commit}'"
        )
        return

    try:
        if not _git_commit_exists(repo_root, commit):
            errors.append(
                f"{MATRIX_PATH}: proof '{proof_id}': ci_evidence commit '{commit}' "
                "was not found in the local Git history"
            )
            return
        if not _git_commit_is_ancestor_of_head(repo_root, commit):
            errors.append(
                f"{MATRIX_PATH}: proof '{proof_id}': ci_evidence commit '{commit}' "
                "is not an ancestor of HEAD"
            )
            return
        paths = _ci_evidence_freshness_paths(proof_id)
        changed_paths = _git_changed_paths_since(repo_root, commit, paths)
        if _workflow_job_changed_since(repo_root, commit, proof_id):
            changed_paths.append(f"{WORKFLOW_PATH} (job '{proof_id}')")
    except GitFreshnessError as exc:
        errors.append(
            f"{MATRIX_PATH}: proof '{proof_id}': unable to check ci_evidence commit "
            f"'{commit}' freshness: {exc}"
        )
        return

    if changed_paths:
        errors.append(
            f"{MATRIX_PATH}: proof '{proof_id}': ci_evidence is stale; changed proof "
            f"harness paths since commit {commit}: {', '.join(changed_paths)}"
        )


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
    if state not in ("prepared", "ci_proven"):
        errors.append(
            f"{MATRIX_PATH}: proof '{proof_id}': state must be 'prepared' or 'ci_proven', "
            f"got '{state}'"
        )
    elif state == "prepared":
        if ci_evidence is not None:
            errors.append(
                f"{MATRIX_PATH}: proof '{proof_id}': state 'prepared' requires ci_evidence "
                f"to be null (no PR-CI evidence recorded for a prepared proof)"
            )
    else:  # state == "ci_proven"
        if _validate_ci_evidence(proof_id, ci_evidence, errors):
            _validate_ci_evidence_freshness(proof_id, repo_root, ci_evidence, errors)

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

    # non_goals is minimum-set checked: future explicit non-goals may be added without changing the guard.
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
        run_commands = _extract_workflow_run_commands(job_block)
        found = any(
            _command_has_required_cargo_test_invocation(cmd, test_name)
            for cmd in run_commands
        )
        if not found:
            errors.append(
                f"{WORKFLOW_PATH}: expected cargo test command for "
                f"'--test {test_name}' with --include-ignored and --test-threads=1 "
                f"not found in any run command of job '{proof_id}'"
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
    task = _find_entry(tasks if isinstance(tasks, list) else [])
    if task is None:
        return None
    val = task.get("updated_at")
    return val if isinstance(val, str) and val.strip() else None


# ---------------------------------------------------------------------------
# Status MD validation (header-aware, unique status row, date sync)
# ---------------------------------------------------------------------------

def _validate_status_md(repo_root, errors):
    text = _read_text(repo_root, STATUS_MD_PATH)
    rows = _annotated_task_rows(text)
    if not rows:
        errors.append(f"{STATUS_MD_PATH}: no OPT-ARC-001 table row found")
        return

    combined = "\n".join(line for line, _, _ in rows)
    for wording in _contains_forbidden_wording(combined):
        errors.append(f"{STATUS_MD_PATH}: {TASK_ID} row must not contain '{wording}'")

    status_rows = [(line, cells, col) for line, cells, col in rows if col is not None]
    if len(status_rows) != 1:
        errors.append(
            f"{STATUS_MD_PATH}: expected exactly one {TASK_ID} status row "
            f"(a row in a table with a status column), found {len(status_rows)}"
        )
        if not status_rows:
            return

    line, cells, status_col = status_rows[0]
    if len(cells) <= status_col:
        errors.append(
            f"{STATUS_MD_PATH}: {TASK_ID} status row has fewer cells than its table header"
        )
        return
    if cells[status_col] != EXPECTED_OVERALL_STATUS:
        errors.append(
            f"{STATUS_MD_PATH}: {TASK_ID} status cell (column {status_col + 1}) must be "
            f"'{EXPECTED_OVERALL_STATUS}', got '{cells[status_col]}'"
        )

    # Date sync: the last (Stand/zuletzt_geprüft) cell must match index.json updated_at.
    task_updated_at = _get_task_updated_at(repo_root)
    if task_updated_at is None:
        errors.append(
            f"{STATUS_MD_PATH}: {TASK_ID} updated_at is missing, empty, or not a string "
            f"in {TASK_INDEX_PATH}"
        )
    elif cells[-1] != task_updated_at:
        errors.append(
            f"{STATUS_MD_PATH}: {TASK_ID} zuletzt_geprüft cell must match "
            f"{TASK_INDEX_PATH} updated_at '{task_updated_at}', got '{cells[-1]}'"
        )

    for required in (MATRIX_PATH, VALIDATOR_PATH):
        if required not in line:
            errors.append(f"{STATUS_MD_PATH}: {TASK_ID} row must reference '{required}'")


# ---------------------------------------------------------------------------
# Board validation (header-aware: one active status row, blocker rows separate)
# ---------------------------------------------------------------------------

def _validate_board(repo_root, errors):
    text = _read_text(repo_root, BOARD_PATH)
    rows = _annotated_task_rows(text)
    if not rows:
        errors.append(f"{BOARD_PATH}: no OPT-ARC-001 table row found")
        return

    # Forbidden wording stays scoped to ALL OPT-ARC-001 rows (incl. blocker rows).
    combined = "\n".join(line for line, _, _ in rows)
    for wording in _contains_forbidden_wording(combined):
        errors.append(f"{BOARD_PATH}: {TASK_ID} row(s) must not contain '{wording}'")

    # The active task row lives in a table with a status column; blocker rows
    # (ID | Blocker | Fehlt | Folge) have none and must not satisfy status or
    # evidence requirements on behalf of the active row.
    active_rows = [(line, cells, col) for line, cells, col in rows if col is not None]
    if len(active_rows) != 1:
        errors.append(
            f"{BOARD_PATH}: expected exactly one active {TASK_ID} row "
            f"(a row in a table with a status column), found {len(active_rows)}"
        )
        if not active_rows:
            return

    line, cells, status_col = active_rows[0]
    if len(cells) <= status_col:
        errors.append(
            f"{BOARD_PATH}: active {TASK_ID} row has fewer cells than its table header"
        )
    elif cells[status_col] != EXPECTED_OVERALL_STATUS:
        errors.append(
            f"{BOARD_PATH}: active {TASK_ID} status cell must be "
            f"'{EXPECTED_OVERALL_STATUS}', got '{cells[status_col]}'"
        )

    for required in BOARD_REQUIRED_MENTIONS:
        if required not in line:
            errors.append(f"{BOARD_PATH}: active {TASK_ID} row must reference '{required}'")


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


def _validate_task_control_entry(entry, rel_path, errors, *, require_links_docs=False):
    """Shared checks for the OPT-ARC-001 entry in task-control JSON artifacts.

    Required evidence must be present; additional legitimate evidence stays
    allowed (no exact-set equality is enforced).
    """
    if entry.get("status") != EXPECTED_OVERALL_STATUS:
        errors.append(
            f"{rel_path}: {TASK_ID} status must be '{EXPECTED_OVERALL_STATUS}', "
            f"got '{entry.get('status')}'"
        )
    _check_missing_evidence_kept(entry.get("missing_evidence"), rel_path, errors)
    _check_no_forbidden_wording_in_entry(entry, rel_path, errors)

    evidence = entry.get("evidence")
    evidence = evidence if isinstance(evidence, list) else []
    for required in ALL_REQUIRED_EVIDENCE:
        if required not in evidence:
            errors.append(f"{rel_path}: {TASK_ID} evidence must contain '{required}'")

    if require_links_docs:
        links = entry.get("links")
        docs_links = links.get("docs") if isinstance(links, dict) else None
        if not isinstance(docs_links, list) or MATRIX_PATH not in docs_links:
            errors.append(f"{rel_path}: {TASK_ID} links.docs must contain '{MATRIX_PATH}'")


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

    _validate_task_control_entry(task, TASK_INDEX_PATH, errors, require_links_docs=True)

    updated_at = task.get("updated_at")
    if not isinstance(updated_at, str) or not updated_at.strip():
        errors.append(
            f"{TASK_INDEX_PATH}: {TASK_ID} updated_at must be a non-empty string"
        )


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

    _validate_task_control_entry(item, STATUS_JSON_PATH, errors)


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
