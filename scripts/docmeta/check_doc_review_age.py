import os
import sys
import datetime

from scripts.docmeta.docmeta import REPO_ROOT, parse_review_policy, parse_repo_index, parse_frontmatter

def main():
    try:
        policy = parse_review_policy()
        strict_mode = policy.get('strict_manifest', False)
        repo_index = parse_repo_index(strict_manifest=strict_mode)
    except ValueError as e:
        print(f"Error parsing manifest/policy: {e}", file=sys.stderr)
        sys.exit(1)

    import json

    try:
        warn_days = policy['warn_days']
        fail_days = policy['fail_days']
        mode = policy['mode']
    except KeyError as e:
        print(f"Error: review policy missing required key {e} (parser contract violation).", file=sys.stderr)
        sys.exit(1)

    errors = []
    warnings = []
    freshness_report = {}

    for zone_name, zone_data in repo_index.get('zones', {}).items():
        rel_zone_path = zone_data.get('path')
        if not rel_zone_path:
            continue

        zone_path = os.path.join(REPO_ROOT, rel_zone_path)
        if not os.path.exists(zone_path):
            continue

        for doc_file in zone_data.get('canonical_docs', []):
            file_path = os.path.join(zone_path, doc_file)
            rel_file_path = os.path.join(rel_zone_path, doc_file)

            if not os.path.exists(file_path):
                continue

            frontmatter = parse_frontmatter(file_path)
            if not frontmatter:
                continue

            doc_id = frontmatter.get('id', rel_file_path)
            last_reviewed_str = frontmatter.get('last_reviewed')

            status = 'unknown'
            days_since_review = -1

            if not last_reviewed_str:
                msg = f"Missing 'last_reviewed' in '{rel_file_path}'."
                status = 'missing'
                if mode in ['strict', 'fail-closed']:
                    errors.append(msg)
                else:
                    warnings.append(msg)
            else:
                try:
                    last_reviewed_date = datetime.datetime.strptime(last_reviewed_str, "%Y-%m-%d").date()
                    today = datetime.date.today()
                    delta = today - last_reviewed_date
                    days_since_review = delta.days

                    if days_since_review > fail_days:
                        status = 'fail'
                        msg = f"Document '{rel_file_path}' review age ({days_since_review} days) exceeds fail limit ({fail_days} days)."
                        if mode in ['strict', 'fail-closed']:
                            errors.append(msg)
                        else:
                            warnings.append(msg)
                    elif days_since_review > warn_days:
                        status = 'warn'
                        msg = f"Document '{rel_file_path}' review age ({days_since_review} days) exceeds warn limit ({warn_days} days)."
                        warnings.append(msg)
                    else:
                        status = 'pass'
                except ValueError:
                    status = 'invalid'
                    errors.append(f"Invalid 'last_reviewed' format '{last_reviewed_str}' in '{rel_file_path}'. Must be YYYY-MM-DD.")

            freshness_report[doc_id] = {
                "file": rel_file_path,
                "last_reviewed": last_reviewed_str,
                "days_since_review": days_since_review,
                "status": status
            }

    # Save artifacts
    artifacts_dir = os.path.join(REPO_ROOT, "artifacts", "docmeta")
    os.makedirs(artifacts_dir, exist_ok=True)

    with open(os.path.join(artifacts_dir, "freshness.json"), 'w', encoding='utf-8') as f:
        json.dump(freshness_report, f, indent=2)

    with open(os.path.join(artifacts_dir, "freshness.md"), 'w', encoding='utf-8') as f:
        f.write("# Freshness Report\n\n")
        f.write("| ID | File | Last Reviewed | Age (Days) | Status |\n")
        f.write("|---|---|---|---|---|\n")

        for doc_id in sorted(freshness_report.keys()):
            info = freshness_report[doc_id]
            status_icon = "✅"
            if info["status"] == "warn":
                status_icon = "⚠️"
            elif info["status"] == "fail":
                status_icon = "❌"
            elif info["status"] in ["missing", "invalid"]:
                status_icon = "❓"

            f.write(f"| {doc_id} | `{info['file']}` | {info['last_reviewed']} | {info['days_since_review']} | {status_icon} {info['status']} |\n")

    if warnings:
        print(f"\n--- Warnings ({len(warnings)}) ---", file=sys.stderr)
        for warning in warnings:
            print(f"- {warning}", file=sys.stderr)

    if errors:
        print(f"\n--- Errors ({len(errors)}) ---", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        print("\nDoc review age check failed.", file=sys.stderr)
        sys.exit(1)

    print(f"Doc review age check passed (0 errors, {len(warnings)} warnings).")

if __name__ == '__main__':
    main()
