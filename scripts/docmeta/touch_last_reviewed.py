import os
import sys
import re
import datetime

from scripts.docmeta.docmeta import REPO_ROOT

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 -m scripts.docmeta.touch_last_reviewed <file_path>", file=sys.stderr)
        sys.exit(1)

    file_path = sys.argv[1]

    # Normalize to absolute path
    if not os.path.isabs(file_path):
        file_path = os.path.abspath(file_path)

    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find the frontmatter
    match = re.match(r'^(---\r?\n.*?)(?:\r?\n---\r?\n|\r?\n---$)', content, re.DOTALL)
    if not match:
        print(f"Error: No valid frontmatter found in '{file_path}'.", file=sys.stderr)
        sys.exit(1)

    frontmatter_text = match.group(1)
    end_marker_match = re.search(r'(\r?\n---\r?\n|\r?\n---$)', content[len(frontmatter_text):])
    end_marker = end_marker_match.group(1) if end_marker_match else "\n---\n"

    body = content[len(frontmatter_text) + len(end_marker):]

    today_str = datetime.date.today().strftime("%Y-%m-%d")

    # Replace last_reviewed using regex preserving original line endings
    if re.search(r'^last_reviewed:.*$', frontmatter_text, re.MULTILINE):
        new_frontmatter = re.sub(
            r'^(last_reviewed:).*$',
            f'\\g<1> {today_str}',
            frontmatter_text,
            flags=re.MULTILINE
        )
    else:
        new_frontmatter = frontmatter_text + f"\nlast_reviewed: {today_str}"

    new_content = new_frontmatter + end_marker + body

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"Updated last_reviewed to {today_str} in '{file_path}'.")

if __name__ == '__main__':
    main()
