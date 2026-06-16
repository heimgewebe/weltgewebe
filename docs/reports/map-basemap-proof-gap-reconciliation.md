---
id: map-basemap-proof-gap-reconciliation
title: MAP-PROOF-001 — Basemap Proof Gap Reconciliation
doc_type: report
status: active
summary: Diagnose-/Reconciliation-Report, der den belegbaren Beweisstand der Basemap-Runtime (statische Config, gemockter Client, Caddy-Range, PMTiles-Content, Browser-/PMTiles-Init, visuelle Artefakte, Produktions-Caddy) gegen verifizierte CI-Evidenz abgleicht und den naechsten Implementierungs-PR ableitet.
relations:
  - type: relates_to
    target: docs/reports/map-status-matrix.md
  - type: relates_to
    target: docs/blueprints/kartenklarheit-phase6.md
  - type: relates_to
    target: docs/blueprints/kartenklarheit-roadmap.md
  - type: relates_to
    target: docs/proofs/basemap-hamburg-artifact-proof.md
  - type: relates_to
    target: scripts/guard/basemap-runtime-proof.sh
  - type: relates_to
    target: .github/workflows/basemap-runtime-proof.yml
---

# MAP-PROOF-001 — Basemap Proof Gap Reconciliation

Status: diagnosis/reconciliation-only
Date: 2026-06-15
Scope: map / basemap / Caddy / PMTiles / HTTP Range / CI / visual proof

> Dieser Report implementiert keinen Runtime-Proof. Er versoehnt den vorhandenen
> Beweisstand mit der tatsaechlichen CI-Realitaet und leitet daraus den naechsten
> Implementierungs-PR ab. Alle hier zitierten CI-Belege wurden ueber die
> GitHub-Actions-API gegen das Repository `heimgewebe/weltgewebe` verifiziert
> (Stand 2026-06-15). Synthetische CI-Belege werden nicht als echter Karten- oder
> Rendering-Beweis gewertet.

## These / Antithese / Synthese

**These (Ausgangsplan):** „Caddy + HTTP 206 + echtes Kartenartefakt + visuelles
Rendering im CI sind weitgehend unbewiesen; der naechste Schritt ist ein realer
PMTiles-Content-Proof."

**Antithese (Repo-Befund):** Der Dump und die verifizierte CI-Historie zeigen das
Gegenteil der Restleerstellen-Hypothese: Der `basemap-runtime-proof.yml`-Workflow
betreibt vier Jobs, von denen drei blockierend sind. Real-Caddy-Range (synthetisch),
echtes Hamburg-PMTiles-Artefakt (Magic + SHA256) und der **browserseitige
PMTiles-Protokollzugriff samt Render-Initialisierung** sind **bereits gruen auf `main`**.
Die Statusdokumente sind hier nicht zu optimistisch, sondern zu **pessimistisch**:
Sie behaupten teils noch `NOT_PROVEN` / `READY_FOR_CI_PROOF`, obwohl die Jobs
nachweislich gruen sind.

**Synthese:** Die eigentliche Leerstelle ist nicht „Beweis fehlt", sondern
„Beweis-Einordnung driftet". Real bewiesen sind P0–P3 und P5 (mit klaren
Scope-Grenzen). Echte Restleerstellen bleiben: tiefe PMTiles-Strukturvalidierung
(P4), die Vector-Tile-Payload-/Tile-Datenlieferung, visuelle **Korrektheit** statt
nur Rendering-Signal (P6), Produktionsnaehe der Caddy-Konfiguration (P7) und die
**Reproduzierbarkeit** des Artefakts. Der naechste PR ist deshalb nicht „erst mal ein echtes Artefakt bauen"
(das existiert), sondern „die echte Restleerstelle schliessen + die Dokumentation
konsolidieren".

## 1. Warum dieser Task jetzt

- Die Behauptungslage zur Basemap-Runtime ist ueber mehrere Dokumente verteilt
  (`docs/reports/map-status-matrix.md` + `.json`, `docs/blueprints/kartenklarheit-phase6.md`,
  `docs/blueprints/kartenklarheit-roadmap.md`, `docs/proofs/basemap-hamburg-artifact-proof.md`).
- Diese Dokumente widersprechen sich gegenseitig (siehe Abschnitt 4) und teils der
  tatsaechlichen CI-Realitaet.
- Ohne saubere Einordnung droht entweder Overclaiming (synthetischer Range-Proof als
  echter Karteninhalt) oder Underclaiming (gruener Visual-CI-Job, der weiter als
  `NOT_PROVEN` gefuehrt wird). Beides ist im Repo aktuell gleichzeitig vorhanden.
- Ziel: ein einziger, belegbarer Beweis-Stand mit klaren Scope-Grenzen, der den
  naechsten Implementierungs-PR schneidet.

## 2. Vorhandene Beweisschichten

### 2.1 Static Basemap Config

- `map-style/style.json`: souveraener Style, Source `basemap` ueber
  `pmtiles://basemap-hamburg.pmtiles`, Glyphs ueber `/local-basemap/glyphs/...`.
  Die `metadata`-Note kennzeichnet die PMTiles-URL selbst als Platzhalter
  („actual resolution depends on runtime protocol handler").
- `apps/web/src/lib/map/basemap.ts`: `resolveBasemapStyle()` liefert fuer
  `local-sovereign` `"/local-basemap/style.json"`; `rewritePmtilesUrl()` schreibt
  blanke `pmtiles://`-Aliase auf den lokalen Pfad um. Selbstdokumentierter Hinweis:
  „The existence of this rewrite is not evidence of an active end-to-end supported mode."
- `apps/web/src/lib/map/config/basemap.current.ts`: `resolveBasemapMode()` schaltet
  dev/test → `local-sovereign`, Produktion → `remote-style`, ueberschreibbar via
  `PUBLIC_BASEMAP_MODE`. Zentrum: Hammer Park (`53.5585, 10.058`).
- **Bewertung:** statische Konfiguration vorhanden und typisiert; kein Laufzeitbeweis.

### 2.2 Mocked Client Integration

- `apps/web/tests/basemap-client-integration.spec.ts` mockt `/local-basemap/style.json`
  und `/local-basemap/*.pmtiles` per `page.route(...)` und belegt, dass MapLibre den
  `pmtiles://`-Source aufloest und einen `Range: bytes=...`-Header sendet.
  Der Test markiert sich selbst als gemockt („not real Edge-routing delivery").
- `apps/web/tests/basemap-sovereignty-testbuild.spec.ts` und
  `apps/web/tests/basemap.spec.ts` decken Modus-/Style-Aufloesung und den
  clientseitigen lokalen Pfad ab.
- **Bewertung:** clientseitiges Protokollverhalten bewiesen, ohne echtes HTTP-Backend.

### 2.3 Caddy Range Delivery

- Guard `scripts/guard/basemap-runtime-proof.sh`, Scope `range-delivery` (Default):
  Range-GET (`bytes=0-511`) gegen laufenden Caddy, erzwingt HTTP 206 und mindestens
  einen der Header `Accept-Ranges` / `Content-Range`; explizit kein Inhaltsbeweis.
- CI-Job `basemap-range-delivery-proof` startet `caddy:2.7` mit
  `infra/caddy/Caddyfile.proof` und einem **synthetischen 64-KiB-Artefakt** (kein
  gueltiges PMTiles). Blockierend.
- **Bewertung:** Range-Auslieferungs-Kette real bewiesen — aber nur fuer
  **synthetischen** Inhalt.

### 2.4 PMTiles Artifact / Magic Bytes

- Build: `scripts/basemap/build-hamburg-pmtiles.sh` (Planetiler `0.8.2`, gepinnt per
  Image-Digest; OSM-Input `hamburg-250101.osm.pbf` mit SHA256 verifiziert).
- Guard-Scope `pmtiles-content`: lokale Datei nicht-leer + Magic `PMTiles` an Offset 0
  - optional SHA256 + via Caddy ausgelieferte Magic-Bytes `0-6` (`PMTiles`) bei HTTP 206.
- CI-Job `basemap-pmtiles-content-proof` baut das echte Hamburg-Artefakt im Lauf,
  serviert es ueber Caddy, prueft Magic + SHA256. Blockierend.
- **Bewertung:** echtes Artefakt + Magic + intra-run SHA256 bewiesen; **keine**
  Strukturvalidierung jenseits der ersten 7 Bytes.

### 2.5 PMTiles Structural Validation

- Der Guard druckt explizit:
  `NOT_PROVEN: Deep PMTiles structure validation (tile index, directory, metadata integrity)`.
- Kein Code liest PMTiles-v3-Header (Version-Byte, Root-Directory-Offset/Length,
  Metadata-Block) oder fuehrt einen Tile-Read durch.
- **Bewertung:** `NOT_PROVEN`. Magic-Byte-Check ist keine Strukturvalidierung.

### 2.6 Browser PMTiles Protocol / Render Init

- `apps/web/tests/proofs/basemap-real-hamburg-visual.proof.ts` greift auf das **echte**
  Hamburg-Artefakt ueber die **Vite-Middleware** (nicht Caddy) zu: ein **separater
  direkter** Range-Request beweist HTTP 206 + `Accept-Ranges` + `Content-Range`;
  zusaetzlich werden MapLibre-Canvas sichtbar (Dimensionen > 0), `isStyleLoaded() === true`,
  **≥ 1 beobachteter** lokaler PMTiles-(Range-)Request und **0** Requests an externe
  Tile-Provider geprueft.
- CI-Job `basemap-visual-proof` (`needs: basemap-pmtiles-content-proof`) fuehrt genau
  diesen Test aus. **Gruen auf `main`** (siehe Abschnitt 6).
- **Bewertung:** Browserseitiger PMTiles-Protokollzugriff und Render-Initialisierung
  sind belegt. Der vorhandene Test belegt **nicht**, dass ein Vector-Tile-Payload gelesen
  wurde. Der beobachtete PMTiles-Request kann Header-/Indexzugriff sein; der harte
  HTTP-206-Beweis stammt aus einem separaten direkten Range-Request. Echte
  Tile-Datenlieferung / Source-loaded-Tile-Payload bleibt `NOT_PROVEN`.

### 2.7 Visual Artifact / Screenshot

- Der Visual-Job nimmt einen Screenshot (`screenshot.png`) und schreibt
  `proof-summary.json` (`verdict: PROVEN`), beide als CI-Artefakt hochgeladen.
- Es gibt **keinen** Pixel-/Baseline-Vergleich (`toMatchSnapshot` o. ae.). Der
  Screenshot belegt „etwas wurde gerendert", nicht „die Karte ist visuell korrekt".
- **Bewertung:** `PARTIAL`. Rendering-Signal + Souveraenitaet bewiesen; visuelle
  **Korrektheit** nicht. (Pixelvergleich ist ein bewusstes Nicht-Ziel.)

### 2.8 Production-like Caddy

- Proof-Pfad: `caddy:2.7` (Stock-Image) + minimaler `infra/caddy/Caddyfile.proof`
  (`auto_https off`, `admin off`, blanker `file_server`, **kein** CORS/CSP/Reverse-Proxy).
- Produktions-/Heim-Pfad: gebautes Image `infra/caddy/Dockerfile` = **`caddy:2.8.4`**
  (+ `caddy-ratelimit@v0.1.0`); `infra/compose/compose.prod.yml` mountet
  `infra/caddy/Caddyfile.heim` (CORS + Range + CSP + Cache-Header +
  `.pmtiles`/`.meta.json`-Regexp-Routing).
- `infra/caddy/Caddyfile.prod` (`weltgewebe.net`) besitzt **gar keine**
  `/local-basemap/`-Route — der Web-Upstream wird an Cloudflare Pages/Vercel
  weitergereicht.
- **Bewertung:** `NOT_PROVEN`. Version-Drift (2.7 vs 2.8.4 + Plugin),
  Config-Surface-Drift und eine `heim` vs `net`-Architektur-Divergenz.

## 3. Proof-Level-Matrix

| Level | Status | Scope | Evidence | Establishes | Does not establish | Gap |
| --- | --- | --- | --- | --- | --- | --- |
| P0 static-config | PROVEN | code+docs (statisch) | `map-style/style.json`, `apps/web/src/lib/map/basemap.ts`, `apps/web/src/lib/map/config/basemap.current.ts`, `apps/web/tests/basemap.spec.ts` | Style/Modus/Alias existieren, typisiert, modusgetestet | jede Laufzeit-Auslieferung/Rendering | → P1+ |
| P1 mocked-client-path | PROVEN | test (mocked) | `apps/web/tests/basemap-client-integration.spec.ts`, `basemap-sovereignty-testbuild.spec.ts` | MapLibre loest `pmtiles://` auf + sendet Range-Header (gemockt) | reale Caddy-/Vite-Auslieferung, echter Inhalt | → P2 |
| P2 caddy-range-synthetic | PROVEN | CI + synthetisch | Job `basemap-range-delivery-proof`, Run 27028165272 (Job 79773383993); fruehere Runs 25970466659, 26447341921; `caddy:2.7`+`Caddyfile.proof`, 64-KiB-Synthetik | echte Caddy-206-Range-Kette auf `/local-basemap/*` | echten Karteninhalt (Artefakt synthetisch) | → P3 |
| P3 real-pmtiles-magic | PROVEN | CI + lokal, Magic/Hash | Job `basemap-pmtiles-content-proof`, Run 27028165272 (Job 79773383882) + Run 26447341921 (Job 77857000606); `docs/proofs/basemap-hamburg-artifact-proof.md` | echtes Hamburg-PMTiles, Magic `PMTiles`@0, intra-run SHA256, Caddy liefert Bytes 0-6 via 206 | tiefe Struktur; **Reproduzierbarkeit** (SHA env-abhaengig) | → P4 + Reprod. |
| P4 real-pmtiles-structure | NOT_PROVEN | — | Guard druckt `NOT_PROVEN: Deep PMTiles structure validation` | nichts ueber Magic hinaus | Tile-Directory/Metadata/Tile-Read | Strukturparser/Inspect auf Fixture |
| P5 browser-pmtiles-protocol-init | PROVEN | CI + echtes Artefakt via Vite-Middleware | Job `basemap-visual-proof`, Run 27028165272 (Job 79773804577) + Run 26535801825 (Job 78164572577); `apps/web/tests/proofs/basemap-real-hamburg-visual.proof.ts` | separater direkter HTTP-206-Range-Request, beobachteter lokaler PMTiles-Request, Canvas sichtbar, `isStyleLoaded()`, 0 externe Provider | Vector-Tile-Payload-/Tile-Datenlieferung, Source-loaded-Tile-Payload, Caddy-Visual-Pfad, Pixel-Korrektheit, Produktion | → P6, P7 |
| P6 visual-artifact | PARTIAL | CI Screenshot, kein Baseline | `screenshot.png` + `proof-summary.json` (Run 27028165272 Job 79773804577) | Screenshot + Rendering-/Souveraenitaets-Signal | visuelle **Korrektheit** (kein Pixel-/Baseline-Vergleich) | bewusst bounded (Pixelvergleich = Nicht-Ziel) |
| P7 production-like-caddy | NOT_PROVEN | — | Proof `caddy:2.7`+`Caddyfile.proof` bzw. Vite; Prod `infra/caddy/Dockerfile`=`caddy:2.8.4`+`caddy-ratelimit`, `Caddyfile.heim`; `Caddyfile.prod` ohne `/local-basemap/` | nichts ueber Prod-Aequivalenz | Version-/Config-/Architektur-Aequivalenz | Prod-naher Caddy-Proof |

### Querschnitt: Reproduzierbarkeit (eigene Leerstelle)

- Heimserver-Artefakt (`docs/proofs/basemap-hamburg-artifact-proof.md`):
  SHA256 `f0734f0137c69b345ea81ed865519402d96f226fe15bc6c976134d9ed1f28a8e`,
  `23948877` Bytes.
- CI-Artefakt (Run 26447341921, dieselbe Pipeline):
  SHA256 `3eea9946f90a1cca425916c5b3272692ae8a1030bf22e700b67908cfafee8eab`,
  `23948909` Bytes.
- Gleicher gepinnter Planetiler-Digest, gleicher gepinnter OSM-Input-Hash —
  trotzdem **unterschiedliche Ausgabe** (Δ 32 Bytes). Der Build deklariert selbst:
  „outputs are not yet strictly reproducible". Die Ursache ist noch nicht belegt.
  Plausible Kandidaten sind PMTiles-/MBTiles-Metadaten, Build-Zeitstempel, SQLite/Page-Layout
  oder Planetiler-Ausgabedetails. Dieser Report behauptet daher nur die Abweichung, nicht die Ursache.
- Konsequenz: Der SHA256-Check des Guards ist **intra-run/selbstreferenziell** (er
  hasht die soeben gebaute Datei und vergleicht sie mit der im selben Lauf
  geschriebenen `meta.json`). Er beweist Integritaet innerhalb eines Laufs, **nicht**
  einen kanonischen, umgebungsstabilen Soll-Hash. Status: `NOT_PROVEN`
  (Cross-Env-Reproduzierbarkeit).

## 4. Status-Reconciliation

| Statement | Source | Current finding | Assessment | Proposed correction |
| --- | --- | --- | --- | --- |
| „CI-Ausfuehrung des visuellen Proofs: READY_FOR_CI_PROOF … kein gruener GitHub-Actions-Lauf liegt noch vor." | `docs/reports/map-status-matrix.md` §6 + `.json` (`missing_evidence`) | Job `basemap-visual-proof` ist **gruen auf `main`**: Run 27028165272 (Job 79773804577, 2026-06-05) und Run 26535801825 (Job 78164572577, 2026-05-27) | **Stale / Underclaim** | Visual-CI auf PROVEN (Scope: Vite-Middleware, kein Caddy/Pixel) mit Run-Belegen |
| Phase 6: „[ ] Visuelle Abnahme" / „NOT_PROVEN" | `docs/blueprints/kartenklarheit-phase6.md` §2.4, `kartenklarheit-roadmap.md` Phase 6 | s. o. — gruen auf `main` | **Stale / Underclaim** | Checkbox auf erledigt (mit Scope-Grenze + Run-Beleg) |
| Phase 6: „[ ] PMTiles-Magic-Byte-Check im CI … wartet auf ein echtes Artefakt" | `kartenklarheit-phase6.md` §2.4, `kartenklarheit-roadmap.md` Phase 6 | Job `basemap-pmtiles-content-proof` ist gruen (Runs 26447341921, 26535801825, 27028165272); `map-status-matrix` fuehrt es korrekt als PROVEN | **Intra-Repo-Widerspruch** (Matrix sagt PROVEN, Roadmap/Phase6 sagen offen) | Roadmap-Checkbox auf erledigt (Scope: Magic; Struktur bleibt offen) |
| „Hamburg-/Deutschland-Builds … laufen weiterhin nur via `workflow_dispatch`." | `kartenklarheit-phase6.md` §2.4, `kartenklarheit-roadmap.md` Phase 6 | Workflow-Trigger: `pull_request`+`push` auf `main` (path-gated) **plus** `workflow_dispatch`; verifizierte Runs liefen als `pull_request`/`push` | **Falsch** (Trigger-Drift) | Aussage praezisieren: laeuft path-gated auf PR/Push, nicht nur dispatch |
| „Visuelle Abnahme in GitHub Actions Standard-CI (`test:ci`): NOT_PROVEN" | `docs/proofs/basemap-hamburg-artifact-proof.md` | **Korrekt** — `test:ci` fuehrt den opt-in Proof nicht aus; der gruene Lauf liegt im dedizierten `basemap-runtime-proof.yml` | **Konsistent** (saubere Scope-Trennung) | keine Korrektur; nur Praezisierung im Report |
| SHA256/Groesse des „v0.1.0"-Artefakts | `artifact-proof.md` (`f0734…`/23948877) vs `map-status-matrix` (`3eea…`/23948909) | abweichend → nicht reproduzierbar | **Nicht-reproduzierbar; bisher nicht eingeordnet** | als bewusste Leerstelle dokumentieren (intra-run SHA) |
| Caddy-Version im Proof vs. Produktion | nirgends abgeglichen | Proof `caddy:2.7`, Prod/Heim `caddy:2.8.4`+`caddy-ratelimit` (`infra/caddy/Dockerfile`) | **Bisher unbenannte Drift** | als P7-Gap fuehren |

> **Phase-6-Sync (in diesem PR):** Dieser PR korrigiert `docs/reports/map-status-matrix.md` + `.json`,
> `docs/blueprints/kartenklarheit-roadmap.md` **und** `docs/blueprints/kartenklarheit-phase6.md`.
> Damit ist die zuvor bewusst belassene Drift aufgeloest: Phase 6 fuehrt `pmtiles-content`
> und den Browser-/PMTiles-Init-Proof jetzt konsistent als PROVEN (mit Scope-Grenzen),
> waehrend PMTiles-Struktur (P4), Vector-Tile-Payload-Lieferung, Pixel-Korrektheit (P6)
> und produktionsnaher Caddy (P7) offen bleiben.

## 5. Synthetisch vs. echtes Kartenartefakt

- **Synthetisch (P2):** Der `range-delivery`-Job schreibt deterministisch 64 KiB
  Pseudozufall — bewusst **kein** gueltiges PMTiles. Er beweist ausschliesslich die
  Caddy-Range-Kette (206 + Header). Er beweist **keinen** Karteninhalt.
- **Echt (P3/P5):** Der `pmtiles-content`- und der `visual`-Job bauen das echte
  Hamburg-Artefakt (Planetiler, gepinnt) und beweisen Magic/Hash bzw. den
  Browser-/PMTiles-Protokollzugriff samt Render-Initialisierung (kein Tile-Payload-Read).
- **Regel:** Range-Delivery ist PROVEN, aber bei synthetischem Scope bleibt echter
  Karteninhalt **getrennt** zu betrachten. „Caddy liefert 206" ⇒ nicht „die Karte
  stimmt". P2 und P3/P5 duerfen nicht vermischt werden.

## 6. Lokal vs. CI

Verifizierte CI-Belege (GitHub Actions API, `heimgewebe/weltgewebe`, Workflow
„Basemap Runtime Proof"):

- **Run 27028165272** (`main`, `push`, 2026-06-05, `head_sha` `303e88f9`): **4/4 Jobs
  `success`** —
  `basemap-runtime-proof` (79773383916, skip-Dry-Run),
  `basemap-range-delivery-proof` (79773383993, synthetisch),
  `basemap-pmtiles-content-proof` (79773383882, echtes Hamburg-Artefakt, Build-Schritt
  ~2 min),
  `basemap-visual-proof` (79773804577, Playwright echtes Artefakt via Vite-Middleware).
- **Run 26535801825** (`main`, `push`, 2026-05-27): ebenfalls **4/4 `success`**,
  inkl. `basemap-visual-proof` (78164572577).
- **Run 26447341921** (`pull_request`, Branch `chore/api-dockerfile-cargo-build-jobs`,
  2026-05-26): 3/4 — dieser aeltere Lauf hatte den Visual-Job **noch nicht**;
  `pmtiles-content` (77857000606) und `range-delivery` (77857000627) waren `success`.
- **Run 25970466659**: in den Statusdokumenten als erster `range-delivery`-PROVEN-Beleg
  gefuehrt (Commit 14feefd6).

Schlussfolgerungen:

- Der Visual-Job wurde **nach** Run 26447341921 hinzugefuegt; seine ersten gruenen
  Laeufe liegen auf `main` (26535801825, 27028165272). Damit ist die
  „kein gruener Lauf"-Aussage der Statusdokumente ueberholt.
- Lokaler Heimserver-Proof (`artifact-proof.md`) und CI-Proof sind **getrennte**
  Belege; der lokale Visual-Proof zaehlt nicht automatisch als CI-Proof — hier liegt
  aber inzwischen zusaetzlich ein CI-Beleg vor.

## 7. Minimal ausreichender naechster Implementierungs-PR

Der naechste PR ist **nicht** „erst mal ein echtes Artefakt im CI bauen" — das ist
bereits PROVEN (P3) inklusive Browser-/PMTiles-Init (P5). Die minimal sinnvolle echte
Restleerstelle ist **P4 (PMTiles-Strukturvalidierung jenseits der Magic-Bytes)**,
flankiert von der Konsolidierung der Dokumentation.

Empfehlung: **MAP-PROOF-002 — Real PMTiles structural validation fixture**.

Minimaler Scope (siehe Abschnitt 8/9):

- kleines, eindeutig referenziertes PMTiles-Fixture **oder** ein klar benannter
  Artefaktpfad (kein grosser Hamburg-/Deutschland-Build im normalen CI),
- Validierung ueber Magic hinaus: PMTiles-v3-Header (Spec-Version, Root-Dir-Offset/Length,
  Metadata) **oder** ein einzelner Tile-Read/Metadata-Inspect,
- `proof-summary.json` erzeugen,
- Statusmatrix entsprechend differenziert aktualisieren.

Nicht in MAP-PROOF-002: produktionsnaher Caddy-Proof (P7), Pixelvergleich (P6),
Reproduzierbarkeits-Pinning — das sind eigene, spaeter zu schneidende Schritte.

## 8. Empfohlene Fixture-Strategie

| Option | Beschreibung | Reproduzierbarkeit | Repo-Gewicht | Netzrisiko | Beweiskraft | Empfehlung |
| --- | --- | --- | --- | --- | --- | --- |
| A: winziges echtes PMTiles-Fixture im Repo | 1–2-Tile-Mini-PMTiles (wenige KB) committen | hoch (statischer Hash) | gering (KB) | keins | mittel–hoch (Struktur real pruefbar) | **empfohlen** |
| B: Mini-Build aus winzigem OSM-Extract in CI | sehr kleiner bbox-Extract → Planetiler | mittel | gering | mittel (Download) | hoch | Fallback, wenn A nicht erzeugbar |
| C: bestehender Hamburg-Build wiederverwenden | Artefakt aus `pmtiles-content`-Job teilen | niedrig (env-abhaengig) | keins | bereits vorhanden | hoch (aber schwer) | nur fuer P4 ungeeignet schwer/langsam |
| D: rein synthetischer PMTiles-Header | handgebauter, gueltiger v3-Header ohne echte Tiles | hoch | minimal | keins | niedrig–mittel (Struktur, kein echter Inhalt) | nur als Ergaenzung zu A |

Begruendung: Option A liefert echten, reproduzierbaren Strukturinhalt bei minimalem
Repo-Gewicht und ohne Netzrisiko — passt zu den Nicht-Zielen (kein grosser Build,
kein unbegrenzter Download, keine grosse PMTiles-Datei).

## 9. Proof-Summary-v1 Vorschlag

PROVEN-Form (Beispiel fuer MAP-PROOF-002, Scope `pmtiles-content`):

```json
{
  "id": "MAP-PROOF-002",
  "status": "PROVEN",
  "scope": "pmtiles-content",
  "artifact_kind": "real_map",
  "checked_at": "2026-06-15T00:00:00Z",
  "caddy": {
    "config": "infra/caddy/Caddyfile.proof",
    "image": "caddy:2.7"
  },
  "pmtiles": {
    "path": "build/basemap/basemap-hamburg-v0.1.0.pmtiles",
    "sha256": "3eea9946f90a1cca425916c5b3272692ae8a1030bf22e700b67908cfafee8eab",
    "kind": "hamburg",
    "structural_validation": "magic"
  },
  "http": {
    "range_status": 206,
    "accept_ranges": true,
    "content_range": "bytes 0-511/23948909"
  },
  "visual": {
    "screenshot": "build/proofs/basemap-visual/screenshot.png",
    "network_proof": "build/proofs/basemap-visual/proof-summary.json"
  },
  "does_not_establish": [
    "pmtiles_structure_beyond_magic",
    "visual_correctness_pixel",
    "production_like_caddy",
    "cross_environment_reproducibility"
  ]
}
```

NOT_PROVEN-Form (fuer die echte Restleerstelle P4):

```json
{
  "id": "MAP-PROOF-002",
  "status": "NOT_PROVEN",
  "scope": "pmtiles-structure",
  "missing": [
    "pmtiles_v3_header_parse",
    "root_directory_offset_length_check",
    "metadata_block_inspect_or_tile_read"
  ],
  "reason": "Guard validiert nur die 7-Byte-Magic; Tile-Directory/Metadata/Tile-Read fehlen."
}
```

## 10. Stop-Kriterien fuer spaetere Guards

Ein spaeterer harter Guard (nicht Teil dieses PRs) darf erst aktiviert werden, wenn:

- ein deterministisches, reproduzierbares Fixture (stabiler SHA256) vorliegt,
- der Strukturcheck ohne Netzwerk im normalen CI laeuft,
- der Guard zwischen `synthetic` und `real_map` sowie zwischen `magic`,
  `metadata` und `tile-read` unterscheidet,
- die Statusmatrix den Scope korrekt fuehrt (kein Sammel-`PROVEN`).

Bis dahin gilt: lieber sichtbares `NOT_PROVEN` als falsches Gruen.

## 11. Tests / Checks

- `python3 -m scripts.docmeta.check_links`
- `python3 -m scripts.docmeta.validate_doc_freshness_registry` (nicht blockierend)
- `make validate-core`
- `git diff --check`

Scope-Gate: keine Aenderung an Runtime-Code, Infra, Workflows, Skripten, Contracts
oder Lockfiles. Aenderungen ausschliesslich in `docs/`.

## Essenz

- **Bewiesen (mit Scope):** P0 (static config), P1 (mocked client), P2 (Caddy-Range,
  **synthetisch**), P3 (echtes PMTiles Magic+Hash, CI), P5 (Browser-/PMTiles-Protokollzugriff
  und Render-Initialisierung via **Vite**, CI).
- **Nicht bewiesen:** P4 (PMTiles-Struktur), die Vector-Tile-Payload-/Tile-Datenlieferung,
  P6 (visuelle **Korrektheit**), P7 (produktionsnaher Caddy) sowie Cross-Env-Reproduzierbarkeit.
- **Kern-Reconciliation:** Die Statusdokumente **untertreiben** — der Visual-CI-Job
  ist gruen auf `main`, wird aber teils noch als `NOT_PROVEN`/`READY_FOR_CI_PROOF`
  gefuehrt; `pmtiles-content` ist gruen, in Roadmap/Phase6 aber noch offen.
- **Naechster PR:** MAP-PROOF-002 — Real PMTiles **structural** validation fixture
  (nicht „voller Production-Visual-Proof").
