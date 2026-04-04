with open('docs/deploy/CHANGELOG.md', 'r', encoding='utf-8') as f:
    content = f.read()

old_block = """## 2026-04-04 - Entfernung des Legacy-Alias /auth/login/consume

**Ursprung / Referenz:** Phase 4 Passkey-Architektur / Magic Link Migration

**Geänderte Dateien:**

- `infra/caddy/Caddyfile.prod`

**Beschreibung:**

Der temporäre Legacy-Alias `/auth/login/consume` wurde entfernt. Der Magic-Link-Consume-Pfad läuft nun ausschließlich über `/auth/magic-link/consume`.

**Risiko:** Niedrig.
"""

new_block = """## 2026-04-04 - Entfernung des Legacy-Alias /auth/login/consume

**Beschreibung:**

Der temporäre Legacy-Alias `/auth/login/consume` wurde entfernt. Der Magic-Link-Consume-Pfad läuft nun ausschließlich über `/auth/magic-link/consume`.

**Risiko:** Niedrig.
"""

content = content.replace(old_block, new_block)

with open('docs/deploy/CHANGELOG.md', 'w', encoding='utf-8') as f:
    f.write(content)
