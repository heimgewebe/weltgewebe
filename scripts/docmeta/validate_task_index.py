"""
validate_task_index.py — Validates docs/tasks/index.json against schema and business rules.

Usage:
    python3 scripts/docmeta/validate_task_index.py docs/tasks/index.json

Exit codes:
    0  all checks pass
    1  validation errors found

No files are written. Errors are printed to stderr.
"""
import json
import os
import re
import sys

REPO_ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", ".."))

SCHEMA_PATH = os.path.join(REPO_ROOT, "docs", "tasks", "schema.json")

ALLOWED_AREA = {"docs", "ci", "api", "web", "infra", "release", "auth", "map", "governance"}
ALLOWED_STATUS = {"open", "partial", "done", "blocked", "obsolete", "contradicted"}
ALLOWED_PRIORITY = {"high", "medium", "low"}
ALLOWED_EFFORT = {"XS", "S", "M", "L", "XL"}
ALLOWED_RISK = {"low", "medium", "high"}

ID_PATTERN = re.compile(r"^[A-Z]+(-[A-Z]+)*-[0-9]{3}$")
DATE_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")

REQUIRED_TASK_FIELDS = frozenset({
    "id", "title", "area", "status", "priority", "effort", "risk",
    "owner", "evidence", "missing_evidence", "acceptance", "links", "updated_at",
})
REQUIRED_LINKS_FIELDS = frozenset({"issues", "prs", "docs"})


def _path_exists(rel_path):
    return os.path.isfile(os.path.join(REPO_ROOT, rel_path))


def validate_task_index(index_path):
    """
    Validate a task index JSON file.

    Returns a list of error strings. Empty list means valid.
    Does not write any files.
    """
    errors = []

    if not os.path.isfile(index_path):
        return [f"Index file not found: {index_path}"]

    try:
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)
    except json.JSONDecodeError as e:
        return [f"Invalid JSON in {index_path}: {e}"]

    if not os.path.isfile(SCHEMA_PATH):
        errors.append(f"Schema file not found: {SCHEMA_PATH}")

    if not isinstance(index, dict):
        return errors + [f"index.json must be a JSON object, got {type(index).__name__}"]

    if "schema_version" not in index:
        errors.append("Missing required top-level field: schema_version")

    if "tasks" not in index:
        errors.append("Missing required top-level field: tasks")
        return errors

    tasks = index["tasks"]
    if not isinstance(tasks, list):
        errors.append(f"'tasks' must be an array, got {type(tasks).__name__}")
        return errors

    for sf in index.get("source_files", []):
        if not _path_exists(sf):
            errors.append(f"source_files: '{sf}' does not exist")

    seen_ids = {}

    for i, task in enumerate(tasks):
        if not isinstance(task, dict):
            errors.append(f"tasks[{i}]: expected object, got {type(task).__name__}")
            continue

        task_id = task.get("id", f"<unnamed[{i}]>")
        prefix = f"tasks[{i}] ({task_id})"

        for field in sorted(REQUIRED_TASK_FIELDS):
            if field not in task:
                errors.append(f"{prefix}: missing required field '{field}'")

        tid = task.get("id")
        if tid is not None:
            if not isinstance(tid, str) or not ID_PATTERN.match(tid):
                errors.append(
                    f"{prefix}: id '{tid}' does not match pattern "
                    r"^[A-Z]+(-[A-Z]+)*-[0-9]{3}$"
                )
            if tid in seen_ids:
                errors.append(
                    f"{prefix}: duplicate id '{tid}' (also at tasks[{seen_ids[tid]}])"
                )
            else:
                seen_ids[tid] = i

        area = task.get("area")
        if area is not None and area not in ALLOWED_AREA:
            errors.append(f"{prefix}: area '{area}' not in {sorted(ALLOWED_AREA)}")

        status = task.get("status")
        if status is not None and status not in ALLOWED_STATUS:
            errors.append(f"{prefix}: status '{status}' not in {sorted(ALLOWED_STATUS)}")

        priority = task.get("priority")
        if priority is not None and priority not in ALLOWED_PRIORITY:
            errors.append(f"{prefix}: priority '{priority}' not in {sorted(ALLOWED_PRIORITY)}")

        effort = task.get("effort")
        if effort is not None and effort not in ALLOWED_EFFORT:
            errors.append(f"{prefix}: effort '{effort}' not in {sorted(ALLOWED_EFFORT)}")

        risk = task.get("risk")
        if risk is not None and risk not in ALLOWED_RISK:
            errors.append(f"{prefix}: risk '{risk}' not in {sorted(ALLOWED_RISK)}")

        updated_at = task.get("updated_at")
        if updated_at is not None:
            if not isinstance(updated_at, str) or not DATE_PATTERN.match(updated_at):
                errors.append(f"{prefix}: updated_at '{updated_at}' must match YYYY-MM-DD")

        acceptance = task.get("acceptance", [])
        evidence = task.get("evidence", [])
        missing_evidence = task.get("missing_evidence", [])

        if priority == "high" and isinstance(acceptance, list) and len(acceptance) == 0:
            errors.append(
                f"{prefix}: high priority task must have at least one acceptance criterion"
            )

        if status == "done" and isinstance(evidence, list) and len(evidence) == 0:
            errors.append(f"{prefix}: done task must have at least one evidence entry")

        links = task.get("links")
        if links is not None:
            if not isinstance(links, dict):
                errors.append(f"{prefix}: 'links' must be an object")
            else:
                for lf in sorted(REQUIRED_LINKS_FIELDS):
                    if lf not in links:
                        errors.append(f"{prefix}: links missing required field '{lf}'")

                for doc_path in links.get("docs", []):
                    if not isinstance(doc_path, str):
                        continue
                    if not _path_exists(doc_path):
                        explained = any(
                            doc_path in me
                            for me in missing_evidence
                            if isinstance(me, str)
                        )
                        if not explained:
                            errors.append(
                                f"{prefix}: links.docs '{doc_path}' does not exist "
                                f"and is not explained in missing_evidence"
                            )

        for ev in evidence:
            if not isinstance(ev, str):
                continue
            if ev.startswith("docs/") and not _path_exists(ev):
                explained = any(
                    ev in me for me in missing_evidence if isinstance(me, str)
                )
                if not explained:
                    errors.append(
                        f"{prefix}: evidence path '{ev}' does not exist "
                        f"and is not explained in missing_evidence"
                    )

    return errors


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <path-to-index.json>", file=sys.stderr)
        sys.exit(1)

    arg = sys.argv[1]
    index_path = arg if os.path.isabs(arg) else os.path.join(REPO_ROOT, arg)

    errors = validate_task_index(index_path)

    if errors:
        print(f"\n--- Task Index Validation Errors ({len(errors)}) ---", file=sys.stderr)
        for error in errors:
            print(f"  ERROR: {error}", file=sys.stderr)
        print(f"\nValidation failed: {len(errors)} error(s).", file=sys.stderr)
        sys.exit(1)

    print("Task index validation passed (0 errors).")


if __name__ == "__main__":
    main()
