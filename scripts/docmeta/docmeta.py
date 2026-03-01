import os
import re

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

def parse_frontmatter(file_path):
    if not os.path.exists(file_path):
        return None

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Robust matching of YAML Frontmatter allowing CRLF, ending at EOF, with spacing
    match = re.match(r'^---\r?\n(.*?)(?:\r?\n---\r?\n|\r?\n---$)', content, re.DOTALL)
    if not match:
        return None

    frontmatter_text = match.group(1)
    data = {}
    for line in frontmatter_text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        if ':' in line:
            key, val = line.split(':', 1)
            key = key.strip()
            val = val.strip()
            if val.startswith('[') and val.endswith(']'):
                val = [item.strip() for item in val[1:-1].split(',') if item.strip()]
            data[key] = val
    return data

def parse_repo_index(manifest_path=None):
    if not manifest_path:
        manifest_path = os.path.join(REPO_ROOT, "manifest", "repo-index.yaml")

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
        if not stripped or stripped.startswith('#') or stripped == '---':
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

def parse_review_policy(policy_path=None):
    if not policy_path:
        policy_path = os.path.join(REPO_ROOT, "manifest", "review-policy.yaml")

    if not os.path.exists(policy_path):
        return None

    with open(policy_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    data = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or stripped == '---':
            continue
        if ':' in line:
            key, val = line.split(':', 1)
            data[key.strip()] = val.strip()

    if 'strict_manifest' in data:
        data['strict_manifest'] = data['strict_manifest'].lower() == 'true'
    else:
        data['strict_manifest'] = False

    return data
