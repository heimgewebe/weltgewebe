import os
import sys
import datetime

from scripts.docmeta.docmeta import REPO_ROOT, parse_repo_index, parse_frontmatter, parse_review_policy, normalize_list_field, extract_depends_on

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

    output = [
        "---",
        "id: docs.generated.system-map",
        "title: System Map",
        "doc_type: generated",
        "status: active",
        "summary: Automatisch generierte System Map.",
        "---",
        "## Weltgewebe System Map\n\nGenerated automatically. Do not edit.\n\nSource: scripts/docmeta/generate_system_map.py\n"
    ]

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

                depends_on_list = extract_depends_on(frontmatter)
                depends_on_str = ', '.join(depends_on_list)

                vw_list = normalize_list_field(frontmatter.get('verifies_with', []))

                # Check for missing scripts
                vw_display = []
                missing_scripts = []
                # Keep sorted order for determinism
                for vw in sorted(vw_list):
                    vw_path = os.path.join(REPO_ROOT, vw)
                    if not os.path.exists(vw_path):
                        missing_scripts.append(vw)
                        vw_display.append(f"{vw} 🔴(Missing)")
                    else:
                        vw_display.append(vw)

                verifies_with_str = ', '.join(vw_display)
                missing_scripts_str = ', '.join(missing_scripts)

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

    out_path = os.path.join(REPO_ROOT, 'docs', '_generated', 'system-map.md')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(output))

if __name__ == '__main__':
    main()
