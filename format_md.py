import re

def fix_line_lengths(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    out_lines = []
    for line in lines:
        if len(line) > 120 and not line.strip().startswith('-') and not line.strip().startswith('`'):
             # Simplistic wrapper for non-code lines
             # Only wrap if it's normal text
             if not line.startswith(' ') and not line.startswith('#'):
                 words = line.split()
                 current_line = ""
                 for word in words:
                     if len(current_line) + len(word) + 1 <= 120:
                         if current_line:
                             current_line += " " + word
                         else:
                             current_line = word
                     else:
                         out_lines.append(current_line + '\n')
                         current_line = word
                 if current_line:
                     out_lines.append(current_line + '\n')
                 continue
        out_lines.append(line)

    with open(filename, 'w', encoding='utf-8') as f:
        f.writelines(out_lines)

fix_line_lengths("AGENTS.md")
