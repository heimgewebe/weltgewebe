import os
import sys

from docmeta import parse_repo_index, parse_frontmatter

def main():
    manifest_path = 'manifest/repo-index.yaml'
    repo_index = parse_repo_index(manifest_path)
    if not repo_index:
        print(f"Error: Could not parse {manifest_path}", file=sys.stderr)
        sys.exit(1)

    output = ["# SYSTEM_MAP\n"]

    for zone_name, zone_data in sorted(repo_index.get('zones', {}).items()):
        output.append(f"## Zone: {zone_name}\n")

        rows = []
        for doc_file in sorted(zone_data.get('canonical_docs', [])):
            file_path = os.path.join(zone_data.get('path', ''), doc_file)
            frontmatter = parse_frontmatter(file_path)

            if frontmatter:
                doc_id = frontmatter.get('id', '')
                status = frontmatter.get('status', '')
                last_reviewed = frontmatter.get('last_reviewed', '')
                depends_on = frontmatter.get('depends_on', [])
                if isinstance(depends_on, str) and depends_on.startswith('[') and depends_on.endswith(']'):
                    depends_on_list = [d.strip() for d in depends_on[1:-1].split(',')]
                    depends_on_str = ', '.join(depends_on_list)
                elif isinstance(depends_on, list):
                    depends_on_str = ', '.join(depends_on)
                else:
                    depends_on_str = depends_on
            else:
                doc_id = ""
                status = ""
                last_reviewed = ""
                depends_on_str = ""
            rows.append([doc_id, file_path, status, last_reviewed, depends_on_str])

        headers = ["ID", "File", "Status", "Last Reviewed", "Depends On"]
        col_widths = [len(h) for h in headers]

        for row in rows:
            for i, col in enumerate(row):
                if len(col) > col_widths[i]:
                    col_widths[i] = len(col)

        def pad(text, width):
            return text + " " * (width - len(text))

        header_row = "| " + " | ".join([pad(h, w) for h, w in zip(headers, col_widths)]) + " |"
        output.append(header_row)

        sep_row = "|" + "|".join(["-" * (w + 2) for w in col_widths]) + "|"
        output.append(sep_row)

        for row in rows:
            data_row = "| " + " | ".join([pad(c, w) for c, w in zip(row, col_widths)]) + " |"
            output.append(data_row)

        output.append("")

    with open('SYSTEM_MAP.md', 'w', encoding='utf-8') as f:
        f.write("\n".join(output))

if __name__ == '__main__':
    main()
