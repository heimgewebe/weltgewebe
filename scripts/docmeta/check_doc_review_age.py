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

    default_cycle_days = policy['default_review_cycle_days']
    mode = policy['mode']

    errors = []
    warnings = []

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

            last_reviewed_str = frontmatter.get('last_reviewed')
            if not last_reviewed_str:
                msg = f"Missing 'last_reviewed' in '{rel_file_path}'."
                if mode == 'fail':
                    errors.append(msg)
                else:
                    warnings.append(msg)
                continue

            try:
                last_reviewed_date = datetime.datetime.strptime(last_reviewed_str, "%Y-%m-%d").date()
                today = datetime.date.today()
                delta = today - last_reviewed_date

                if delta.days > default_cycle_days:
                    msg = f"Document '{rel_file_path}' review age ({delta.days} days) exceeds default review cycle ({default_cycle_days} days)."
                    if mode == 'fail':
                        errors.append(msg)
                    else:
                        warnings.append(msg)
            except ValueError:
                errors.append(f"Invalid 'last_reviewed' format '{last_reviewed_str}' in '{rel_file_path}'. Must be YYYY-MM-DD.")

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
