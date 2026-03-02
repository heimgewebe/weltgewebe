import os
import sys
import re

from scripts.docmeta.docmeta import REPO_ROOT, parse_repo_index, parse_review_policy

def main():
    try:
        policy = parse_review_policy()
        strict_mode = policy.get('strict_manifest', False)
        repo_index = parse_repo_index(strict_manifest=strict_mode)
    except ValueError as e:
        print(f"Error parsing manifest/policy: {e}", file=sys.stderr)
        sys.exit(1)

    import json

    errors = []
    link_report = {}

    zones = repo_index.get('zones', {})

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

                # Strip anchor from url if present
                file_url = url.split('#')[0]
                if not file_url:
                    continue

                target_path = os.path.abspath(os.path.join(os.path.dirname(file_path), file_url))

                link_report[rel_file_path]["total_links"] += 1

                if not os.path.exists(target_path):
                    errors.append(f"Broken link in '{rel_file_path}': Target '{file_url}' does not exist.")
                    link_report[rel_file_path]["broken_links"].append(file_url)

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

    if errors:
        print(f"\n--- Errors ({len(errors)}) ---", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        print("\nDoc link check failed.", file=sys.stderr)
        sys.exit(1)

    print("Doc link check passed (0 errors).")

if __name__ == '__main__':
    main()
