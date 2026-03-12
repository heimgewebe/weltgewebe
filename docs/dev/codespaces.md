---
id: dev.codespaces
title: Codespaces
doc_type: reference
status: active
canonicality: derived
summary: Automatisch hinzugefügtes Frontmatter.
---
# Codespaces: Dev-Server schnell starten

Für die schnellste Entwicklung empfehlen wir den "Ein-Klick"-Task.

## Frontend schnell starten

1. **Dev-Server starten**

   [▶ Frontend in Codespaces starten](command:workbench.action.tasks.runTask?%5B%22Web%3A%20Devserver%20(Codespaces)%22%5D)

2. **Frontend im Browser öffnen**

   [🌍 Karte öffnen](http://localhost:5173/map)

## Manuelle Methode

Alternativ kannst du den Server auch im Terminal starten:

```bash
cd apps/web
corepack enable
pnpm install
pnpm dev -- --host 0.0.0.0 --port 5173
```

**Troubleshooting:**

- „vite: not found“: `pnpm install` erneut ausführen.
- „leere Seite“: Du bist vermutlich auf `/` statt `/map`. Nutze den Link oben oder hänge `/map` an die URL an.
