import os
import sys
import json

from scripts.docmeta.docmeta import REPO_ROOT, parse_repo_index, parse_frontmatter, parse_review_policy, normalize_list_field


def _get_depends_on(frontmatter):
    """Get dependency IDs from frontmatter.

    Supports both the direct ``depends_on`` field and the ``relations``
    array (entries with ``type: depends_on``).  The direct field takes
    precedence; the relations fallback ensures compatibility when
    ``parse_frontmatter`` does not handle ``depends_on`` as a block list.
    """
    deps = normalize_list_field(frontmatter.get('depends_on', []))
    if deps:
        return deps
    relations = frontmatter.get('relations', [])
    if isinstance(relations, list):
        for entry in relations:
            if isinstance(entry, dict) and entry.get('type') == 'depends_on':
                target = entry.get('target', '')
                if target:
                    deps.append(target)
    return deps


def main():
    try:
        policy = parse_review_policy()
        strict_mode = policy.get('strict_manifest', False)
        mode = policy.get('mode', 'warn')
        repo_index = parse_repo_index(strict_manifest=strict_mode)
    except ValueError as e:
        print(f"Error parsing manifest/policy: {e}", file=sys.stderr)
        sys.exit(1)

    # Build dependency graph — all edges are ID-based.
    # reverse_deps: id -> list of doc IDs that depend on it
    # forward_deps: id -> list of doc IDs it depends on
    reverse_deps = {}
    forward_deps = {}
    id_to_file = {}
    missing_ids = []

    zones = repo_index.get('zones', {})

    for zone_name, zone_data in zones.items():
        rel_zone_path = zone_data.get('path', '')
        zone_path = os.path.join(REPO_ROOT, rel_zone_path)
        canonical_docs = zone_data.get('canonical_docs', [])

        for doc_file in canonical_docs:
            rel_file_path = os.path.join(rel_zone_path, doc_file)
            file_path = os.path.join(zone_path, doc_file)

            if not os.path.exists(file_path):
                continue

            frontmatter = parse_frontmatter(file_path)
            if not frontmatter:
                continue

            doc_id = frontmatter.get('id')
            if not doc_id:
                missing_ids.append(rel_file_path)
                continue

            id_to_file[doc_id] = rel_file_path

            depends_on = _get_depends_on(frontmatter)

            forward_deps[doc_id] = depends_on

            for dep_id in depends_on:
                if dep_id not in reverse_deps:
                    reverse_deps[dep_id] = []
                reverse_deps[dep_id].append(doc_id)

    # Check for cycles
    def find_cycles():
        cycles = []
        visited = set()
        recursion_stack = []

        def dfs(node):
            visited.add(node)
            recursion_stack.append(node)

            for neighbor in forward_deps.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in recursion_stack:
                    idx = recursion_stack.index(neighbor)
                    cycle = recursion_stack[idx:] + [neighbor]
                    cycles.append(cycle)

            recursion_stack.pop()

        for node in forward_deps:
            if node not in visited:
                dfs(node)

        return cycles

    missing_ids = sorted(list(set(missing_ids)))

    if missing_ids and mode in ['strict', 'fail-closed']:
        print(f"Error: {len(missing_ids)} document(s) missing 'id' in frontmatter:", file=sys.stderr)
        for mid in missing_ids:
            print(f"- {mid}", file=sys.stderr)
        sys.exit(1)

    cycles = find_cycles()

    # Calculate transitive impact for all documents (fully ID-based traversal)
    impact_data = {}
    for doc_id, filepath in id_to_file.items():
        visited = set()
        queue = [doc_id]
        impacted_ids = set()

        while queue:
            current_id = queue.pop(0)
            if current_id in visited:
                continue
            visited.add(current_id)

            for dep_id in reverse_deps.get(current_id, []):
                impacted_ids.add(dep_id)
                queue.append(dep_id)

        impacted_files = sorted(
            id_to_file[i] for i in impacted_ids if i in id_to_file
        )

        impact_data[doc_id] = {
            "file": filepath,
            "transitive_impacts": impacted_files
        }

    # Save artifacts
    artifacts_dir = os.path.join(REPO_ROOT, "artifacts", "docmeta")
    os.makedirs(artifacts_dir, exist_ok=True)

    json_path = os.path.join(artifacts_dir, "impact.json")
    md_path = os.path.join(artifacts_dir, "impact.md")

    report_data = {
        "missing_ids": missing_ids,
        "cycles": cycles,
        "impacts": impact_data
    }

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, indent=2)

    with open(md_path, 'w', encoding='utf-8') as f:
        f.write("# Dependency Graph & Impact Report\n\n")

        f.write("## Missing IDs\n\n")
        if missing_ids:
            f.write("Graph incomplete. The following documents are missing an `id`:\n\n")
            for mid in missing_ids:
                f.write(f"- `{mid}`\n")
            f.write("\n")
        else:
            f.write("No missing ids.\n\n")

        if cycles:
            f.write("## ⚠️ Cycles Detected\n\n")
            for cycle in cycles:
                f.write(f"- {' -> '.join([str(x) for x in cycle])}\n")
            f.write("\n")
        else:
            f.write("## Cycles\n\nNo cycles detected.\n\n")

        f.write("## Transitive Impact\n\n")
        for doc_id in sorted(impact_data.keys()):
            info = impact_data[doc_id]
            f.write(f"### {doc_id} (`{info['file']}`)\n\n")
            if info["transitive_impacts"]:
                for imp in info["transitive_impacts"]:
                    f.write(f"- {imp}\n")
            else:
                f.write("No dependents.\n")
            f.write("\n")

    # Cycle enforcement policy
    if cycles:
        print(f"Warning: {len(cycles)} cycle(s) detected in the dependency graph.", file=sys.stderr)
        if mode in ['strict', 'fail-closed']:
            print("Mode is strict/fail-closed. Failing build.", file=sys.stderr)
            sys.exit(1)

    print("Review impact generation completed successfully.")

if __name__ == '__main__':
    main()
