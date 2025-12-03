# weltgewebe-web (Gate A Click-Dummy)

Frontend-only Prototyp zur Diskussion von UX und Vokabular (Karte, Knoten,
Fäden, Drawer, Zeitachse).

## Development & Preview

Das Projekt verwendet pnpm via Corepack. Aktiviere es mit `corepack enable`.

### Development (HMR)

Für schnelle Iterationen mit Hot Module Replacement:

```bash
cd apps/web
pnpm install
pnpm dev -- --host 0.0.0.0 --port 5173
```

- **Port:** 5173
- **URL:** [http://localhost:5173/map](http://localhost:5173/map)
- **Hinweis:** In Codespaces/Containern ist `--host 0.0.0.0` zwingend nötig. Alternativ: `pnpm dev:cs`.

### Preview (Production Build)

Um den echten Build (wie in CI) zu testen und das Layout final zu prüfen (**idealer Weg**):

```bash
cd apps/web
pnpm build
pnpm preview -- --host 0.0.0.0 --port 4173
```

- **Port:** 4173
- **URL:** [http://localhost:4173/map](http://localhost:4173/map)
- **Hinweis:** Playwright-Tests nutzen lokal standardmäßig diesen Port. Alternativ: `pnpm preview:cs`.

<!-- prettier-ignore-start -->
> [!TIP]
> **E2E-Tests:** Playwright nutzt lokal Port `4173` (Preview-Server) und fällt in CI automatisch
> auf `5173` zurück (siehe [`playwright.config.ts`](./playwright.config.ts)). Setze `PORT=<nummer>`
> und führe `pnpm test:ci` aus, um den Port explizit vorzugeben.
> HTML-Reports landen unter `apps/web/playwright-report` (überschreibbar via
> `PLAYWRIGHT_HTML_REPORT`). CI-Artefakt-Uploads sollten sowohl den Ordner als auch die Datei
> `apps/web/playwright-report/results.xml` einsammeln.
>
> [!NOTE]
> **Node-Version:** Bitte Node.js ≥ 20.19 (oder ≥ 22.12) verwenden – darunter
> verweigern Vite und Freunde den Dienst. Per `nvm use` kannst du via
> `.nvmrc` im Projektverzeichnis direkt auf die richtige Version springen.
<!-- prettier-ignore-end -->

### Polyfill-Debugging

Für ältere Safari-/iPadOS-Versionen wird automatisch ein `inert`-Polyfill aktiviert.
Falls du das native Verhalten prüfen möchtest, hänge `?noinert=1` an die URL
(oder setze `window.__NO_INERT__ = true` im DevTools-Console).

### Screenshot aufnehmen

In einem zweiten Terminal (während `pnpm dev` läuft):

```bash
pnpm screenshot
```

Legt `public/demo.png` an.

## Was kann das?

- Vollbild-Karte (MapLibre) mit 4 Strukturknoten (Platzhalter).
- Linker/rechter Drawer (UI-Stubs), Legende, Zeitachsen-Stub im Footer.
- Keine Persistenz, keine echten Filter/Abfragen (Ethik → UX → Gemeinschaft →
  Zukunft → Autonomie → Kosten).

## Nächste Schritte

- A-2: Klick auf Marker öffnet Panel mit „Was passiert hier später?“
- A-3: Dummy-Datenlayer (JSON) für 2–3 Knotentypen, 2 Fadenfarben
- A-4: Accessibility-Pass 1 (Fokus, Kontrast)
- A-5: Dev-Overlay: Bundle-Größe (Budget ≤ ~90KB Initial-JS)

## Tests

### Tests & Reports

Playwright legt lokale HTML-Reports unter `apps/web/playwright-report` ab. Öffne sie bei
Bedarf mit `pnpm exec playwright show-report playwright-report`.

### Playwright (Drawer + Keyboard)

```bash
pnpm exec playwright install --with-deps  # einmalig
pnpm exec playwright test tests/drawers.spec.ts
```

Die Tests setzen in `beforeEach` das Flag `window.__E2E__ = true`, damit
Maus-Drags die Swipe-Gesten simulieren können.
