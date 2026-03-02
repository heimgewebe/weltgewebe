import os
import sys
import datetime
import json

from scripts.docmeta.docmeta import REPO_ROOT, parse_repo_index, parse_frontmatter, parse_review_policy

def main():
    try:
        policy = parse_review_policy()
        strict_mode = policy.get('strict_manifest', False)
        warn_days = policy.get('warn_days', 90)
        fail_days = policy.get('fail_days', 180)
        repo_index = parse_repo_index(strict_manifest=strict_mode)
    except ValueError as e:
        print(f"Error parsing manifest/policy: {e}", file=sys.stderr)
        sys.exit(1)

    output = ["# SYSTEM_MAP\n"]

    for zone_name, zone_data in sorted(repo_index.get('zones', {}).items()):
        output.append(f"## Zone: {zone_name}\n")

        # Collect all documents with id
        docs = []
        for doc_file in zone_data.get('canonical_docs', []):
            rel_zone_path = zone_data.get('path', '')
            rel_file_path = os.path.join(rel_zone_path, doc_file)
            file_path = os.path.join(REPO_ROOT, rel_file_path)

            frontmatter = parse_frontmatter(file_path)
            if frontmatter:
                doc_id = frontmatter.get('id', '')
                docs.append((doc_id, frontmatter, rel_file_path))
            else:
                docs.append(('_Missing_', None, rel_file_path))

        # Stable sort by id
        docs.sort(key=lambda x: x[0])

        rows = []
        for doc_id, frontmatter, rel_file_path in docs:
            if frontmatter:
                status = frontmatter.get('status', '')
                organ = frontmatter.get('organ', '')
                role = frontmatter.get('role', '')
                last_reviewed_str = frontmatter.get('last_reviewed', '')

                # Freshness status
                freshness_status = "unknown"
                if last_reviewed_str:
                    try:
                        last_reviewed_date = datetime.datetime.strptime(last_reviewed_str, "%Y-%m-%d").date()
                        today = datetime.date.today()
                        delta = today - last_reviewed_date
                        if delta.days > fail_days:
                            freshness_status = "fail"
                        elif delta.days > warn_days:
                            freshness_status = "warn"
                        else:
                            freshness_status = "pass"
                    except ValueError:
                        freshness_status = "invalid"
                else:
                    freshness_status = "missing"

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

                verifies_with = frontmatter.get('verifies_with', [])
                if isinstance(verifies_with, str):
                    if verifies_with.startswith('[') and verifies_with.endswith(']'):
                        vw_list = [v.strip() for v in verifies_with[1:-1].split(',') if v.strip()]
                    else:
                        vw_list = [verifies_with.strip()] if verifies_with.strip() else []
                elif isinstance(verifies_with, list):
                    vw_list = verifies_with
                else:
                    vw_list = []

                # Check for missing scripts
                vw_display = []
                missing_scripts = []
                for vw in vw_list:
                    vw_path = os.path.join(REPO_ROOT, vw)
                    if not os.path.exists(vw_path):
                        missing_scripts.append(f"{vw}")
                    else:
                        vw_display.append(vw)

                verifies_with_str = ', '.join(sorted(vw_display))
                missing_scripts_str = ', '.join(sorted(missing_scripts))

                file_link = rel_file_path
            else:
                role = "_Missing_"
                status = "_Missing_"
                organ = "_Missing_"
                last_reviewed_str = "_Missing_"
                depends_on_str = "_Missing_"
                verifies_with_str = "_Missing_"
                freshness_status = "_Missing_"
                missing_scripts_str = "_Missing_"
                file_link = rel_file_path

            rows.append([doc_id, file_link, role, organ, status, last_reviewed_str, depends_on_str, verifies_with_str, freshness_status, missing_scripts_str])

        headers = ["id", "path", "role", "organ", "status", "last_reviewed", "depends_on", "verifies_with", "freshness_status", "missing_scripts"]

        header_row = "|" + "|".join(headers) + "|"
        output.append(header_row)

        sep_row = "|" + "|".join(["---" for _ in headers]) + "|"
        output.append(sep_row)

        for row in rows:
            data_row = "|" + "|".join(row) + "|"
            output.append(data_row)

        output.append("")

    output.append("## Automated Checks\n")
    checks = repo_index.get('checks', [])
    if checks:
        for check in sorted(checks):
            # Strip markdown link syntax to avoid diff noise
            output.append(f"- {check}")
        output.append("")

    out_path = os.path.join(REPO_ROOT, 'SYSTEM_MAP.md')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(output))

if __name__ == '__main__':
    main()
