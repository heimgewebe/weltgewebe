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

    output = ["# SYSTEM_MAP\n"]

    for zone_name, zone_data in sorted(repo_index.get('zones', {}).items()):
        output.append(f"## Zone: {zone_name}\n")

        rows = []
        for doc_file in sorted(zone_data.get('canonical_docs', [])):
            rel_zone_path = zone_data.get('path', '')
            rel_file_path = os.path.join(rel_zone_path, doc_file)
            file_path = os.path.join(REPO_ROOT, rel_file_path)

            frontmatter = parse_frontmatter(file_path)
            if frontmatter:
                doc_id = frontmatter.get('id', '')
                status = frontmatter.get('status', '')
                last_reviewed = frontmatter.get('last_reviewed', '')
                depends_on = frontmatter.get('depends_on', [])
                if isinstance(depends_on, str):
                    if depends_on.startswith('[') and depends_on.endswith(']'):
                        depends_on_list = [d.strip() for d in depends_on[1:-1].split(',') if d.strip()]
                        depends_on_str = ', '.join(depends_on_list)
                    else:
                        depends_on_str = depends_on.strip()
                elif isinstance(depends_on, list):
                    depends_on_str = ', '.join(depends_on)
                else:
                    depends_on_str = str(depends_on)

                # Make the file path a markdown link
                file_link = f"[{rel_file_path}]({rel_file_path})"
            else:
                doc_id = "_Missing_"
                status = "_Missing_"
                last_reviewed = "_Missing_"
                depends_on_str = "_Missing_"
                file_link = f"[{rel_file_path}]({rel_file_path})"

            rows.append([doc_id, file_link, status, last_reviewed, depends_on_str])

        headers = ["ID", "File", "Status", "Last Reviewed", "Depends On"]

        header_row = "| " + " | ".join(headers) + " |"
        output.append(header_row)

        sep_row = "|" + "|".join(["---" for _ in headers]) + "|"
        output.append(sep_row)

        for row in rows:
            data_row = "| " + " | ".join(row) + " |"
            output.append(data_row)

        output.append("")

    output.append("## Automated Checks\n")
    checks = repo_index.get('checks', [])
    if checks:
        for check in sorted(checks):
            output.append(f"- [{check}]({check})")
        output.append("")

    out_path = os.path.join(REPO_ROOT, 'SYSTEM_MAP.md')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(output))

if __name__ == '__main__':
    main()
