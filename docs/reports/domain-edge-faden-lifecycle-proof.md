---
id: reports.domain-edge-faden-lifecycle-proof
title: "Domain Edge — Faden-Lifecycle-Proof"
doc_type: report
status: active
lifecycle_state: active
lifecycle: proof
owner_task: OPT-ARC-001
created: 2026-07-17
review_after: 2026-10-17
canonicality: evidence
lang: de
summary: >
  Lokaler, diffgebundener Implementierungs- und Regressionstest für den
  exakt 168 Stunden langen Lebenszyklus unverzwirnter Fäden einschließlich
  rückwirkender Ableitung für datierte Legacy-Projektionen ohne persistiertes
  expires_at. Belegt sind servereigene Ablaufzeit, Filterung vor Paginierung,
  404 nach Ablauf und kontinuierliches lineares Kartenverblassen.
  Garn und Verzwirnung bleiben ein eigener, noch zu spezifizierender Vertrag.
relations:
  - type: supersedes
    target: docs/reports/domain-edge-write-path-proof.md
  - type: relates_to
    target: docs/specs/garnrolle-knoten-faden.md
  - type: relates_to
    target: contracts/domain/edge.schema.json
---

# Domain Edge — Faden-Lifecycle-Proof

## Ergebnis

**LOCAL_PROVEN.** Jeder neu erzeugte Faden erhält serverseitig
`expires_at = created_at + 168 Stunden`. Clientwerte für `created_at` und
`expires_at` bleiben verboten. Ab `now == expires_at` verschwindet der Faden
aus aktiven Listen, Einzelabrufen, Account-Projektionen und der Karte. Seine
persistierte Webungsaktion wird nicht gelöscht. Für bestehende Projektionen mit
gültigem `created_at`, aber fehlendem `expires_at`, wird dieselbe Grenze beim
Lesen abgeleitet, ohne gespeicherte Daten oder die Chronik umzuschreiben.

## Belegte Semantik

| Achse | Vertrag |
|---|---|
| Zeitautorität | API-Server setzt `created_at` und leitet `expires_at` daraus ab. |
| Dauer | Exakt 168 Stunden; keine Konfiguration und kein Refresh durch spätere Aktionen. |
| JSONL | Neue Fäden speichern beide Zeitstempel. Datierte Legacy-Zeilen ohne `expires_at` bleiben unverändert. |
| PostgreSQL | `created_at` bleibt Spalte; `expires_at` wird für neue Fäden im bestehenden JSONB-Payload gespeichert und beim Reload rekonstruiert. |
| Aktive Projektion | Filterung erfolgt vor Offset- und Cursor-Paginierung; Einzelabruf liefert nach Ablauf 404. |
| Nebenprojektion | Account-Details verwenden denselben aktiven Fadenprädikat. |
| Darstellung | Die lineare Deckkraft wird aus vorgeparsten Millisekunden berechnet und minütlich neu projiziert; ein separater Einmal-Timer entfernt den nächsten Faden exakt bei `expires_at`. |
| Legacy | Fehlt das `expires_at`-Feld ganz, wird es aus einem gültigen `created_at` exakt abgeleitet. Vollständig undatierte Datensätze bleiben sichtbar; Persistenz und Chronik werden nicht verändert. |
| Korruption | Ungültige vorhandene Zeitstempel, ein explizites `expires_at: null` bei datiertem `created_at`, strukturell fehlerhafte PostgreSQL-Payload-Werte sowie explizite, nicht exakt 168 Stunden auseinanderliegende Grenzen werden fail-closed ausgeblendet beziehungsweise beim Laden übersprungen — keiner dieser Fälle wird mit dem legitimen, fehlenden Feld verwechselt. |
| Garn | Dauerhaft und ausgenommen, aber ohne geratenes Feld oder öffentliches CRUD; eigener Folgeauftrag. |

## Revalidierung 2026-07-29

- API-Lifecycle-Unit-Tests: 9 bestanden, 0 fehlgeschlagen.
- API-Edge-Integrationstests: 28 bestanden, 0 fehlgeschlagen. Enthalten ist ein
  vor Einführung des Lifecycle-Vertrags erzeugter Faden mit `created_at`, aber
  ohne `expires_at`, der vor Paginierung gefiltert wird und im Einzelabruf 404
  liefert.
- Karten-Lifecycle-Tests: 5 bestanden, 0 fehlgeschlagen.
- Svelte-Typ- und Komponentenprüfung: 0 Fehler, 0 Warnungen.
- Domain-Contracts: sechs Schemata und alle Beispielinstanzen bestanden.
- Rust-Formatprüfung, Clippy mit Warnungen als Fehler und Web-Lint: bestanden.

Nicht als neue lokale Evidenz behauptet werden der vollständige Web-Build, das
gesamte API-Testkorpus, `cargo deny` und die Remote-CI. Diese Prüfungen bleiben
den repositoryweiten beziehungsweise PR-gebundenen Gates vorbehalten.

## Revalidierung 2026-07-30

Drei von Codex gemeldete Befunde auf dem vorherigen Head sind behoben:

- P2: Die API unterschied beim JSONL- und PostgreSQL-Laden ein fehlendes
  `expires_at` nicht von einem explizit gespeicherten `expires_at: null`,
  wodurch ein datierter Legacy-Faden mit explizitem `null` fälschlich eine
  rückwirkend abgeleitete Ablaufzeit erhielt statt fail-closed ausgeblendet zu
  werden. `Edge.expires_at` ist jetzt ein Tri-State
  (`Option<Option<LifecycleTimestamp>>`), rund-trip-fest für beide
  Persistenzpfade.
- P2: Die Kartengrenze (`edgeLifecycle.ts`) behandelte ein fehlendes
  `created_at` wie den undatierten Legacy-Zustand statt es als nichtkonform
  abzulehnen; sie unterscheidet jetzt `undefined` (immer ungültig) von einem
  expliziten `null` (nur mit explizitem `expires_at: null` gültig).
- P3: Eine strukturell fehlerhafte (weder fehlende, `null`- noch String-)
  `expires_at`-Nutzlast im PostgreSQL-JSONB-Payload wurde zuvor stillschweigend
  wie ein explizites `null` behandelt; bei fehlendem `created_at` hätte das
  denselben Datensatz wie einen legitimen, dauerhaft sichtbaren undatierten
  Altbestand erscheinen lassen. Der PostgreSQL-Ladepfad überspringt solche
  Zeilen jetzt mit einer Warnung, statt sie zu maskieren.

Aktualisierte lokale Prüfbelege:

- API-Lifecycle-Unit-Tests (`routes::edges::tests`): 10 bestanden, 0
  fehlgeschlagen (zuvor 9; neuer Test deckt das explizite `null` bei
  datiertem `created_at` ab).
- Neue PostgreSQL-Payload-Unit-Tests (`domain_db::edge_write_path_tests`): 3
  zusätzliche Tests für die Tri-State-Unterscheidung und das Verwerfen
  strukturell fehlerhafter Nutzlasten.
- Karten-Lifecycle-Tests: 6 bestanden, 0 fehlgeschlagen (zuvor 5; neuer Test
  deckt das fehlende `created_at` an der Kartengrenze ab).
- Vollständige lokale Rust-Bibliothekstests (470 bestanden), `cargo clippy
  --all-targets -- -D warnings` und `cargo fmt --check`: bestanden.
- Vollständige lokale Web-Vitest-Suite (275 bestanden über 36 Dateien),
  `svelte-check` (0 Fehler) und `pnpm lint`: bestanden.
- `just contracts-domain-check`: alle sechs Schemata und Beispielinstanzen
  weiterhin gültig; dieser Fix ändert kein Schema.

## Grenzen und Folgetasks

- Vollständig undatierte Legacy-Projektionen bleiben sichtbar, weil ihr Alter
  nicht ohne Schätzung rekonstruiert werden kann.
- Abgelaufene Projektionen bleiben aus Chronik- und Idempotenzgründen
  persistiert; sichere Archivierung oder Kompaktion ist separat registriert.
- Die feste Sieben-Tage-Frist besitzt keine Runtime-Oberfläche mehr; AppConfig
  weist die entfernten Schlüssel `fade_days` und `HA_FADE_DAYS` fail-closed ab.
- Garn und Verzwirnung benötigen einen eigenen Domänen-, Ereignis- und
  Persistenzvertrag.
- Endpoint- und Ablaufindexierung für sehr große Edge-Bestände ist als
  `WELTGEWEBE-EDGE-PROJECTION-INDEX-BENCH-V1` in Bureau-PR #649 registriert; sie
  erfordert zuerst eine reproduzierbare 500k-Messung.
- MapLibre-Feature-State ist als `WELTGEWEBE-MAP-EDGE-FEATURE-STATE-V1` in
  Bureau-PR #649 registriert und bleibt profilinggebunden, weil der auf 250
  Fäden begrenzte minütliche `setData`-Pfad derzeit keinen belegten Engpass
  darstellt.
- Remote-CI- und Live-Evidence werden nach PR und Merge ergänzt; dieser Bericht
  behauptet bis dahin ausschließlich den lokal reproduzierten Stand.
