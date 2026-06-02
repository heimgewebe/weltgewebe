"""
Planning Registration Guard.

Checks that planning artifacts (blueprints, roadmaps, status docs) are
registered in task-control or roadmap documents.

Config: scripts/docmeta/planning_registration.yml
  PyYAML is used for config parsing. It is available on ubuntu-latest CI
  and in the project Python environment (verified before this dependency
  was introduced).

Modes:
  report  — print findings, exit 0 (default)
  warn    — print findings as GitHub Actions ::warning annotations, exit 0
  strict  — print findings, exit 1 when findings exist

--strict is kept as a backwards-compatible alias for --mode strict.
"""

import argparse
import glob
import json
import os
import re
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "planning_registration.yml")

# ── defaults (fallback when config is missing or invalid) ────────────────────

_DEFAULT_CONFIG = {
    "version": 1,
    "scan_patterns": [
        "docs/blueprints/*.md",
        "docs/roadmap.md",
        "docs/reports/*status*.md",
        "docs/reports/*roadmap*.md",
        "docs/reports/*next-step*.md",
        "docs/specs/*.md",
    ],
    "excluded_prefixes": [
        "docs/_generated/",
        "docs/proofs/",
        "docs/runbooks/",
        "docs/reference/",
        "docs/adr/",
        "docs/policies/",
        "docs/process/",
        "docs/claims/",
    ],
    "excluded_paths": ["docs/deploy/CHANGELOG.md"],
    "planning_doc_types": ["roadmap", "plan", "status", "status-matrix"],
    "terminal_statuses": ["deprecated", "superseded", "archived", "deferred"],
    "registration_sources": {
        "task_index": "docs/tasks/index.json",
        "board": "docs/tasks/board.md",
        "roadmap": "docs/roadmap.md",
    },
}


# ── config loading ────────────────────────────────────────────────────────────

def load_config():
    """Load and validate planning_registration.yml.

    Returns (config_dict, finding_or_None). On missing/invalid config,
    returns (_DEFAULT_CONFIG, finding) so scanning continues with defaults.
    """
    if not os.path.exists(CONFIG_PATH):
        return _DEFAULT_CONFIG, {
            "code": "CONFIG_MISSING",
            "path": "scripts/docmeta/planning_registration.yml",
            "reason": "Config file not found; scanning continues with built-in defaults.",
            "suggestion": "Create scripts/docmeta/planning_registration.yml.",
            "source": "planning-registration",
        }
    try:
        import yaml  # PyYAML — verified available in CI before introduction
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        if not isinstance(raw, dict):
            raise ValueError("Config root must be a YAML mapping.")
        for k in (
            "version", "scan_patterns", "excluded_prefixes",
            "planning_doc_types", "terminal_statuses", "registration_sources",
        ):
            if k not in raw:
                raise ValueError(f"Missing required key: '{k}'")
        return raw, None
    except Exception as exc:
        return _DEFAULT_CONFIG, {
            "code": "CONFIG_INVALID",
            "path": "scripts/docmeta/planning_registration.yml",
            "reason": f"Config invalid: {exc}",
            "suggestion": "Fix scripts/docmeta/planning_registration.yml.",
            "source": "planning-registration",
        }


# ── file I/O ──────────────────────────────────────────────────────────────────

def _read_text(rel_path):
    full_path = os.path.join(REPO_ROOT, rel_path)
    if not os.path.exists(full_path):
        return None, f"file not found: {rel_path}"
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read(), None
    except OSError as e:
        return None, f"cannot read file: {e}"


# ── scalar frontmatter parser ─────────────────────────────────────────────────

_SCALAR_RE = re.compile(r"^(status|doc_type):\s*(.+)$", re.MULTILINE)


def _parse_scalars(text):
    """Extract status and doc_type from frontmatter content string.

    Kept as a minimal local parser for scalar fields only (Path A: relations
    are delegated to the centralized relations_parser). Handles quoted scalars.
    """
    if not text or not text.startswith("---"):
        return {}
    parts = text.split("\n---", 1)
    if len(parts) < 2:
        return {}
    fm = parts[0][3:]
    result = {}
    for m in _SCALAR_RE.finditer(fm):
        result[m.group(1)] = m.group(2).strip().strip("\"'")
    return result


# ── relations (centralized parser) ───────────────────────────────────────────

def _get_relations(text):
    """Extract relations via the canonical centralized parser.

    Returns list of dicts (or bare strings for non-dict list items).
    """
    from scripts.docmeta.relations_parser import extract_relations_from_content
    return extract_relations_from_content(text)


# ── registered paths ──────────────────────────────────────────────────────────

def get_registered_paths(config):
    """Build the set of registered paths from task-control and roadmap sources."""
    sources = config.get("registration_sources", _DEFAULT_CONFIG["registration_sources"])
    task_index_path = sources.get("task_index", "docs/tasks/index.json")
    board_path = sources.get("board", "docs/tasks/board.md")
    roadmap_path = sources.get("roadmap", "docs/roadmap.md")

    registered = set()
    errors = []

    index_text, err = _read_text(task_index_path)
    if err:
        errors.append(("CONTROL_FILE_MISSING", task_index_path, err))
    else:
        try:
            data = json.loads(index_text)
            for task in data.get("tasks", []):
                for path in task.get("evidence", []):
                    registered.add(path)
                for phrase in task.get("missing_evidence", []):
                    for word in phrase.split():
                        if word.startswith("docs/") or word.startswith("scripts/"):
                            registered.add(word)
        except json.JSONDecodeError as e:
            errors.append(("CONTROL_FILE_PARSE_ERROR", task_index_path, f"Invalid JSON: {e}"))

    board_text, err = _read_text(board_path)
    if err:
        errors.append(("CONTROL_FILE_MISSING", board_path, err))
    else:
        for m in re.findall(r'`(docs/[^`]+)`', board_text):
            registered.add(m)
        for m in re.findall(r'(docs/[^\s,`]+)', board_text):
            registered.add(m.rstrip('`'))

    roadmap_text, err = _read_text(roadmap_path)
    if err:
        errors.append(("CONTROL_FILE_MISSING", roadmap_path, err))
    else:
        for link in re.findall(r'\]\(([^)]+)\)', roadmap_text):
            if link.endswith('.md'):
                registered.add(link if link.startswith('docs/') else f"docs/{link}")
        for m in re.findall(r'`(docs/[^`]+)`', roadmap_text):
            registered.add(m)

    registered.add(task_index_path)
    registered.add(board_path)
    registered.add(roadmap_path)

    return registered, errors


# ── artifact discovery ────────────────────────────────────────────────────────

def get_all_planning_artifacts(config):
    """Discover candidate planning artifacts using config scan patterns."""
    patterns = config.get("scan_patterns", _DEFAULT_CONFIG["scan_patterns"])
    excluded_prefixes = tuple(
        config.get("excluded_prefixes", _DEFAULT_CONFIG["excluded_prefixes"])
    )
    excluded_paths = set(config.get("excluded_paths", _DEFAULT_CONFIG["excluded_paths"]))

    files = set()
    for pattern in patterns:
        for path in glob.glob(os.path.join(REPO_ROOT, pattern)):
            rel = os.path.relpath(path, REPO_ROOT)
            if rel.startswith(excluded_prefixes):
                continue
            if rel in excluded_paths:
                continue
            files.add(rel)

    return sorted(files)


# ── classification ────────────────────────────────────────────────────────────

def is_registered(rel_path, registered_paths, meta, relations, config):
    """True if the artifact is registered in task-control or has terminal status."""
    if rel_path in registered_paths:
        return True
    for rel in relations:
        target = rel.get("target", "") if isinstance(rel, dict) else str(rel)
        if target.startswith("docs/tasks/") or target == "docs/roadmap.md":
            return True
    terminal = set(config.get("terminal_statuses", _DEFAULT_CONFIG["terminal_statuses"]))
    if meta.get("status") in terminal:
        return True
    return False


def is_planning_doc(rel_path, meta, config):
    """True if this file is subject to registration requirements."""
    if "blueprints/" in rel_path or "roadmap" in rel_path or "status" in rel_path:
        return True
    planning_types = set(
        config.get("planning_doc_types", _DEFAULT_CONFIG["planning_doc_types"])
    )
    doc_type = meta.get("doc_type")
    if doc_type in planning_types:
        return True
    # docs/specs/ files are not planning unless they carry an explicit planning doc_type.
    if rel_path.startswith("docs/specs/"):
        return False
    status = meta.get("status")
    if status in ("draft", "open", "in-progress"):
        return True
    return False


# ── check runner ──────────────────────────────────────────────────────────────

def run_checks(config=None):
    """Run all planning-registration checks. Returns list of finding dicts.

    If config is None, loads config internally (config findings are silently
    discarded; use main() to surface them).
    """
    if config is None:
        config, _ = load_config()

    registered_paths, control_errors = get_registered_paths(config)
    artifacts = get_all_planning_artifacts(config)

    findings = []
    for code, path, reason in control_errors:
        findings.append({
            "code": code,
            "path": path,
            "reason": reason,
            "suggestion": "Ensure the control file exists and is valid.",
            "source": "planning-registration",
        })

    for rel_path in artifacts:
        text, err = _read_text(rel_path)
        if err:
            findings.append({
                "code": "FILE_READ_ERROR",
                "path": rel_path,
                "reason": err,
                "suggestion": "Ensure the file exists and is readable.",
                "source": "planning-registration",
            })
            continue

        meta = _parse_scalars(text)
        relations = _get_relations(text)

        if not is_planning_doc(rel_path, meta, config):
            continue

        if not is_registered(rel_path, registered_paths, meta, relations, config):
            findings.append({
                "code": "UNREGISTERED_PLANNING_ARTIFACT",
                "path": rel_path,
                "reason": "Planning artifact is active but not registered in task-control or roadmap.",
                "suggestion": (
                    "Add path to docs/tasks/index.json evidence, docs/tasks/board.md, "
                    "or docs/roadmap.md; or add a frontmatter 'relates_to' relation "
                    "targeting docs/tasks/... or docs/roadmap.md."
                ),
                "source": "planning-registration",
            })

    return findings


# ── output helpers ────────────────────────────────────────────────────────────

def _emit_text(findings, mode):
    if not findings:
        print("Agent-planning registration check passed (0 issues).")
        return
    n = len(findings)
    print(f"\n--- Planning Artifact Registration Drift ({n}) ---", file=sys.stderr)
    for f in findings:
        if mode == "warn":
            # GitHub Actions annotation format — stdout so GH picks it up
            print(f"::warning file={f['path']}::[{f['code']}] {f['reason']}")
        else:
            print(f"[{f['code']}] {f['path']}", file=sys.stderr)
            print(f"  Reason: {f['reason']}", file=sys.stderr)
            print(f"  Fix:    {f.get('suggestion', '')}\n", file=sys.stderr)
    print(f"Check finished with {n} issue(s).", file=sys.stderr)


def _emit_json(findings, mode):
    sorted_findings = sorted(
        findings, key=lambda f: (f.get("path", ""), f.get("code", ""))
    )
    output = {
        "findings": sorted_findings,
        "finding_count": len(sorted_findings),
        "format": "json",
        "mode": mode,
        "ok": len(sorted_findings) == 0,
    }
    print(json.dumps(output, sort_keys=True, indent=2))


# ── CLI ───────────────────────────────────────────────────────────────────────

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Guard against unregistered blueprints and planning artifacts."
    )
    parser.add_argument(
        "--mode",
        choices=["report", "warn", "strict"],
        default="report",
        help="report (default, exit 0), warn (GH annotations, exit 0), strict (exit 1 on findings).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Backwards-compatible alias for --mode strict.",
    )
    parser.add_argument(
        "--format",
        dest="fmt",
        choices=["text", "json"],
        default="text",
        help="Output format: text (default) or json.",
    )
    args = parser.parse_args(argv)

    mode = args.mode
    if args.strict:
        mode = "strict"

    config, config_finding = load_config()
    findings = run_checks(config)
    if config_finding:
        findings = [config_finding] + findings

    if args.fmt == "json":
        _emit_json(findings, mode)
    else:
        _emit_text(findings, mode)

    if mode == "strict" and findings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
