import re

with open('docs/blueprints/kartenklarheit.md', 'r') as f:
    content = f.read()

# Fix MD036 for A/B/C/D
content = content.replace('**A. Datenlade-Schicht**', '#### A. Datenlade-Schicht')
content = content.replace('**B. Szenen-Schicht**', '#### B. Szenen-Schicht')
content = content.replace('**C. Render-/Interaktions-Schicht**', '#### C. Render-/Interaktions-Schicht')
content = content.replace('**D. Diagnostik-Schicht**', '#### D. Diagnostik-Schicht')

# Fix MD032 (missing blank lines around lists)
content = re.sub(r'\*\*(Neu|Anpassen|Tests|Sofort|Danach|Zuletzt|Minimalpfad):\*\*\n-', r'**\1:**\n\n-', content)
content = re.sub(r'\*\*(Sofort|Danach|Zuletzt):\*\*\n1\.', r'**\1:**\n\n1.', content)

with open('docs/blueprints/kartenklarheit.md', 'w') as f:
    f.write(content)
