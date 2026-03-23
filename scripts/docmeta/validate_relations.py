"""
Relations Guard — validates the structural and semantic integrity of relations[].

Checks:
1. Structure: relations is a list of objects with required keys (type, target)
2. Allowed types: relates_to, depends_on, supersedes
3. Target validity: target must reference an existing file (repo-root-relative path)
4. No duplicates: identical (type, target) pairs are rejected
5. No self-references: a document must not point to itself
6. No absolute paths or IDs in target
"""

import os
import sys

from scripts.docmeta.docmeta import REPO_ROOT

ALLOWED_TYPES = {"relates_to", "depends_on", "supersedes"}


def validate_relations(file_path, frontmatter):
    """
    Validate the relations[] field of a single document.

    Args:
        file_path: repo-root-relative path of the document (e.g. 'docs/vision.md')
        frontmatter: parsed frontmatter dict

    Returns:
        list of error strings (empty = valid)
    """
    errors = []

    relations = frontmatter.get("relations")

    # relations field not present → OK (optional)
    if relations is None:
        return errors

    # relations must be a list
    if not isinstance(relations, list):
        errors.append(f"{file_path}: 'relations' must be a list, got {type(relations).__name__}")
        return errors

    # Empty list is explicitly allowed
    if len(relations) == 0:
        return errors

    seen = set()

    for i, entry in enumerate(relations):
        prefix = f"{file_path}: relations[{i}]"

        # Each entry must be a dict (parsed from block list items)
        if not isinstance(entry, dict):
            errors.append(f"{prefix}: expected object with 'type' and 'target', got {type(entry).__name__}: {entry!r}")
            continue

        # Required keys
        rel_type = entry.get("type")
        target = entry.get("target")

        if rel_type is None:
            errors.append(f"{prefix}: missing required key 'type'")
        elif not isinstance(rel_type, str) or not rel_type.strip():
            errors.append(f"{prefix}: 'type' must be a non-empty string")
        elif rel_type not in ALLOWED_TYPES:
            errors.append(f"{prefix}: unknown relation type '{rel_type}' (allowed: {', '.join(sorted(ALLOWED_TYPES))})")

        if target is None:
            errors.append(f"{prefix}: missing required key 'target'")
        elif not isinstance(target, str) or not target.strip():
            errors.append(f"{prefix}: 'target' must be a non-empty string")
        else:
            # No absolute paths
            if target.startswith("/"):
                errors.append(f"{prefix}: target must be repo-root-relative, not absolute: '{target}'")

            # Target must exist as a file
            abs_target = os.path.join(REPO_ROOT, target)
            if not os.path.isfile(abs_target):
                errors.append(f"{prefix}: target '{target}' does not exist")

            # No self-references
            if target == file_path:
                errors.append(f"{prefix}: self-reference detected (document points to itself)")

        # Duplicate check
        if rel_type and target:
            pair = (rel_type, target)
            if pair in seen:
                errors.append(f"{prefix}: duplicate relation ({rel_type}, {target})")
            seen.add(pair)

        # Extra keys check
        extra_keys = set(entry.keys()) - {"type", "target"}
        if extra_keys:
            errors.append(f"{prefix}: unexpected keys {extra_keys}")

    return errors


def extract_relations_from_content(content):
    """
    Parse structured relations[] from YAML frontmatter content string.

    Returns list of dicts preserving ALL keys found per relation entry —
    not just type/target. This ensures downstream validation can detect
    unexpected keys, missing keys, and structural issues in real files.
    """
    relations = []
    if not content.startswith("---"):
        return relations

    parts = content.split("---", 2)
    if len(parts) < 3:
        return relations

    fm_str = parts[1]
    lines = fm_str.strip().split("\n")
    in_relations = False
    current_entry = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Detect top-level key (not indented)
        if not line[0:1] in (" ", "\t") and ":" in stripped:
            key = stripped.split(":")[0].strip()
            if key == "relations":
                in_relations = True
                # Handle inline empty: relations: []
                val = stripped.split(":", 1)[1].strip()
                if val == "[]":
                    in_relations = False
            else:
                in_relations = False
            # Flush pending entry before leaving relations block
            if current_entry:
                relations.append(current_entry)
                current_entry = None
            continue

        if in_relations:
            if stripped.startswith("- "):
                # New list item — flush previous entry
                if current_entry:
                    relations.append(current_entry)
                    current_entry = None

                item = stripped[2:]  # strip leading "- "
                if ":" in item:
                    key = item.split(":", 1)[0].strip()
                    val = item.split(":", 1)[1].strip()
                    current_entry = {key: val}
                else:
                    # Bare list item (not a dict) — record as non-dict entry
                    relations.append(item)
            elif ":" in stripped and current_entry is not None:
                # Continuation key within the current dict entry
                key = stripped.split(":", 1)[0].strip()
                val = stripped.split(":", 1)[1].strip()
                current_entry[key] = val

    # Flush any pending entry
    if current_entry:
        relations.append(current_entry)

    return relations


def main():
    errors = []

    # Validate all directories that carry relations: in their frontmatter.
    # This matches the repo-wide relations model documented in
    # architecture/docmeta.schema.md.
    scan_dirs = ["docs", "architecture", "runtime", "runbooks"]

    for scan_dir in scan_dirs:
        dir_path = os.path.join(REPO_ROOT, scan_dir)
        if not os.path.isdir(dir_path):
            continue
        for root, dirs, files in os.walk(dir_path):
            if "_generated" in root:
                continue
            for file in files:
                if not file.endswith(".md"):
                    continue

                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, REPO_ROOT)

                try:
                    with open(abs_path, "r", encoding="utf-8") as f:
                        content = f.read()
                except Exception as e:
                    errors.append(f"{rel_path}: cannot read file: {e}")
                    continue

                relations = extract_relations_from_content(content)

                # Build a frontmatter-like dict for validation
                fm = {"relations": relations}
                file_errors = validate_relations(rel_path, fm)
                errors.extend(file_errors)

    if errors:
        print(f"\n--- Relations validation errors ({len(errors)}) ---", file=sys.stderr)
        for error in errors:
            print(f"  ERROR: {error}", file=sys.stderr)
        print("\nRelations validation failed.", file=sys.stderr)
        sys.exit(1)

    print("Relations validation passed (0 errors).")


if __name__ == "__main__":
    main()
