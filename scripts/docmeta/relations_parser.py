"""
Centralized relations parser — single source of truth for extracting
relations[] from YAML frontmatter content strings.

All tools that need to read relations from markdown files MUST use this
module. No duplicate parsing logic anywhere else in the repository.

Parser Contract (strict YAML subset)
=====================================
This parser supports a **strict YAML subset** — it is NOT a general YAML
parser.

Supported format::

    relations:
      - type: relates_to
        target: docs/foo.md
      - type: supersedes
        target: docs/bar.md

Rules:
- Top-level ``relations:`` key at column 0, followed by a block list.
- Each list item starts with ``- `` (two-space indent + dash + space).
- Continuation keys are indented (spaces or tabs) without a leading dash.
- Key order within an entry is irrelevant (``target`` before ``type`` is fine).
- All keys per entry are preserved (extra keys survive for downstream
  validation).
- Empty list shorthand ``relations: []`` is supported.
- Blank lines and comment lines (``# ...``) inside the relations block are
  ignored.
- Simple surrounding quotes on values (``"val"`` or ``'val'``) are stripped.

Explicitly NOT supported (and not planned):
- Inline mappings ``{type: foo, target: bar}``
- Flow sequences ``[a, b]`` as list items
- Multi-line scalar values
- Nested structures beyond one level of key-value pairs
- Anchors, aliases, or any advanced YAML feature

See also: architecture/docmeta.schema.md (normative schema documentation,
including the decision gate for when to re-evaluate this parser).
"""

import os


def _strip_quotes(value):
    """Strip matching surrounding single or double quotes from a value."""
    if not isinstance(value, str):
        return value
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        return value[1:-1]
    return value


def extract_relations_from_content(content):
    """
    Parse structured relations[] from YAML frontmatter content string.

    Returns a list of entries found in the relations block. Each entry is
    typically a dict preserving ALL keys found per relation entry (not just
    type/target), so downstream validation can detect unexpected keys,
    missing keys, and structural issues in real files.

    Bare list items that are not key-value dicts are returned as-is (strings).
    Consumers must handle non-dict entries defensively (e.g. isinstance check).
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

        # Skip comment lines (both at top level and inside relations block)
        if stripped.startswith("#"):
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
                    val = _strip_quotes(item.split(":", 1)[1].strip())
                    current_entry = {key: val}
                else:
                    # Bare list item (not a dict) — record as non-dict entry
                    relations.append(item)
            elif ":" in stripped and current_entry is not None:
                # Continuation key within the current dict entry
                key = stripped.split(":", 1)[0].strip()
                val = _strip_quotes(stripped.split(":", 1)[1].strip())
                current_entry[key] = val

    # Flush any pending entry
    if current_entry:
        relations.append(current_entry)

    return relations


def collect_file_relations(scan_dirs, repo_root, exclude_generated=True):
    """
    Walk directories and collect all relations from markdown files.

    Args:
        scan_dirs: list of directory names relative to repo_root (e.g. ["docs"])
        repo_root: absolute path to the repository root
        exclude_generated: if True, skip '_generated' directories

    Returns:
        dict mapping repo-root-relative file path -> list of relation dicts
    """
    all_relations = {}
    for scan_dir in scan_dirs:
        dir_path = os.path.join(repo_root, scan_dir)
        if not os.path.isdir(dir_path):
            continue
        for root, dirs, files in os.walk(dir_path):
            if exclude_generated and "_generated" in root:
                continue
            for file in sorted(files):
                if not file.endswith(".md"):
                    continue
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, repo_root)
                try:
                    with open(abs_path, "r", encoding="utf-8") as f:
                        content = f.read()
                except Exception:
                    continue
                rels = extract_relations_from_content(content)
                all_relations[rel_path] = rels
    return all_relations
