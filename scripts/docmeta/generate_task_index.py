"""
generate_task_index.py — Task-control drift check (no silent writes).

The name is inherited from the roadmap (docs/blueprints/doc-structure-task-control-roadmap.md,
Phase 4). In this iteration the script implements a deterministic *check* mode only.
It does NOT write any files: it compares the manually curated task-control artifacts
against each other and reports drift.

Schema-structural validation of docs/tasks/index.json remains the job of
scripts/docmeta/validate_task_index.py (run as a separate CI step). This script
focuses on cross-artifact drift that the schema validator does not cover:

  - docs/tasks/board.md   (human work card)
  - docs/tasks/index.json (machine-readable task index)
  - docs/reports/optimierungsstatus.json (machine twin of the OPT-* status matrix)

Usage:
    python3 -m scripts.docmeta.generate_task_index --check

Exit codes:
    0  no drift found
    1  drift found
    2  invalid invocation (e.g. called without --check; writing is intentionally not implemented)

No files are written in any mode. Drift is printed to stderr.
"""
import argparse
import json
import os
import re
import sys

from scripts.docmeta.docmeta import REPO_ROOT

INDEX_PATH = os.path.join(REPO_ROOT, "docs", "tasks", "index.json")
BOARD_PATH = os.path.join(REPO_ROOT, "docs", "tasks", "board.md")
STATUS_PATH = os.path.join(REPO_ROOT, "docs", "reports", "optimierungsstatus.json")

# Canonical task-id grammar, aligned with docs/tasks/schema.json:
# uppercase letter segments separated by '-', terminated by a three-digit number.
# Matches TASK-CTL-003, OPT-API-001, OPT-MAP-001, AUTH-XYZ-001, MAP-XYZ-001.
TASK_ID_RE = re.compile(r"\b[A-Z]+(?:-[A-Z]+)*-[0-9]{3}\b")

# Generated diagnostics are never canonical and must not be manual write targets.
GENERATED_PREFIX = "docs/_generated/"

# Top-level repository directories. An evidence string is only treated as a
# repo path (and therefore existence-checked) when it starts with one of these
# and contains no spaces. This avoids misclassifying free-form evidence such as
# "CI-Job basemap-range-delivery-proof PROVEN, Commit 14feefd6".
KNOWN_ROOTS = (
    ".github/",
    ".wgx/",
    "apps/",
    "architecture/",
    "audit/",
    "ci/",
    "configs/",
    "contracts/",
    "docs/",
    "infra/",
    "policies/",
    "scripts/",
    "src/",
    "tools/",
)

# Board sections whose tasks are live work items and must exist in index.json.
LIVE_SECTIONS = ("active", "blocker", "candidates")


def _load_json(path):
    """Return (data, error). error is None on success."""
    if not os.path.isfile(path):
        return None, f"file not found: {path}"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f), None
    except json.JSONDecodeError as e:
        return None, f"invalid JSON in {path}: {e}"
    except OSError as e:
        return None, f"cannot read {path}: {e}"


def _read_text(path):
    """Return (text, error). error is None on success."""
    if not os.path.isfile(path):
        return None, f"file not found: {path}"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read(), None
    except OSError as e:
        return None, f"cannot read {path}: {e}"


def _path_exists(rel_path, repo_root):
    return os.path.exists(os.path.join(repo_root, rel_path))


def _looks_like_repo_path(value):
    if not isinstance(value, str) or " " in value:
        return False
    return any(value.startswith(root) for root in KNOWN_ROOTS)


def _classify_section(heading):
    h = heading.strip().lower()
    if "aktive" in h:
        return "active"
    if "blocker" in h:
        return "blocker"
    if "kandidat" in h:
        return "candidates"
    if "zurückgestellt" in h or "zuruckgestellt" in h or "optional" in h:
        return "deferred"
    if "erledigt" in h:
        return "done"
    return "other"


def parse_board(text):
    """
    Parse board.md into a mapping of section-key -> set of task ids.

    Task ids are collected from the *first* cell (the ID column) of Markdown
    table rows (lines starting with '|') within each section. Restricting to
    the first cell prevents task ids that are only mentioned in evidence,
    rationale or next-action columns from being treated as board entries.
    Header and separator rows contain no matching ids and are harmless.
    """
    sections = {
        "active": set(),
        "blocker": set(),
        "candidates": set(),
        "deferred": set(),
        "done": set(),
        "other": set(),
    }
    current = None
    for line in text.splitlines():
        stripped = line.strip()
        heading = re.match(r"^#{1,6}\s+(.*)$", stripped)
        if heading:
            current = _classify_section(heading.group(1))
            continue
        if current and stripped.startswith("|"):
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if not cells:
                continue
            first_cell = cells[0]
            for match in TASK_ID_RE.finditer(first_cell):
                sections[current].add(match.group(0))
    return sections


def _board_union(board_sections, keys):
    union = set()
    for key in keys:
        union |= board_sections.get(key, set())
    return union


def _as_str_list(value):
    return [v for v in value if isinstance(v, str)] if isinstance(value, list) else []


def _explained(path, missing_evidence):
    return any(path in m for m in missing_evidence)


def check_task_control(index, board_sections, status, repo_root):
    """
    Compare task-control artifacts and return a sorted list of drift messages.
    Empty list means no drift. Does not write any files.
    """
    errors = []

    tasks = index.get("tasks") if isinstance(index, dict) else None
    if not isinstance(tasks, list):
        return ["index.json: 'tasks' is missing or not an array"]

    index_tasks = {}
    for task in tasks:
        if isinstance(task, dict) and isinstance(task.get("id"), str):
            index_tasks[task["id"]] = task
    index_ids = set(index_tasks)

    status_items = status.get("items") if isinstance(status, dict) else None
    status_status = {}
    if isinstance(status_items, list):
        for item in status_items:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                status_status[item["id"]] = item.get("status")
    status_ids = set(status_status)

    known_ids = index_ids | status_ids
    board_all = set().union(*board_sections.values())
    live_board = _board_union(board_sections, LIVE_SECTIONS)
    candidates = board_sections.get("candidates", set())
    active = board_sections.get("active", set())
    deferred = board_sections.get("deferred", set())

    # 1. Board active/candidate/blocker tasks must exist in index.json.
    for tid in sorted(live_board):
        if tid not in index_ids:
            errors.append(
                f"board.md lists active/candidate task '{tid}' that is missing from docs/tasks/index.json"
            )

    # 2. Every task mentioned in board.md must be known to the machine layer.
    for tid in sorted(board_all):
        if tid not in known_ids:
            errors.append(
                f"board.md references task '{tid}' unknown to docs/tasks/index.json "
                f"and docs/reports/optimierungsstatus.json"
            )

    # 3. High/medium open or partial tasks must be visible in board.md.
    #    Low-priority, done, or deferred tasks do not need board-level visibility.
    for tid in sorted(index_ids):
        task = index_tasks[tid]
        status_val = task.get("status")
        priority = task.get("priority")
        must_be_visible = status_val in {"open", "partial"} and priority in {"high", "medium"}
        if must_be_visible and tid not in board_all:
            errors.append(
                f"docs/tasks/index.json task '{tid}' is {priority}/{status_val} "
                f"but does not appear in docs/tasks/board.md"
            )

    # Per-task business rules and path checks.
    for tid in sorted(index_ids):
        task = index_tasks[tid]
        status_val = task.get("status")
        priority = task.get("priority")
        evidence = _as_str_list(task.get("evidence"))
        missing_evidence = _as_str_list(task.get("missing_evidence"))
        acceptance = _as_str_list(task.get("acceptance"))
        links = task.get("links") if isinstance(task.get("links"), dict) else {}
        docs_links = _as_str_list(links.get("docs"))

        # 4. done tasks need evidence.
        if status_val == "done" and not evidence:
            errors.append(f"docs/tasks/index.json task '{tid}' is done but has no evidence")

        # 5. high-priority tasks need at least one acceptance criterion.
        if priority == "high" and not acceptance:
            errors.append(
                f"docs/tasks/index.json task '{tid}' is high priority but has no acceptance criterion"
            )

        # 6. evidence repo paths must exist (or be explained in missing_evidence).
        for ev in evidence:
            if ev.startswith(GENERATED_PREFIX):
                errors.append(
                    f"docs/tasks/index.json task '{tid}' lists generated artifact '{ev}' as evidence; "
                    f"docs/_generated/* must not be a manual target"
                )
                continue
            if _looks_like_repo_path(ev) and not _path_exists(ev, repo_root):
                if not _explained(ev, missing_evidence):
                    errors.append(
                        f"docs/tasks/index.json task '{tid}' evidence path '{ev}' does not exist "
                        f"and is not explained in missing_evidence"
                    )

        # 7. links.docs paths must exist (or be explained in missing_evidence).
        for doc in docs_links:
            if doc.startswith(GENERATED_PREFIX):
                errors.append(
                    f"docs/tasks/index.json task '{tid}' links.docs '{doc}' points into docs/_generated/; "
                    f"generated diagnostics must not be a manual target"
                )
                continue
            if not _path_exists(doc, repo_root) and not _explained(doc, missing_evidence):
                errors.append(
                    f"docs/tasks/index.json task '{tid}' links.docs '{doc}' does not exist "
                    f"and is not explained in missing_evidence"
                )

    # 8. TASK-CTL-003 must stay visible as a next priority while it is open.
    t003 = index_tasks.get("TASK-CTL-003")
    if t003 is not None and t003.get("status") == "open":
        if "TASK-CTL-003" not in (candidates | active):
            errors.append(
                "TASK-CTL-003 is open but not listed as a next PR candidate / active priority in docs/tasks/board.md"
            )

    # 9. TASK-CTL-002 must not appear as a next PR candidate while deliberately deferred.
    t002 = index_tasks.get("TASK-CTL-002")
    if t002 is not None:
        t002_missing = _as_str_list(t002.get("missing_evidence"))
        is_deferred = "TASK-CTL-002" in deferred or any(
            "zurückgestellt" in m.lower() or "zurueckgestellt" in m.lower() for m in t002_missing
        )
        if is_deferred and "TASK-CTL-002" in candidates:
            errors.append(
                "TASK-CTL-002 is deliberately deferred but listed as a next PR candidate in docs/tasks/board.md"
            )

    # 10. Status must not contradict between index.json and optimierungsstatus.json.
    for tid in sorted(index_ids & status_ids):
        index_status = index_tasks[tid].get("status")
        twin_status = status_status.get(tid)
        if isinstance(twin_status, str) and index_status != twin_status:
            errors.append(
                f"status mismatch for '{tid}': docs/tasks/index.json='{index_status}' vs "
                f"docs/reports/optimierungsstatus.json='{twin_status}'"
            )

    return sorted(errors)


def run_check(index_path, board_path, status_path, repo_root):
    """Load the three artifacts and return a list of drift messages."""
    errors = []

    index, index_err = _load_json(index_path)
    if index_err:
        errors.append(index_err)

    status, status_err = _load_json(status_path)
    if status_err:
        errors.append(status_err)

    board_text, board_err = _read_text(board_path)
    if board_err:
        errors.append(board_err)

    if index is None or status is None or board_text is None:
        return errors

    board_sections = parse_board(board_text)
    errors.extend(check_task_control(index, board_sections, status, repo_root))
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="generate_task_index",
        description="Check task-control artifacts (board.md, index.json, optimierungsstatus.json) for drift.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate task-control artifacts for drift. No files are written.",
    )
    args = parser.parse_args(argv)

    if not args.check:
        print(
            "generate_task_index: only --check mode is implemented; "
            "silent generation is not allowed. Re-run with --check.",
            file=sys.stderr,
        )
        return 2

    errors = run_check(INDEX_PATH, BOARD_PATH, STATUS_PATH, REPO_ROOT)

    if errors:
        print(f"\n--- Task-Control Drift ({len(errors)}) ---", file=sys.stderr)
        for error in errors:
            print(f"  DRIFT: {error}", file=sys.stderr)
        print(f"\nTask-control drift check failed: {len(errors)} issue(s).", file=sys.stderr)
        return 1

    print("Task-control drift check passed (0 issues).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
