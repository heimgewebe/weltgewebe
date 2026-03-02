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

    errors = []
    warnings = []
    doc_ids = set()
    dependencies = {}
    verifications = {}

    zones = repo_index.get('zones', {})

    for zone_name, zone_data in zones.items():
        rel_zone_path = zone_data.get('path')
        if not rel_zone_path:
            errors.append(f"Zone '{zone_name}' is missing 'path'.")
            continue

        zone_path = os.path.join(REPO_ROOT, rel_zone_path)
        if not os.path.exists(zone_path):
            errors.append(f"Zone path '{rel_zone_path}' for zone '{zone_name}' does not exist.")
            continue

        canonical_docs = zone_data.get('canonical_docs', [])

        for doc_file in canonical_docs:
            file_path = os.path.join(zone_path, doc_file)
            rel_file_path = os.path.join(rel_zone_path, doc_file)

            if not os.path.exists(file_path):
                errors.append(f"Canonical doc '{rel_file_path}' does not exist.")
                continue

            frontmatter = parse_frontmatter(file_path)
            if not frontmatter:
                errors.append(f"Frontmatter missing or invalid in '{rel_file_path}'.")
                continue

            doc_id = frontmatter.get('id')
            if not doc_id:
                errors.append(f"Missing 'id' in frontmatter of '{rel_file_path}'.")
            elif doc_id in doc_ids:
                errors.append(f"Duplicate id '{doc_id}' found in '{rel_file_path}'.")
            else:
                doc_ids.add(doc_id)

            if frontmatter.get('status') != 'canonical':
                errors.append(f"Status is not 'canonical' in '{rel_file_path}'.")

            role = frontmatter.get('role')
            if role not in ('norm', 'reality', 'runbooks', 'action'):
                errors.append(f"Invalid role '{role}' in '{rel_file_path}'. Must be norm|reality|runbooks|action.")

            depends_on = frontmatter.get('depends_on', [])
            if isinstance(depends_on, str):
                if depends_on.startswith('[') and depends_on.endswith(']'):
                    depends_on = [d.strip() for d in depends_on[1:-1].split(',') if d.strip()]
                else:
                    depends_on = [depends_on.strip()] if depends_on.strip() else []

            if not isinstance(depends_on, list):
                depends_on = []

            verifies_with = frontmatter.get('verifies_with', [])
            if isinstance(verifies_with, str):
                if verifies_with.startswith('[') and verifies_with.endswith(']'):
                    verifies_with = [d.strip() for d in verifies_with[1:-1].split(',') if d.strip()]
                else:
                    verifies_with = [verifies_with.strip()] if verifies_with.strip() else []

            if not isinstance(verifies_with, list):
                verifies_with = []

            if doc_id:
                dependencies[doc_id] = depends_on
                verifications[doc_id] = verifies_with

    for doc_id, deps in dependencies.items():
        for dep in deps:
            if dep not in doc_ids:
                errors.append(f"Document '{doc_id}' depends on non-existent ID '{dep}'.")

    # Check for missing scripts
    missing_scripts_report = {}
    for doc_id, scripts in verifications.items():
        missing_for_doc = []
        for script in scripts:
            script_path = os.path.join(REPO_ROOT, script)
            if not os.path.exists(script_path):
                missing_for_doc.append(script)
                errors.append(f"Verification script '{script}' defined in '{doc_id}' does not exist.")

        missing_scripts_report[doc_id] = {
            "all_scripts": scripts,
            "missing": missing_for_doc
        }

    for check in repo_index.get('checks', []):
        check_path = os.path.join(REPO_ROOT, check)
        if not os.path.exists(check_path):
            errors.append(f"Check script '{check}' does not exist.")

    # Save artifact
    artifacts_dir = os.path.join(REPO_ROOT, "artifacts", "docmeta")
    os.makedirs(artifacts_dir, exist_ok=True)

    with open(os.path.join(artifacts_dir, "verification_report.md"), 'w', encoding='utf-8') as f:
        f.write("# Verification Scripts Report\n\n")
        f.write("| Document ID | Verified Scripts |\n")
        f.write("|---|---|\n")

        for doc_id in sorted(missing_scripts_report.keys()):
            info = missing_scripts_report[doc_id]
            scripts_output = []

            if not info["all_scripts"]:
                scripts_output.append("_None_")
            else:
                for script in info["all_scripts"]:
                    if script in info["missing"]:
                        scripts_output.append(f"`{script}` 🔴 (Missing)")
                    else:
                        scripts_output.append(f"`{script}` ✅")

            f.write(f"| {doc_id} | {'<br>'.join(scripts_output)} |\n")

    if warnings:
        print(f"\n--- Warnings ({len(warnings)}) ---", file=sys.stderr)
        for warning in warnings:
            print(f"- {warning}", file=sys.stderr)

    if errors:
        print(f"\n--- Errors ({len(errors)}) ---", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        print("\nRepo index consistency check failed.", file=sys.stderr)
        sys.exit(1)

    print(f"Repo index consistency check passed (0 errors, {len(warnings)} warnings).")

if __name__ == '__main__':
    main()
