import os
import sys
import json

from scripts.docmeta.docmeta import REPO_ROOT, parse_repo_index, parse_frontmatter, parse_review_policy

def main():
    try:
        policy = parse_review_policy()
        strict_mode = policy.get('strict_manifest', False)
        repo_index = parse_repo_index(strict_manifest=strict_mode)
    except ValueError as e:
        print(f"Error parsing manifest/policy: {e}", file=sys.stderr)
        sys.exit(1)

    docs = []

    for zone_name, zone_data in sorted(repo_index.get('zones', {}).items()):
        for doc_file in zone_data.get('canonical_docs', []):
            rel_zone_path = zone_data.get('path', '')
            rel_file_path = os.path.join(rel_zone_path, doc_file)
            file_path = os.path.join(REPO_ROOT, rel_file_path)

            frontmatter = parse_frontmatter(file_path)
            if frontmatter:
                doc_id = frontmatter.get('id', '')
                status = frontmatter.get('status', '')
                organ = frontmatter.get('organ', '')
                role = frontmatter.get('role', '')
                last_reviewed = frontmatter.get('last_reviewed', '')

                depends_on = frontmatter.get('depends_on', [])
                if isinstance(depends_on, str):
                    if depends_on.startswith('[') and depends_on.endswith(']'):
                        depends_on = [d.strip() for d in depends_on[1:-1].split(',') if d.strip()]
                    else:
                        depends_on = [depends_on.strip()] if depends_on.strip() else []

                verifies_with = frontmatter.get('verifies_with', [])
                if isinstance(verifies_with, str):
                    if verifies_with.startswith('[') and verifies_with.endswith(']'):
                        verifies_with = [v.strip() for v in verifies_with[1:-1].split(',') if v.strip()]
                    else:
                        verifies_with = [verifies_with.strip()] if verifies_with.strip() else []

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
                docs.append(doc_entry)

    # Stable sort by id
    docs.sort(key=lambda x: x['id'])

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
