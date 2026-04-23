import os
import sys
import re
import datetime

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

    # Use exact same robust frontmatter match as parse_frontmatter
    match = re.match(r'^(---\r?\n)(.*?)(?:\r?\n---\r?\n|\r?\n---$)', content, re.DOTALL)
    if not match:
        print(f"Error: No valid frontmatter found in '{file_path}'.", file=sys.stderr)
        sys.exit(1)

    start_marker = match.group(1)
    frontmatter_text = match.group(2)
    end_marker = content[match.end(2):match.end()]

    body = content[match.end():]

    today_str = datetime.date.today().strftime("%Y-%m-%d")

    # Check if last_reviewed exists
    if not re.search(r'^last_reviewed:\s*.*$', frontmatter_text, re.MULTILINE):
        print(f"Error: 'last_reviewed' field not found in frontmatter of '{file_path}'.", file=sys.stderr)
        sys.exit(1)

    # Replace last_reviewed using regex
    new_frontmatter = re.sub(
        r'^(last_reviewed:)\s*.*$',
        f'\\g<1> {today_str}',
        frontmatter_text,
        flags=re.MULTILINE
    )

    new_content = start_marker + new_frontmatter + end_marker + body

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"Updated last_reviewed to {today_str} in '{file_path}'.")

if __name__ == '__main__':
    main()
