import os
import sys
import json

from scripts.docmeta.docmeta import REPO_ROOT, parse_repo_index, parse_frontmatter, parse_review_policy

def main():
    try:
        policy = parse_review_policy()
        strict_mode = policy.get('strict_manifest', False)
        mode = policy.get('mode', 'warn')
        repo_index = parse_repo_index(strict_manifest=strict_mode)
    except ValueError as e:
        print(f"Error parsing manifest/policy: {e}", file=sys.stderr)
        sys.exit(1)

    # Build dependency graph: id -> list of dependencies (edges from a doc to what it depends on)
    # Also reverse graph: id -> list of dependent docs (edges from a doc to docs that depend on it)
    dependencies = {} # id -> list of dependent docs (file paths)
    forward_deps = {} # id -> list of ids it depends on
    id_to_file = {}
    file_to_id = {}

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
            if doc_id:
                id_to_file[doc_id] = rel_file_path
                file_to_id[rel_file_path] = doc_id

            depends_on = frontmatter.get('depends_on', [])
            if isinstance(depends_on, str):
                if depends_on.startswith('[') and depends_on.endswith(']'):
                    depends_on = [d.strip() for d in depends_on[1:-1].split(',') if d.strip()]
                else:
                    depends_on = [depends_on.strip()] if depends_on.strip() else []

            forward_deps[doc_id] = depends_on

            for dep in depends_on:
                if dep not in dependencies:
                    dependencies[dep] = []
                dependencies[dep].append(rel_file_path)

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

    cycles = find_cycles()

    # Calculate transitive impact for all documents
    impact_data = {}
    for doc_id, filepath in id_to_file.items():
        visited = set()
        queue = [doc_id]
        impacted_files = set()

        while queue:
            current_id = queue.pop(0)
            if current_id in visited:
                continue
            visited.add(current_id)

            dependents = dependencies.get(current_id, [])
            for dep_file in dependents:
                impacted_files.add(dep_file)
                if dep_file in file_to_id:
                    queue.append(file_to_id[dep_file])

        impact_data[doc_id] = {
            "file": filepath,
            "transitive_impacts": sorted(list(impacted_files))
        }

    # Save artifacts
    artifacts_dir = os.path.join(REPO_ROOT, "artifacts", "docmeta")
    os.makedirs(artifacts_dir, exist_ok=True)

    json_path = os.path.join(artifacts_dir, "impact.json")
    md_path = os.path.join(artifacts_dir, "impact.md")

    report_data = {
        "cycles": cycles,
        "impacts": impact_data
    }

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, indent=2)

    with open(md_path, 'w', encoding='utf-8') as f:
        f.write("# Dependency Graph & Impact Report\n\n")
        if cycles:
            f.write("## ⚠️ Cycles Detected\n\n")
            for cycle in cycles:
                f.write(f"- {' -> '.join(cycle)}\n")
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
