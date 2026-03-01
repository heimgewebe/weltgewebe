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
    current_key = None

    for line in frontmatter_text.splitlines():
        # Keep original indentation to identify block lists
        stripped_line = line.strip()
        if not stripped_line or stripped_line.startswith('#'):
            continue

        if line.startswith(' ') and stripped_line.startswith('- ') and current_key:
            # It's a block list item
            val = stripped_line[2:].strip()
            # Handle quoted strings in lists
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            if isinstance(data[current_key], list):
                data[current_key].append(val)
            else:
                # Convert existing string to list and append
                if data[current_key]:
                    data[current_key] = [data[current_key], val]
                else:
                    data[current_key] = [val]
            continue

        if ':' in line:
            key, val = line.split(':', 1)
            key = key.strip()
            val = val.strip()

            # Reset current key
            current_key = key

            if val.startswith('[') and val.endswith(']'):
                items = [item.strip() for item in val[1:-1].split(',') if item.strip()]
                # Handle quoted strings in inline lists
                for i, item in enumerate(items):
                    if (item.startswith('"') and item.endswith('"')) or (item.startswith("'") and item.endswith("'")):
                        items[i] = item[1:-1]
                val = items
            elif val == '':
                # Initialize empty list for potential block list parsing
                val = []
            elif (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]

            data[key] = val

    # Clean up any empty lists that weren't followed by block list items
    for k, v in data.items():
        if isinstance(v, list) and not v and k not in ['depends_on', 'verifies_with']:
            data[k] = ''

    return data

def parse_repo_index(manifest_path=None, strict_manifest=False):
    if not manifest_path:
        manifest_path = os.environ.get("REPO_INDEX_PATH", os.path.join(REPO_ROOT, "manifest", "repo-index.yaml"))

    if not os.path.exists(manifest_path):
        raise ValueError(f"Repo index file not found: {manifest_path}")

    with open(manifest_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    data = {'zones': {}, 'checks': []}
    current_zone = None
    in_zones = False
    in_checks = False
    in_canonical_docs = False
    has_zones_key = False

    # Track hierarchy implicitly via state to validate indentation.
    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or stripped == '---':
            continue

        indent = len(line) - len(line.lstrip())

        # Validate that no unhandled text exists at indent 0
        if indent == 0:
            if ':' not in stripped:
                raise ValueError(f"Line {line_num}: Expected key-value or key: at root level. Found: '{stripped}'")
            key = stripped.split(':')[0].strip()

            if key == 'zones':
                in_zones = True
                in_checks = False
                has_zones_key = True
            elif key == 'checks':
                in_checks = True
                in_zones = False
            else:
                if strict_manifest:
                    raise ValueError(f"Line {line_num}: Unknown key at root level '{key}' (strict_manifest=True).")
                in_zones = False
                in_checks = False
            continue

        if ':' not in stripped and not stripped.startswith('-'):
            raise ValueError(f"Line {line_num}: Invalid YAML syntax, missing colon or list indicator: '{stripped}'")

        if in_zones:
            if indent == 2:
                if not stripped.endswith(':'):
                    raise ValueError(f"Line {line_num}: Expected zone key ending with colon, found: '{stripped}'")
                current_zone = stripped.rstrip(':')
                data['zones'][current_zone] = {'path': '', 'canonical_docs': []}
                in_canonical_docs = False
            elif indent == 4 and current_zone:
                key = stripped.split(':')[0].strip()
                if key == 'path':
                    data['zones'][current_zone]['path'] = stripped.split(':', 1)[1].strip()
                    in_canonical_docs = False
                elif key == 'canonical_docs':
                    in_canonical_docs = True
                else:
                    in_canonical_docs = False
                    if strict_manifest:
                        raise ValueError(f"Line {line_num}: Unknown key in zone '{current_zone}': '{key}' (strict_manifest=True).")
            elif indent == 6 and in_canonical_docs:
                if not stripped.startswith('- '):
                    raise ValueError(f"Line {line_num}: Expected list item for canonical_docs, found: '{stripped}'")
                doc = stripped.split('-', 1)[1].strip()
                data['zones'][current_zone]['canonical_docs'].append(doc)
            else:
                raise ValueError(f"Line {line_num}: Unexpected indentation level {indent} in zones.")

        elif in_checks:
            if indent == 2:
                if not stripped.startswith('- '):
                    raise ValueError(f"Line {line_num}: Expected list item for checks, found: '{stripped}'")
                check = stripped.split('-', 1)[1].strip()
                data['checks'].append(check)
            else:
                raise ValueError(f"Line {line_num}: Unexpected indentation level {indent} in checks.")

    if not has_zones_key:
        raise ValueError("Missing required key 'zones' in repo-index.")

    if strict_manifest:
        if not data['zones']:
            raise ValueError("The 'zones' section cannot be empty when strict_manifest=True.")
        for z_name, z_data in data['zones'].items():
            if not z_data.get('canonical_docs'):
                raise ValueError(f"Strict Mode: Zone '{z_name}' has no canonical_docs.")

    return data

def parse_review_policy(policy_path=None, strict_manifest=False):
    if not policy_path:
        policy_path = os.environ.get("REVIEW_POLICY_PATH", os.path.join(REPO_ROOT, "manifest", "review-policy.yaml"))

    if not os.path.exists(policy_path):
        raise ValueError(f"Review policy file not found: {policy_path}")

    with open(policy_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    data = {}
    known_keys = {'default_review_cycle_days', 'mode', 'strict_manifest'}

    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or stripped == '---':
            continue

        if ':' not in line:
            raise ValueError(f"Line {line_num}: Invalid YAML syntax, missing colon: '{stripped}'")

        key, val = line.split(':', 1)
        key = key.strip()
        val = val.strip()

        # Unquote if necessary
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]

        data[key] = val

        if strict_manifest and key not in known_keys:
            raise ValueError(f"Line {line_num}: Unknown key '{key}' in review policy (strict_manifest=True).")

    # Validation
    if 'default_review_cycle_days' not in data:
        raise ValueError("Missing required key 'default_review_cycle_days' in review policy.")
    try:
        val = int(data['default_review_cycle_days'])
        if val <= 0:
            raise ValueError
        data['default_review_cycle_days'] = val
    except ValueError:
        raise ValueError(f"Invalid default_review_cycle_days: '{data['default_review_cycle_days']}'. Must be a positive integer.")

    if 'mode' not in data:
        raise ValueError("Missing required key 'mode' in review policy.")
    mode = data['mode'].lower()
    if mode not in ['warn', 'fail']:
        raise ValueError(f"Invalid mode: '{data['mode']}'. Must be 'warn' or 'fail'.")
    data['mode'] = mode

    if 'strict_manifest' in data:
        val = data['strict_manifest'].lower()
        if val not in ['true', 'false']:
            raise ValueError(f"Invalid strict_manifest: '{data['strict_manifest']}'. Must be true or false.")
        data['strict_manifest'] = (val == 'true')
    else:
        data['strict_manifest'] = False

    return data
