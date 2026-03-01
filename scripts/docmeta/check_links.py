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

    errors = []
    warnings = []

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

            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Naive Markdown link parser: [text](url)
            # Ignoring image links ![text](url) could be done by a negative lookbehind, but re module doesn't support variable-width lookbehind easily if not simple.
            # We'll just match `[...](...)` and exclude `![...](...)`.
            links = re.findall(r'(?<!\!)\[.*?\]\((.*?)\)', content)

            for url in links:
                url = url.strip()
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

                if not os.path.exists(target_path):
                    errors.append(f"Broken link in '{rel_file_path}': Target '{file_url}' does not exist.")

    if warnings:
        print(f"\n--- Warnings ({len(warnings)}) ---", file=sys.stderr)
        for warning in warnings:
            print(f"- {warning}", file=sys.stderr)

    if errors:
        print(f"\n--- Errors ({len(errors)}) ---", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        print("\nDoc link check failed.", file=sys.stderr)
        sys.exit(1)

    print(f"Doc link check passed (0 errors, {len(warnings)} warnings).")

if __name__ == '__main__':
    main()
