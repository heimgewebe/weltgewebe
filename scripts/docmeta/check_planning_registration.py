import argparse
import glob
import json
import os
import re
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

def _read_text(rel_path):
    full_path = os.path.join(REPO_ROOT, rel_path)
    if not os.path.exists(full_path):
        return None, f"file not found: {rel_path}"
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read(), None
    except OSError as e:
        return None, f"cannot read file: {e}"

def parse_frontmatter(text):
    """
    Implements a basic frontmatter parser for the required fields:
    id, title, doc_type, status, relations
    """
    if not text.startswith("---"):
        return None

    parts = text.split("\n---", 1)
    if len(parts) < 2:
        return None

    frontmatter_block = parts[0][3:] # Skip initial '---'

    meta = {
        "status": None,
        "doc_type": None,
        "id": None,
        "relations": []
    }

    # Extract scalar fields
    for field in ["status", "doc_type", "id"]:
        match = re.search(fr"^{field}:\s*(.+)$", frontmatter_block, re.MULTILINE)
        if match:
            meta[field] = match.group(1).strip()

    # Extract relations
    in_relations = False
    for line in frontmatter_block.splitlines():
        if line.startswith("relations:"):
            in_relations = True
            continue
        if in_relations:
            if line and not line.startswith((" ", "-")):
                in_relations = False
                continue
            if "target:" in line:
                target = line.split("target:", 1)[1].strip().strip('"\'')
                meta["relations"].append(target)

    return meta

def get_registered_paths():
    """Extract registered paths from index.json, board.md, and roadmap.md"""
    registered = set()
    errors = []

    # 1. docs/tasks/index.json
    index_text, err = _read_text("docs/tasks/index.json")
    if err:
        errors.append(("CONTROL_FILE_MISSING", "docs/tasks/index.json", err))
    else:
        try:
            data = json.loads(index_text)
            for task in data.get("tasks", []):
                for path in task.get("evidence", []):
                    registered.add(path)
                for path in task.get("missing_evidence", []):
                    # Note: missing_evidence might be free text, but we try to match paths
                    words = path.split()
                    for word in words:
                        if word.startswith("docs/") or word.startswith("scripts/"):
                            registered.add(word)
        except json.JSONDecodeError as e:
            errors.append(("CONTROL_FILE_PARSE_ERROR", "docs/tasks/index.json", f"Invalid JSON: {e}"))

    # 2. docs/tasks/board.md
    board_text, err = _read_text("docs/tasks/board.md")
    if err:
        errors.append(("CONTROL_FILE_MISSING", "docs/tasks/board.md", err))
    else:
        # Extract paths in backticks or just docs/ paths
        matches = re.findall(r'`(docs/[^`]+)`', board_text)
        registered.update(matches)
        matches2 = re.findall(r'(docs/[^\s,]+)', board_text)
        for m in matches2:
            if m.endswith('`'): m = m[:-1]
            registered.add(m)

    # 3. docs/roadmap.md
    roadmap_text, err = _read_text("docs/roadmap.md")
    if err:
        errors.append(("CONTROL_FILE_MISSING", "docs/roadmap.md", err))
    else:
        matches = re.findall(r'\]\(([^)]+)\)', roadmap_text)
        for match in matches:
            if match.endswith('.md'):
                if not match.startswith('docs/'):
                    # Relative links from roadmap.md need to be resolved to docs/
                    registered.add(f"docs/{match}")
                else:
                    registered.add(match)
        # Also plain paths
        matches2 = re.findall(r'`(docs/[^`]+)`', roadmap_text)
        registered.update(matches2)

    # Self-register control files
    registered.add("docs/tasks/index.json")
    registered.add("docs/tasks/board.md")
    registered.add("docs/roadmap.md")

    return registered, errors

def get_all_planning_artifacts():
    """Find all potential planning artifacts"""
    patterns = [
        "docs/blueprints/*.md",
        "docs/roadmap.md",
        "docs/reports/*status*.md",
        "docs/reports/*roadmap*.md",
        "docs/reports/*next-step*.md",
        "docs/specs/*.md"
    ]

    files = set()
    for pattern in patterns:
        matched = glob.glob(os.path.join(REPO_ROOT, pattern))
        for path in matched:
            rel_path = os.path.relpath(path, REPO_ROOT)

            # Hard exclusions
            if rel_path.startswith("docs/_generated/"): continue
            if rel_path.startswith("docs/proofs/"): continue
            if rel_path.startswith("docs/runbooks/"): continue
            if rel_path.startswith("docs/reference/"): continue
            if rel_path.startswith("docs/adr/"): continue
            if rel_path.startswith("docs/policies/"): continue
            if rel_path.startswith("docs/process/"): continue
            if rel_path.startswith("docs/claims/"): continue
            if rel_path == "docs/deploy/CHANGELOG.md": continue

            files.add(rel_path)

    return sorted(list(files))

def is_registered(rel_path, registered_paths, meta):
    """Check if an artifact is properly registered"""
    # 1-3. Direct path references in control files
    if rel_path in registered_paths:
        return True

    # 4. Frontmatter relation to task-control artifact
    if meta and "relations" in meta:
        for relation in meta["relations"]:
            if relation.startswith("docs/tasks/") or relation == "docs/roadmap.md":
                return True

    # 5. Marked as deprecated, superseded, archived, or deferred
    if meta and meta.get("status") in ["deprecated", "superseded", "archived", "deferred"]:
        return True

    return False

def is_planning_doc(rel_path, meta):
    """Determine if a doc in a generic dir like specs/ is actually a planning doc"""
    if "blueprints/" in rel_path or "roadmap" in rel_path or "status" in rel_path:
        return True

    if not meta:
        return False

    doc_type = meta.get("doc_type")
    if doc_type in ["roadmap", "plan", "status", "status-matrix"]:
        return True

    # Specs are not planning docs merely because they are draft/open.
    if rel_path.startswith("docs/specs/"):
        return False

    status = meta.get("status")
    if status in ["draft", "open", "in-progress"]:
        return True

    return False

def run_checks():
    registered_paths, control_errors = get_registered_paths()
    artifacts = get_all_planning_artifacts()

    findings = []


    for code, path, reason in control_errors:
        findings.append({
            "code": code,
            "path": path,
            "reason": reason,
            "suggestion": "Ensure the control file exists and is valid."
        })

    for rel_path in artifacts:

        text, err = _read_text(rel_path)
        if err:
            findings.append({
                "code": "CONTROL_FILE_MISSING" if rel_path in ["docs/tasks/index.json", "docs/tasks/board.md", "docs/roadmap.md"] else "FILE_READ_ERROR",
                "path": rel_path,
                "reason": err,
                "suggestion": "Ensure the file exists and is readable."
            })
            continue

        meta = parse_frontmatter(text)

        # Determine if it's really a planning doc
        if not is_planning_doc(rel_path, meta):
            continue

        if not is_registered(rel_path, registered_paths, meta):
            findings.append({
                "code": "UNREGISTERED_PLANNING_ARTIFACT",
                "path": rel_path,
                "reason": "Planning artifact is active but not registered in task-control or roadmap.",
                "suggestion": "Add path to docs/tasks/index.json, docs/roadmap.md, or add a 'relates_to' frontmatter relation to a task doc."
            })

    return findings

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Guard against unregistered blueprints and planning artifacts."
    )
    parser.add_argument("--strict", action="store_true", help="Exit 1 if findings exist.")
    args = parser.parse_args(argv)

    findings = run_checks()

    if not findings:
        print("Agent-planning registration check passed (0 issues).")
        return 0

    print(f"\n--- Planning Artifact Registration Drift ({len(findings)}) ---", file=sys.stderr)
    for f in findings:
        print(f"[{f['code']}] {f['path']}", file=sys.stderr)
        print(f"  Reason: {f['reason']}", file=sys.stderr)
        print(f"  Fix:    {f['suggestion']}\n", file=sys.stderr)

    print(f"Check finished with {len(findings)} issue(s).", file=sys.stderr)

    if args.strict:
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
