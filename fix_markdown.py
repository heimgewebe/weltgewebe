import re

with open('docs/blueprints/kartenklarheit.md', 'r') as f:
    content = f.read()

# Replace MD036 issues (bold text acting as headings) with regular text or proper lists if it makes sense, but the easiest fix for MD036 that avoids MD024 is just removing the bolding, but that loses emphasis.
# Another way to fix MD036 is to make them actual headings but avoid duplication.
# Or, if they are just labels, we can append a colon to them or embed them in the paragraph.
# Let's append a colon and remove the blank line after them to make them just bold text starting a paragraph.

def replace_bold_heading(match):
    text = match.group(1)
    # Return bold text with a colon, without the extra newlines that make it look like a heading
    return f"**{text}:**\n"

content = re.sub(r'^\*\*([^\*]+)\*\*\n+(?=[^\n#])', replace_bold_heading, content, flags=re.MULTILINE)

# Also fix the A/B/C/D ones at the top:
content = re.sub(r'^#### ([A-D]\. .*)\n', r'**\1**\n', content, flags=re.MULTILINE)

with open('docs/blueprints/kartenklarheit.md', 'w') as f:
    f.write(content)
