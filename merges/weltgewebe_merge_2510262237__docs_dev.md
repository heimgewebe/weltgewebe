### 📄 docs/dev/codespaces.md

**Größe:** 448 B | **md5:** `539e936bc772bd3ec55d4aa23b73f07d`

```markdown
# Codespaces: Dev-Server schnell starten

Im Codespace werden die Web-Abhängigkeiten automatisch installiert.

**Start:**

```bash
cd apps/web
npm run dev -- --host
```

Codespaces öffnet automatisch den Port **5173** – Link anklicken, `/map` ansehen.

**Troubleshooting:**  

- „vite: not found“: `npm i -D vite` und erneut starten.  
- „leere Seite“: einmal im Kartenbereich klicken (Keyboard-Fokus), dann `[` / `]` / `Alt+G` testen.
```

