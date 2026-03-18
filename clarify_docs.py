import re
import glob
import os

# Update docs/adr/ADR-0003__privacy-ungenauigkeitsradius-ron.md
with open('docs/adr/ADR-0003__privacy-ungenauigkeitsradius-ron.md', 'r') as f:
    code = f.read()

code = re.sub(
    r'RoN-Zuordnungen erscheinen im Zentrum des jeweiligen Stadtteils\.',
    r'RoN-Zuordnungen haben keine individuelle öffentliche Position (`public_pos = None`). Eine Gruppierung im Zentrum des jeweiligen Stadtteils ist eine spätere Darstellungsoption (noch nicht implementiert).', code
)
code = re.sub(
    r'und bei `mode=ron` keine individuelle Position \(bzw. Stadtteilzentrum\)\.',
    r'und bei `mode=ron` keine individuelle Position (`public_pos` ist leer).', code
)

with open('docs/adr/ADR-0003__privacy-ungenauigkeitsradius-ron.md', 'w') as f:
    f.write(code)

# Update docs/konzepte/garnrolle-und-verortung.md
with open('docs/konzepte/garnrolle-und-verortung.md', 'r') as f:
    code = f.read()

code = re.sub(
    r'Rolle ohne Namen im Zentrum deines Stadtteils\.',
    r'Rolle ohne Namen ohne individuelle Position auf der Karte.', code
)
code = re.sub(
    r'Rolle ohne Namen im Zentrum des Stadtteils',
    r'Rolle ohne Namen ohne individuelle Position (Stadtteilzentrum ist eine spätere Darstellungsoption)', code
)
code = re.sub(
    r'stattdessen Rolle ohne Namen im Zentrum des Stadtteils',
    r'keine individuelle Position (`public_pos` = None)', code
)

with open('docs/konzepte/garnrolle-und-verortung.md', 'w') as f:
    f.write(code)

# Update contracts/domain/account.schema.json
with open('contracts/domain/account.schema.json', 'r') as f:
    code = f.read()

code = re.sub(
    r'\(for verortete\) or city center \(for ron\)\.',
    r'(for verortete). RoN accounts do not have a public_pos.', code
)

with open('contracts/domain/account.schema.json', 'w') as f:
    f.write(code)
