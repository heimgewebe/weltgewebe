with open("docs/blueprints/ui-state-machine.md", "r") as f:
    lines = f.readlines()

new_lines = []
canonicality_added = False
for i, line in enumerate(lines):
    if line.startswith("---") and i > 0 and not canonicality_added:
        # the closing dash
        pass
    if line.startswith("canonicality: \"state-machine-contract\"") and i == 8:
        continue
    new_lines.append(line)

with open("docs/blueprints/ui-state-machine.md", "w") as f:
    f.writelines(new_lines)
