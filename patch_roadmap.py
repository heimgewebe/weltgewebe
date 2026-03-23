import re

path = "docs/blueprints/map-roadmap.md"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

# Replace the text describing the published strategy
old_text = "- [x] Publish- und Rollback-Strategie festlegen\n  - _Umgesetzt: Publish- und Rollback-Strategie inklusive Atomic Switch und Sentinel-Verifikation in `map-blaupause.md` normativ definiert._"
new_text = "- [x] Publish- und Rollback-Strategie festlegen\n  - _Umgesetzt: Publish- und Rollback-Strategie inklusive Atomic Switch und Sentinel-Verifikation in `map-blaupause.md` normativ definiert, operative Implementierung (CI/Guards) ausstehend._"

text = text.replace(old_text, new_text)

with open(path, "w", encoding="utf-8") as f:
    f.write(text)

print("Patched map-roadmap.md")
