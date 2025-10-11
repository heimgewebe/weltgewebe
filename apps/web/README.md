# weltgewebe-web (Gate A Click-Dummy)

Frontend-only Prototyp zur Diskussion von UX und Vokabular (Karte, Knoten, Fäden, Drawer, Zeitachse).

## Dev
```bash
cd apps/web
pnpm install
pnpm dev
```
Standardmäßig läuft der Dev-Server auf `http://localhost:5173/map`. 
In Container- oder Codespaces-Umgebungen kannst du optional `pnpm dev -- --host --port 5173` verwenden.

### Screenshot aufnehmen

In einem zweiten Terminal (während `pnpm dev` läuft):

```bash
pnpm run screenshot
```

Legt `public/demo.png` an.

## Was kann das?
- Vollbild-Karte (MapLibre) mit 4 Strukturknoten (Platzhalter).
- Linker/rechter Drawer (UI-Stubs), Legende, Zeitachsen-Stub im Footer.
- Keine Persistenz, keine echten Filter/Abfragen (Ethik → UX → Gemeinschaft → Zukunft → Autonomie → Kosten).

## Nächste Schritte
- A-2: Klick auf Marker öffnet Panel mit „Was passiert hier später?“
- A-3: Dummy-Datenlayer (JSON) für 2–3 Knotentypen, 2 Fadenfarben
- A-4: Accessibility-Pass 1 (Fokus, Kontrast)
- A-5: Dev-Overlay: Bundle-Größe (Budget ≤ ~90KB Initial-JS)
