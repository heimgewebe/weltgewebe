import re

with open('docs/blueprints/kartenklarheit-roadmap.md', 'r') as f:
    content = f.read()

# Fix lists not having blank lines above them
# Basically if we see a heading followed immediately by a list item without a blank line, add a blank line
content = re.sub(r'^(### .+)\n(- \[ \])', r'\1\n\n\2', content, flags=re.MULTILINE)

# Remove trailing punctuation from the Minimalpfad heading
content = content.replace("### Minimalpfad erfolgreich, wenn:\n", "### Minimalpfad erfolgreich, wenn\n\n")

# Make duplicate headings unique and add blanks
# We know the duplicate headings are "### Ziel", "### Arbeitspakete", "### Verifikation", "### Stop-Kriterium"
# We can just manually substitute each phase's occurrences to be unique.

phases = [
    ("Phase 0", [("Ziel", "Phase 0"), ("Arbeitspakete", "Phase 0"), ("Stop-Kriterium", "Phase 0")]),
    ("Phase 1", [("Ziel", "Phase 1"), ("Arbeitspakete", "Phase 1"), ("Verifikation", "Phase 1"), ("Stop-Kriterium", "Phase 1")]),
    ("Phase 2", [("Ziel", "Phase 2"), ("Arbeitspakete", "Phase 2"), ("Verifikation", "Phase 2"), ("Stop-Kriterium", "Phase 2")]),
    ("Phase 3", [("Ziel", "Phase 3"), ("Arbeitspakete", "Phase 3"), ("Verifikation", "Phase 3"), ("Stop-Kriterium", "Phase 3")]),
    ("Phase 4", [("Ziel", "Phase 4"), ("Arbeitspakete", "Phase 4"), ("Verifikation", "Phase 4"), ("Stop-Kriterium", "Phase 4")]),
    ("Phase 5", [("Ziel", "Phase 5"), ("Arbeitspakete", "Phase 5"), ("Verifikation", "Phase 5"), ("Stop-Kriterium", "Phase 5")]),
    ("Phase 6", [("Ziel", "Phase 6"), ("Arbeitspakete", "Phase 6"), ("Verifikation", "Phase 6"), ("Stop-Kriterium", "Phase 6")]),
]

# We will just replace all of them with unique names by keeping track of the current phase.
# A simpler approach is to replace "### Ziel" with "### Ziel (Phase 0)" etc.
# We'll parse the file line by line and track the last seen phase heading.

lines = content.split('\n')
out_lines = []
current_phase = None

for i, line in enumerate(lines):
    if line.startswith("## Phase "):
        current_phase = line.replace("## ", "").split(" ")[0] + " " + line.replace("## ", "").split(" ")[1] # "Phase 0"

    if current_phase and line.startswith("### "):
        # Replace only if it's one of the duplicates
        heading = line.replace("### ", "").strip()
        if heading in ["Ziel", "Arbeitspakete", "Verifikation", "Stop-Kriterium"]:
            line = f"### {heading} ({current_phase})"

    out_lines.append(line)

content = '\n'.join(out_lines)

# Ensure blank lines around headings
# We can just run markdownlint --fix using npx markdownlint-cli2 --fix if available, but let's do it manually just in case
# Actually, npx markdownlint-cli2 docs/blueprints/kartenklarheit-roadmap.md --fix does most of MD022 and MD032
# Let's save the file and run that.

with open('docs/blueprints/kartenklarheit-roadmap.md', 'w') as f:
    f.write(content)
