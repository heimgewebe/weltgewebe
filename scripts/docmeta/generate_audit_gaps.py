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

    audit_gaps = {}
    total_gaps = 0
    seen_ids = {}

    zones = repo_index.get('zones', {})

    for zone_name in sorted(zones.keys()):
        zone_data = zones[zone_name]
        rel_zone_path = zone_data.get('path', '')
        zone_path = os.path.join(REPO_ROOT, rel_zone_path)
        canonical_docs = zone_data.get('canonical_docs', [])

        for doc_file in sorted(canonical_docs):
            rel_file_path = os.path.normpath(os.path.join(rel_zone_path, doc_file))
            file_path = os.path.join(zone_path, doc_file)

            if not os.path.exists(file_path):
                continue

            frontmatter = parse_frontmatter(file_path)
            if not frontmatter:
                continue

            doc_id = frontmatter.get('id', rel_file_path)

            gaps = normalize_list_field(frontmatter.get('audit_gaps', []))

            if doc_id in seen_ids:
                prev_file = seen_ids[doc_id]
                msg = f"Warning: Duplicate ID '{doc_id}' found in '{prev_file}' and '{rel_file_path}'."
                if gaps:
                    msg += " Overwriting previous entries."
                elif doc_id in audit_gaps:
                    msg += " Clearing previous audit_gaps entry."
                print(msg, file=sys.stderr)

            seen_ids[doc_id] = rel_file_path

            if not gaps:
                if doc_id in audit_gaps:
                    total_gaps -= len(audit_gaps[doc_id]["gaps"])
                    del audit_gaps[doc_id]
                continue

            if doc_id in audit_gaps:
                total_gaps -= len(audit_gaps[doc_id]["gaps"])

            audit_gaps[doc_id] = {
                "file": rel_file_path,
                "gaps": gaps
            }
            total_gaps += len(gaps)

    # Save artifacts
    artifacts_dir = os.path.join(REPO_ROOT, "artifacts", "docmeta")
    os.makedirs(artifacts_dir, exist_ok=True)

    json_path = os.path.join(artifacts_dir, "audit_gaps.json")
    md_path = os.path.join(artifacts_dir, "audit_gaps.md")

    report_data = {
        "total_gaps": total_gaps,
        "documents_with_gaps": len(audit_gaps),
        "gaps": audit_gaps
    }

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, indent=2, sort_keys=True, ensure_ascii=False)
        f.write("\n")

    with open(md_path, 'w', encoding='utf-8') as f:
        f.write("# Audit Gaps Report\n\n")
        f.write("> **Note:** This report only aggregates known debt from canonical documents.\n")
        f.write("> Duplicate document IDs: last processed file wins; a warning is emitted during generation.\n\n")
        f.write(f"**Total Gaps:** {total_gaps} across {len(audit_gaps)} documents.\n\n")

        if audit_gaps:
            for doc_id in sorted(audit_gaps.keys()):
                info = audit_gaps[doc_id]
                f.write(f"## {doc_id}\n\n")
                f.write(f"File: `{info['file']}`\n\n")
                for gap in info['gaps']:
                    f.write(f"- [ ] {gap}\n")
                f.write("\n")
        else:
            f.write("No audit gaps found.\n\n")

    print(f"Audit gaps generation completed ({total_gaps} gaps found).")

if __name__ == '__main__':
    main()
