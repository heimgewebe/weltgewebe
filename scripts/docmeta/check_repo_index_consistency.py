import os
import sys

def parse_repo_index(manifest_path):
    if not os.path.exists(manifest_path):
        return None

    with open(manifest_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    data = {'zones': {}, 'checks': []}
    current_zone = None
    in_zones = False
    in_checks = False
    in_canonical_docs = False

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue

        if line.startswith('zones:'):
            in_zones = True
            in_checks = False
            continue
        elif line.startswith('checks:'):
            in_checks = True
            in_zones = False
            continue

        if in_zones:
            if line.startswith('  ') and not line.startswith('    '):
                current_zone = stripped.rstrip(':')
                data['zones'][current_zone] = {'path': '', 'canonical_docs': []}
                in_canonical_docs = False
            elif line.startswith('    path:'):
                data['zones'][current_zone]['path'] = line.split('path:')[1].strip()
            elif line.startswith('    canonical_docs:'):
                in_canonical_docs = True
            elif in_canonical_docs and line.startswith('      - '):
                doc = line.split('- ')[1].strip()
                data['zones'][current_zone]['canonical_docs'].append(doc)

        elif in_checks:
            if line.startswith('  - '):
                check = line.split('- ')[1].strip()
                data['checks'].append(check)

    return data

def parse_frontmatter(file_path):
    import re
    if not os.path.exists(file_path):
        return None

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
    if not match:
        return None

    frontmatter_text = match.group(1)
    data = {}
    for line in frontmatter_text.split('\n'):
        if ':' in line:
            key, val = line.split(':', 1)
            key = key.strip()
            val = val.strip()
            if val.startswith('[') and val.endswith(']'):
                val = [item.strip() for item in val[1:-1].split(',') if item.strip()]
            data[key] = val
    return data

def main():
    manifest_path = 'manifest/repo-index.yaml'
    repo_index = parse_repo_index(manifest_path)

    if not repo_index:
        print(f"Error: Manifest '{manifest_path}' does not exist.")
        sys.exit(1)

    errors = []
    doc_ids = set()
    dependencies = {}

    for zone_name, zone_data in repo_index.get('zones', {}).items():
        zone_path = zone_data.get('path')
        if not zone_path or not os.path.exists(zone_path):
            errors.append(f"Zone path '{zone_path}' for zone '{zone_name}' does not exist.")
            continue

        for doc_file in zone_data.get('canonical_docs', []):
            file_path = os.path.join(zone_path, doc_file)
            if not os.path.exists(file_path):
                errors.append(f"Canonical doc '{file_path}' does not exist.")
                continue

            frontmatter = parse_frontmatter(file_path)
            if not frontmatter:
                errors.append(f"Frontmatter missing or invalid in '{file_path}'.")
                continue

            doc_id = frontmatter.get('id')
            if not doc_id:
                errors.append(f"Missing 'id' in frontmatter of '{file_path}'.")
            elif doc_id in doc_ids:
                errors.append(f"Duplicate id '{doc_id}' found in '{file_path}'.")
            else:
                doc_ids.add(doc_id)

            if frontmatter.get('status') != 'canonical':
                errors.append(f"Status is not 'canonical' in '{file_path}'.")

            role = frontmatter.get('role')
            if role not in ('norm', 'reality', 'runbooks', 'action'):
                errors.append(f"Invalid role '{role}' in '{file_path}'. Must be norm|reality|runbooks|action.")

            depends_on = frontmatter.get('depends_on', [])
            if isinstance(depends_on, str) and depends_on.startswith('[') and depends_on.endswith(']'):
                depends_on = [d.strip() for d in depends_on[1:-1].split(',') if d.strip()]
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
        if not os.path.exists(check):
            errors.append(f"Check script '{check}' does not exist.")

    if errors:
        for error in errors:
            print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)

    print("Repo index consistency check passed.")

if __name__ == '__main__':
    main()
