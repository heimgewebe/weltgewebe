import os
import sys
import re
from datetime import datetime

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 -m scripts.docmeta.touch_last_reviewed <file_path>", file=sys.stderr)
        sys.exit(1)

    file_path = sys.argv[1]
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' not found.", file=sys.stderr)
        sys.exit(1)

    today = datetime.today().strftime('%Y-%m-%d')
    updated = False

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Search and replace last_reviewed in frontmatter
    # Frontmatter is between the first two ---

    match = re.search(r'^---\r?\n(.*?)(?:\r?\n---\r?\n|\r?\n---$)', content, re.DOTALL)
    if not match:
        print(f"Error: No YAML frontmatter found in '{file_path}'.", file=sys.stderr)
        sys.exit(1)

    frontmatter = match.group(1)
    new_frontmatter = []

    for line in frontmatter.splitlines():
        if line.startswith('last_reviewed:'):
            new_frontmatter.append(f"last_reviewed: {today}")
            updated = True
        else:
            new_frontmatter.append(line)

    if not updated:
        print(f"Error: 'last_reviewed' field not found in frontmatter of '{file_path}'.", file=sys.stderr)
        sys.exit(1)

    # Reconstruct the file content
    old_fm_block = match.group(0)
    # the replacement logic must carefully preserve trailing/leading things of old_fm_block
    line_ending = '\r\n' if '\r\n' in old_fm_block else '\n'
    new_fm_block = old_fm_block.replace(frontmatter, line_ending.join(new_frontmatter))

    new_content = content.replace(old_fm_block, new_fm_block, 1)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"Updated last_reviewed to {today} in '{file_path}'.")

if __name__ == '__main__':
    main()
