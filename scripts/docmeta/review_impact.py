import os
import sys

from scripts.docmeta.docmeta import REPO_ROOT, parse_repo_index, parse_frontmatter, parse_review_policy

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 -m scripts.docmeta.review_impact <modified_file_path>", file=sys.stderr)
        sys.exit(1)

    modified_file = sys.argv[1]
    # Normalize to relative path to REPO_ROOT if it's absolute
    if os.path.isabs(modified_file):
        try:
            modified_file = os.path.relpath(modified_file, REPO_ROOT)
        except ValueError:
            pass

    try:
        policy = parse_review_policy()
        strict_mode = policy.get('strict_manifest', False)
        repo_index = parse_repo_index(strict_manifest=strict_mode)
    except ValueError as e:
        print(f"Error parsing manifest/policy: {e}", file=sys.stderr)
        sys.exit(1)

    # Build dependency graph: id -> list of dependent docs (file paths)
    dependencies = {}
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

            for dep in depends_on:
                if dep not in dependencies:
                    dependencies[dep] = []
                dependencies[dep].append(rel_file_path)

    if modified_file not in file_to_id:
        print(f"Warning: '{modified_file}' is not a canonical doc or has no valid ID.")
        sys.exit(0)

    modified_id = file_to_id[modified_file]

    # BFS to find all transitive dependents
    visited = set()
    queue = [modified_id]

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

    if not impacted_files:
        print(f"No canonical docs depend on '{modified_file}'.")
    else:
        print(f"Review Impact for '{modified_file}':")
        for f in sorted(list(impacted_files)):
            print(f"- {f} (needs_review)")

if __name__ == '__main__':
    main()
