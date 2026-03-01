import os
import sys
import datetime

from scripts.docmeta.docmeta import REPO_ROOT, parse_repo_index, parse_frontmatter, parse_review_policy

def main():
    try:
        policy = parse_review_policy()
        strict_mode = policy.get('strict_manifest', False)
        repo_index = parse_repo_index(strict_manifest=strict_mode)
    except ValueError as e:
        print(f"Error parsing manifest/policy: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        default_cycle_days = policy['default_review_cycle_days']
        policy_mode = policy['mode']
    except KeyError as e:
        print(f"Error: review policy missing required key {e}", file=sys.stderr)
        sys.exit(1)

    output = ["# SYSTEM_MAP\n"]

    today = datetime.date.today()

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

                # Freshness
                freshness = "🟢"
                if last_reviewed:
                    try:
                        lr_date = datetime.datetime.strptime(last_reviewed, "%Y-%m-%d").date()
                        delta = today - lr_date
                        if delta.days > default_cycle_days:
                            freshness = "🔴" if policy_mode == "fail" else "🟡"
                    except ValueError:
                        freshness = "❓"
                else:
                    freshness = "❓"

                last_reviewed_str = f"{last_reviewed} {freshness}".strip()

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
                for vw in vw_list:
                    vw_path = os.path.join(REPO_ROOT, vw)
                    if not os.path.exists(vw_path):
                        vw_display.append(f"{vw} 🔴(Missing)")
                    else:
                        vw_display.append(vw)
                verifies_with_str = ', '.join(vw_display)

                # Make the file path a markdown link (we remove this for diff-noise minimieren? Wait, prompt says: generate_system_map: Spaltenbreiten/Width-Calc kosmetisch: Link-Text strippen, Diff-Noise minimieren. We can just use the path as text, not markdown link, to avoid formatting noise). Let's use rel_file_path directly.
                file_link = rel_file_path
            else:
                doc_id = "_Missing_"
                status = "_Missing_"
                last_reviewed_str = "_Missing_"
                depends_on_str = "_Missing_"
                verifies_with_str = "_Missing_"
                file_link = rel_file_path

            rows.append([doc_id, file_link, status, last_reviewed_str, depends_on_str, verifies_with_str])

        headers = ["ID", "File", "Status", "Last Reviewed", "Depends On", "Verifies With"]

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
            # Same here, strip markdown link syntax to avoid diff noise
            output.append(f"- {check}")
        output.append("")

    out_path = os.path.join(REPO_ROOT, 'SYSTEM_MAP.md')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(output))

if __name__ == '__main__':
    main()
