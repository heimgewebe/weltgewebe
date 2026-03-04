import os
import sys
import json

from scripts.docmeta.docmeta import REPO_ROOT, parse_repo_index, parse_frontmatter, parse_review_policy, normalize_list_field

def main():
    try:
        policy = parse_review_policy()
        strict_mode = policy.get('strict_manifest', False)
        repo_index = parse_repo_index(strict_manifest=strict_mode)
    except ValueError as e:
        print(f"Error parsing manifest/policy: {e}", file=sys.stderr)
        sys.exit(1)

    docs_by_id = {}
    docs_without_id = []
    seen_ids = {}
    duplicate_errors = []
    duplicate_warnings = []

    mode = policy.get('mode', 'warn')

    for zone_name, zone_data in sorted(repo_index.get('zones', {}).items()):
        for doc_file in sorted(zone_data.get('canonical_docs', [])):
            rel_zone_path = zone_data.get('path', '')
            rel_file_path = os.path.normpath(os.path.join(rel_zone_path, doc_file))
            file_path = os.path.normpath(os.path.join(REPO_ROOT, rel_file_path))

            if not os.path.exists(file_path):
                continue

            frontmatter = parse_frontmatter(file_path)
            if frontmatter:
                doc_id = frontmatter.get('id', '')

                if doc_id:
                    if doc_id in seen_ids:
                        prev_file = seen_ids[doc_id]
                        if mode in ('strict', 'fail-closed'):
                            duplicate_errors.append(f"Error: Duplicate ID '{doc_id}' found in '{prev_file}' and '{rel_file_path}'.")
                        else:
                            duplicate_warnings.append(f"Warning: Duplicate ID '{doc_id}' found in '{prev_file}' and '{rel_file_path}'. Overwriting.")
                    seen_ids[doc_id] = rel_file_path

                status = frontmatter.get('status', '')
                organ = frontmatter.get('organ', '')
                role = frontmatter.get('role', '')
                last_reviewed = frontmatter.get('last_reviewed', '')

                depends_on = normalize_list_field(frontmatter.get('depends_on', []))
                verifies_with = normalize_list_field(frontmatter.get('verifies_with', []))

                doc_entry = {
                    "id": doc_id,
                    "role": role,
                    "organ": organ,
                    "status": status,
                    "last_reviewed": last_reviewed,
                    "depends_on": depends_on,
                    "verifies_with": verifies_with,
                    "path": rel_file_path
                }
                if doc_id:
                    docs_by_id[doc_id] = doc_entry
                else:
                    docs_without_id.append(doc_entry)

    for warning in sorted(duplicate_warnings):
        print(warning, file=sys.stderr)

    if duplicate_errors:
        for error in sorted(duplicate_errors):
            print(error, file=sys.stderr)
        sys.exit(1)

    docs = list(docs_by_id.values()) + docs_without_id

    # Stable sort by id, putting empty/None ids at the end
    docs.sort(key=lambda x: (x.get('id') in (None, ''), x.get('id', '')))

    output_data = {
        "docs": docs
    }

    # Save artifact
    artifacts_dir = os.path.join(REPO_ROOT, "artifacts", "docmeta")
    os.makedirs(artifacts_dir, exist_ok=True)

    out_path = os.path.join(artifacts_dir, 'docs.index.json')

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2)
        f.write("\n")

    print("Docs index exported successfully.")

if __name__ == '__main__':
    main()
