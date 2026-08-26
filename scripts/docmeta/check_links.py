import os
import sys
import re
import json

from scripts.docmeta.docmeta import REPO_ROOT, parse_repo_index, parse_review_policy

def main():
    try:
        policy = parse_review_policy()
        strict_mode = policy.get('strict_manifest', False)
        mode = policy.get('mode', 'warn')
        repo_index = parse_repo_index(strict_manifest=strict_mode)
    except ValueError as e:
        print(f"Error parsing manifest/policy: {e}", file=sys.stderr)
        sys.exit(1)

    errors = []
    warnings = []
    link_report = {}

    def report_issue(msg):
        if mode in ['strict', 'fail-closed']:
            errors.append(msg)
        else:
            warnings.append(msg)

    # Load docs index for doc:<id> resolution
    docs_index_path = os.path.join(REPO_ROOT, "artifacts", "docmeta", "docs.index.json")
    valid_doc_ids = set()
    docs_index_exists = os.path.exists(docs_index_path)

    if docs_index_exists:
        with open(docs_index_path, 'r', encoding='utf-8') as f:
            docs_data = json.load(f)
            for doc in docs_data.get('docs', []):
                doc_id = doc.get('id')
                if doc_id:
                    valid_doc_ids.add(doc_id)

    zones = repo_index.get('zones', {})

    doc_links_found = False

    for zone_name, zone_data in zones.items():
        rel_zone_path = zone_data.get('path', '')
        zone_path = os.path.join(REPO_ROOT, rel_zone_path)
        canonical_docs = zone_data.get('canonical_docs', [])

        for doc_file in canonical_docs:
            rel_file_path = os.path.join(rel_zone_path, doc_file)
            file_path = os.path.join(zone_path, doc_file)

            if not os.path.exists(file_path):
                continue

            link_report[rel_file_path] = {
                "total_links": 0,
                "broken_links": []
            }

            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Naive Markdown link parser: [text](url)
            # Ignoring image links ![text](url)
            links = re.findall(r'(?<!\!)\[.*?\]\((.*?)\)', content)

            for link_content in links:
                link_content = link_content.strip()

                # Extract URL from link_content handling optional titles and <url> syntax
                if link_content.startswith('<'):
                    end_idx = link_content.find('>')
                    if end_idx != -1:
                        url = link_content[1:end_idx]
                    else:
                        # Syntax error is always a strict error, regardless of mode.
                        errors.append(f"Malformed link in '{rel_file_path}': missing '>' in '{link_content}'")
                        continue
                else:
                    # Markdown links with titles are supported (e.g., [text](url "title")).
                    # If the actual URL contains spaces, it must be written using the <...> syntax.
                    # Otherwise, splitting by whitespace correctly extracts the URL and drops the title.
                    url = link_content.split()[0]

                # Skip external links
                if url.startswith(('http://', 'https://', 'mailto:', 'tel:')):
                    continue

                # Skip fragment-only links within the same document
                if url.startswith('#'):
                    continue

                raw_url = url
                file_url = raw_url.split('#', 1)[0]
                if not file_url:
                    continue

                link_report[rel_file_path]["total_links"] += 1

                if raw_url.startswith('doc:'):
                    doc_links_found = True
                    # The reviewer wants target_id explicitly stripped from raw_target
                    raw_target = raw_url[4:]
                    target_id = raw_target.split('#', 1)[0]
                    if not target_id:
                        report_issue(f"Malformed doc: link in '{rel_file_path}': missing canonical ID in '{raw_url}'.")
                        link_report[rel_file_path]["broken_links"].append(raw_url)
                    elif docs_index_exists:
                        if target_id not in valid_doc_ids:
                            report_issue(f"Broken link in '{rel_file_path}': Canonical ID '{target_id}' does not exist.")
                            link_report[rel_file_path]["broken_links"].append(raw_url)
                else:
                    target_path = os.path.abspath(os.path.join(os.path.dirname(file_path), file_url))

                    if not os.path.exists(target_path):
                        report_issue(f"Broken link in '{rel_file_path}': Target '{file_url}' does not exist.")
                        link_report[rel_file_path]["broken_links"].append(raw_url)

    if doc_links_found and not docs_index_exists:
        report_issue(f"Docs index missing ('{docs_index_path}'); cannot validate doc: links; run export_docs_index first.")

    # Save artifacts
    artifacts_dir = os.path.join(REPO_ROOT, "artifacts", "docmeta")
    os.makedirs(artifacts_dir, exist_ok=True)

    with open(os.path.join(artifacts_dir, "link_report.json"), 'w', encoding='utf-8') as f:
        json.dump(link_report, f, indent=2)

    with open(os.path.join(artifacts_dir, "link_report.md"), 'w', encoding='utf-8') as f:
        f.write("# Internal Link Report\n\n")
        f.write("| Document | Total Internal Links | Broken Links |\n")
        f.write("|---|---|---|\n")

        for doc_path in sorted(link_report.keys()):
            info = link_report[doc_path]
            broken_links_output = []

            if not info["broken_links"]:
                broken_links_output.append("_None_")
            else:
                for link in info["broken_links"]:
                    broken_links_output.append(f"`{link}` 🔴")

            f.write(f"| `{doc_path}` | {info['total_links']} | {'<br>'.join(broken_links_output)} |\n")

    if warnings:
        print(f"\n--- Warnings ({len(warnings)}) ---", file=sys.stderr)
        for warning in warnings:
            print(f"- {warning}", file=sys.stderr)
        print(f"\nMode is {mode}. Doc link check generated warnings but will not fail the build.", file=sys.stderr)

    if errors:
        print(f"\n--- Errors ({len(errors)}) ---", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        print(f"\nMode is {mode}. Failing build.", file=sys.stderr)
        sys.exit(1)

    if not errors and not warnings:
        print("Doc link check passed (0 errors, 0 warnings).")

if __name__ == '__main__':
    main()
