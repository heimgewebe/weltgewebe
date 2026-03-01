import os
import sys

from scripts.docmeta.docmeta import REPO_ROOT, parse_repo_index, parse_frontmatter, parse_review_policy

def main():
    try:
        policy = parse_review_policy()
        strict_mode = policy.get('strict_manifest', False)
        repo_index = parse_repo_index(strict_manifest=strict_mode)
    except ValueError as e:
        print(f"Error parsing manifest/policy: {e}", file=sys.stderr)
        sys.exit(1)

    errors = []
    warnings = []
    doc_ids = set()
    dependencies = {}

    zones = repo_index.get('zones', {})

    for zone_name, zone_data in zones.items():
        rel_zone_path = zone_data.get('path')
        if not rel_zone_path:
            errors.append(f"Zone '{zone_name}' is missing 'path'.")
            continue

        zone_path = os.path.join(REPO_ROOT, rel_zone_path)
        if not os.path.exists(zone_path):
            errors.append(f"Zone path '{rel_zone_path}' for zone '{zone_name}' does not exist.")
            continue

        canonical_docs = zone_data.get('canonical_docs', [])

        for doc_file in canonical_docs:
            file_path = os.path.join(zone_path, doc_file)
            rel_file_path = os.path.join(rel_zone_path, doc_file)

            if not os.path.exists(file_path):
                errors.append(f"Canonical doc '{rel_file_path}' does not exist.")
                continue

            frontmatter = parse_frontmatter(file_path)
            if not frontmatter:
                errors.append(f"Frontmatter missing or invalid in '{rel_file_path}'.")
                continue

            doc_id = frontmatter.get('id')
            if not doc_id:
                errors.append(f"Missing 'id' in frontmatter of '{rel_file_path}'.")
            elif doc_id in doc_ids:
                errors.append(f"Duplicate id '{doc_id}' found in '{rel_file_path}'.")
            else:
                doc_ids.add(doc_id)

            if frontmatter.get('status') != 'canonical':
                errors.append(f"Status is not 'canonical' in '{rel_file_path}'.")

            owner = frontmatter.get('owner')
            if not owner or not str(owner).strip():
                errors.append(f"Missing or empty 'owner' in frontmatter of '{rel_file_path}'.")

            role = frontmatter.get('role')
            if role not in ('norm', 'reality', 'runbooks', 'action'):
                errors.append(f"Invalid role '{role}' in '{rel_file_path}'. Must be norm|reality|runbooks|action.")

            depends_on = frontmatter.get('depends_on', [])
            if isinstance(depends_on, str):
                if depends_on.startswith('[') and depends_on.endswith(']'):
                    depends_on = [d.strip() for d in depends_on[1:-1].split(',') if d.strip()]
                else:
                    depends_on = [depends_on.strip()] if depends_on.strip() else []

            if not isinstance(depends_on, list):
                depends_on = []

            if doc_id:
                dependencies[doc_id] = depends_on

    for doc_id, deps in dependencies.items():
        for dep in deps:
            if dep not in doc_ids:
                errors.append(f"Document '{doc_id}' depends on non-existent ID '{dep}'.")

    # Check for cycles
    def has_cycle(node, visited, recursion_stack):
        visited.add(node)
        recursion_stack.add(node)

        for neighbor in dependencies.get(node, []):
            if neighbor not in visited:
                if has_cycle(neighbor, visited, recursion_stack):
                    return True
            elif neighbor in recursion_stack:
                return True

        recursion_stack.remove(node)
        return False

    visited = set()
    recursion_stack = set()
    for node in dependencies:
        if node not in visited:
            if has_cycle(node, visited, recursion_stack):
                errors.append("Cycle detected in dependencies.")
                break

    for check in repo_index.get('checks', []):
        check_path = os.path.join(REPO_ROOT, check)
        if not os.path.exists(check_path):
            errors.append(f"Check script '{check}' does not exist.")

    if warnings:
        print(f"\n--- Warnings ({len(warnings)}) ---", file=sys.stderr)
        for warning in warnings:
            print(f"- {warning}", file=sys.stderr)

    if errors:
        print(f"\n--- Errors ({len(errors)}) ---", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        print("\nRepo index consistency check failed.", file=sys.stderr)
        sys.exit(1)

    print(f"Repo index consistency check passed (0 errors, {len(warnings)} warnings).")

if __name__ == '__main__':
    main()
