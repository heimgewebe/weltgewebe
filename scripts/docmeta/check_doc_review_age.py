import os
import sys
import datetime

from scripts.docmeta.docmeta import REPO_ROOT, parse_review_policy, parse_repo_index, parse_frontmatter

def main():
    policy = parse_review_policy()

    if not policy:
        print("Error: Could not parse review-policy.yaml", file=sys.stderr)
        sys.exit(1)

    try:
        default_cycle_days = int(policy.get('default_review_cycle_days', 90))
        if default_cycle_days <= 0:
            raise ValueError
    except ValueError:
        print("Error: Invalid default_review_cycle_days in policy. Must be positive int.", file=sys.stderr)
        sys.exit(1)

    mode = policy.get('mode', 'warn').lower()
    if mode not in ['warn', 'fail']:
        print("Error: Invalid mode in policy. Must be 'warn' or 'fail'.", file=sys.stderr)
        sys.exit(1)

    repo_index = parse_repo_index()
    if not repo_index:
        print("Error: Manifest does not exist or could not be parsed.")
        sys.exit(1)

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
