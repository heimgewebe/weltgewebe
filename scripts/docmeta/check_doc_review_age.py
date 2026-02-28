import os
import sys
import datetime
import re

def parse_review_policy(policy_path):
    if not os.path.exists(policy_path):
        return None

    with open(policy_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    data = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        if ':' in line:
            key, val = line.split(':', 1)
            data[key.strip()] = val.strip()
    return data

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
    policy_path = 'manifest/review-policy.yaml'
    policy = parse_review_policy(policy_path)

    if not policy:
        print(f"Error: Could not parse {policy_path}", file=sys.stderr)
        sys.exit(1)

    default_cycle_days = int(policy.get('default_review_cycle_days', 90))
    mode = policy.get('mode', 'warn').lower()

    manifest_path = 'manifest/repo-index.yaml'
    repo_index = parse_repo_index(manifest_path)

    if not repo_index:
        print(f"Error: Manifest '{manifest_path}' does not exist.")
        sys.exit(1)

    errors = []
    warnings = []

    for zone_name, zone_data in repo_index.get('zones', {}).items():
        zone_path = zone_data.get('path')
        if not zone_path or not os.path.exists(zone_path):
            continue

        for doc_file in zone_data.get('canonical_docs', []):
            file_path = os.path.join(zone_path, doc_file)
            if not os.path.exists(file_path):
                continue

            frontmatter = parse_frontmatter(file_path)
            if not frontmatter:
                continue

            last_reviewed_str = frontmatter.get('last_reviewed')
            if not last_reviewed_str:
                warnings.append(f"Missing 'last_reviewed' in '{file_path}'.")
                continue

            try:
                last_reviewed_date = datetime.datetime.strptime(last_reviewed_str, "%Y-%m-%d").date()
                today = datetime.date.today()
                delta = today - last_reviewed_date

                if delta.days > default_cycle_days:
                    msg = f"Document '{file_path}' review age ({delta.days} days) exceeds default review cycle ({default_cycle_days} days)."
                    if mode == 'fail':
                        errors.append(msg)
                    else:
                        warnings.append(msg)
            except ValueError:
                errors.append(f"Invalid 'last_reviewed' format '{last_reviewed_str}' in '{file_path}'. Must be YYYY-MM-DD.")

    if warnings:
        for warning in warnings:
            print(f"Warning: {warning}", file=sys.stderr)

    if errors:
        for error in errors:
            print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)

    print("Doc review age check passed.")

if __name__ == '__main__':
    main()
