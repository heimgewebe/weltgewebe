"""
validate_task_index.py — Validates docs/tasks/index.json against the task-index contract.

This is a hand-coded validator that mirrors the constraints defined in
docs/tasks/schema.json plus business rules. It does not use a generic
JSON-Schema library; schema.json remains the canonical human-readable contract.

Usage:
    python3 -m scripts.docmeta.validate_task_index docs/tasks/index.json

Exit codes:
    0  all checks pass
    1  validation errors found

No files are written. Errors are printed to stderr.
"""
import json
import os
import re
import sys

from scripts.docmeta.docmeta import REPO_ROOT

SCHEMA_PATH = os.path.join(REPO_ROOT, "docs", "tasks", "schema.json")

ALLOWED_AREA = frozenset({"docs", "ci", "api", "web", "infra", "release", "auth", "map", "governance"})
ALLOWED_STATUS = frozenset({"open", "partial", "done", "blocked", "obsolete", "contradicted"})
ALLOWED_PRIORITY = frozenset({"high", "medium", "low"})
ALLOWED_EFFORT = frozenset({"XS", "S", "M", "L", "XL"})
ALLOWED_RISK = frozenset({"low", "medium", "high"})

ID_PATTERN = re.compile(r"^[A-Z]+(-[A-Z]+)*-[0-9]{3}$")
DATE_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
SEMVER_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")

TOP_LEVEL_REQUIRED = frozenset({"schema_version", "curation", "source_files", "tasks"})
TOP_LEVEL_ALLOWED = frozenset({"schema_version", "curation", "source_files", "tasks", "generated_at"})

TASK_REQUIRED = frozenset({
    "id", "title", "area", "status", "priority", "effort", "risk",
    "owner", "evidence", "missing_evidence", "acceptance", "links", "updated_at",
})
TASK_ALLOWED = TASK_REQUIRED

LINKS_REQUIRED = frozenset({"issues", "prs", "docs"})
LINKS_ALLOWED = LINKS_REQUIRED


def _path_exists(rel_path):
    return os.path.isfile(os.path.join(REPO_ROOT, rel_path))


def _check_array_of_strings(value, path, errors):
    if not isinstance(value, list):
        errors.append(f"{path}: must be array[string], got {type(value).__name__}")
        return False
    for i, item in enumerate(value):
        if not isinstance(item, str):
            errors.append(f"{path}[{i}]: must be string, got {type(item).__name__}")
    return True


def _validate_links(links, prefix, missing_evidence, errors):
    if not isinstance(links, dict):
        errors.append(f"{prefix}.links: must be an object, got {type(links).__name__}")
        return

    for f in sorted(LINKS_REQUIRED):
        if f not in links:
            errors.append(f"{prefix}.links: missing required field '{f}'")

    extra_keys = set(links.keys()) - LINKS_ALLOWED
    for k in sorted(extra_keys):
        errors.append(f"{prefix}.links: unexpected key '{k}'")

    for field in ("issues", "prs", "docs"):
        if field in links:
            _check_array_of_strings(links[field], f"{prefix}.links.{field}", errors)

    for doc_path in links.get("docs", []):
        if not isinstance(doc_path, str):
            continue
        if not _path_exists(doc_path):
            explained = any(
                doc_path in me for me in missing_evidence if isinstance(me, str)
            )
            if not explained:
                errors.append(
                    f"{prefix}: links.docs '{doc_path}' does not exist "
                    f"and is not explained in missing_evidence"
                )


def _validate_task(task, index, prefix, errors):
    if not isinstance(task, dict):
        errors.append(f"{prefix}: expected object, got {type(task).__name__}")
        return

    for field in sorted(TASK_REQUIRED):
        if field not in task:
            errors.append(f"{prefix}: missing required field '{field}'")

    extra_keys = set(task.keys()) - TASK_ALLOWED
    for k in sorted(extra_keys):
        errors.append(f"{prefix}: unexpected key '{k}'")

    tid = task.get("id")
    if tid is not None:
        if not isinstance(tid, str) or not ID_PATTERN.match(tid):
            errors.append(
                f"{prefix}: id '{tid}' does not match pattern "
                r"^[A-Z]+(-[A-Z]+)*-[0-9]{3}$"
            )
        if isinstance(tid, str) and tid in index:
            errors.append(
                f"{prefix}: duplicate id '{tid}' (first seen at {index[tid]})"
            )
        elif isinstance(tid, str):
            index[tid] = prefix

    for str_field in ("title", "area", "status", "priority", "effort", "risk", "owner", "updated_at"):
        val = task.get(str_field)
        if val is not None and not isinstance(val, str):
            errors.append(f"{prefix}.{str_field}: must be string, got {type(val).__name__}")

    area = task.get("area")
    if isinstance(area, str) and area not in ALLOWED_AREA:
        errors.append(f"{prefix}.area: '{area}' not in {sorted(ALLOWED_AREA)}")

    status = task.get("status")
    if isinstance(status, str) and status not in ALLOWED_STATUS:
        errors.append(f"{prefix}.status: '{status}' not in {sorted(ALLOWED_STATUS)}")

    priority = task.get("priority")
    if isinstance(priority, str) and priority not in ALLOWED_PRIORITY:
        errors.append(f"{prefix}.priority: '{priority}' not in {sorted(ALLOWED_PRIORITY)}")

    effort = task.get("effort")
    if isinstance(effort, str) and effort not in ALLOWED_EFFORT:
        errors.append(f"{prefix}.effort: '{effort}' not in {sorted(ALLOWED_EFFORT)}")

    risk = task.get("risk")
    if isinstance(risk, str) and risk not in ALLOWED_RISK:
        errors.append(f"{prefix}.risk: '{risk}' not in {sorted(ALLOWED_RISK)}")

    updated_at = task.get("updated_at")
    if isinstance(updated_at, str) and not DATE_PATTERN.match(updated_at):
        errors.append(f"{prefix}.updated_at: '{updated_at}' must match YYYY-MM-DD")

    evidence = task.get("evidence", [])
    missing_evidence = task.get("missing_evidence", [])
    acceptance = task.get("acceptance", [])

    _check_array_of_strings(evidence, f"{prefix}.evidence", errors)
    _check_array_of_strings(missing_evidence, f"{prefix}.missing_evidence", errors)
    _check_array_of_strings(acceptance, f"{prefix}.acceptance", errors)

    if isinstance(priority, str) and priority == "high":
        if isinstance(acceptance, list) and len(acceptance) == 0:
            errors.append(
                f"{prefix}: high priority task must have at least one acceptance criterion"
            )

    if isinstance(status, str) and status == "done":
        if isinstance(evidence, list) and len(evidence) == 0:
            errors.append(f"{prefix}: done task must have at least one evidence entry")

    links = task.get("links")
    if links is not None:
        _validate_links(
            links,
            prefix,
            missing_evidence if isinstance(missing_evidence, list) else [],
            errors,
        )

    for ev in (evidence if isinstance(evidence, list) else []):
        if not isinstance(ev, str):
            continue
        if ev.startswith("docs/") and not _path_exists(ev):
            me = missing_evidence if isinstance(missing_evidence, list) else []
            explained = any(ev in m for m in me if isinstance(m, str))
            if not explained:
                errors.append(
                    f"{prefix}: evidence path '{ev}' does not exist "
                    f"and is not explained in missing_evidence"
                )


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
        errors.append(f"index.json must be a JSON object, got {type(index).__name__}")
        return errors

    # Required top-level fields
    for field in sorted(TOP_LEVEL_REQUIRED):
        if field not in index:
            errors.append(f"Missing required top-level field: '{field}'")

    # No extra top-level keys
    extra_top = set(index.keys()) - TOP_LEVEL_ALLOWED
    for k in sorted(extra_top):
        errors.append(f"Unexpected top-level key: '{k}'")

    # schema_version: string matching semver
    sv = index.get("schema_version")
    if sv is not None:
        if not isinstance(sv, str):
            errors.append(f"schema_version must be string, got {type(sv).__name__}")
        elif not SEMVER_PATTERN.match(sv):
            errors.append(f"schema_version '{sv}' must match X.Y.Z")

    # generated_at: string or null
    ga = index.get("generated_at")
    if ga is not None and not isinstance(ga, str):
        errors.append(f"generated_at must be string or null, got {type(ga).__name__}")

    # curation: string
    curation = index.get("curation")
    if curation is not None and not isinstance(curation, str):
        errors.append(f"curation must be string, got {type(curation).__name__}")

    # source_files: array[string]
    source_files = index.get("source_files")
    if source_files is not None:
        _check_array_of_strings(source_files, "source_files", errors)
        for sf in (source_files if isinstance(source_files, list) else []):
            if isinstance(sf, str) and not _path_exists(sf):
                errors.append(f"source_files: '{sf}' does not exist")

    # tasks: array[object]
    tasks = index.get("tasks")
    if tasks is None:
        return errors

    if not isinstance(tasks, list):
        errors.append(f"'tasks' must be an array, got {type(tasks).__name__}")
        return errors

    seen_ids = {}
    for i, task in enumerate(tasks):
        task_id = task.get("id", f"<unnamed[{i}]>") if isinstance(task, dict) else f"<unnamed[{i}]>"
        _validate_task(task, seen_ids, f"tasks[{i}] ({task_id})", errors)

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
