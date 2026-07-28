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
  exakt 168 Stunden langen Lebenszyklus neu abgeleiteter, unverzwirnter Fäden.
  Belegt sind servereigene Ablaufzeit, JSONL-/PostgreSQL-Mapping, Filterung vor
  Paginierung, 404 nach Ablauf, Account-Projektion und kontinuierliches lineares Kartenverblassen.
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
persistierte Webungsaktion wird nicht gelöscht.

## Belegte Semantik

| Achse | Vertrag |
|---|---|
| Zeitautorität | API-Server setzt `created_at` und leitet `expires_at` daraus ab. |
| Dauer | Exakt 168 Stunden; keine Konfiguration und kein Refresh durch spätere Aktionen. |
| JSONL | Beide Zeitstempel landen in derselben dauerhaften Zeile und im Cache. |
| PostgreSQL | `created_at` bleibt Spalte; `expires_at` wird im bestehenden JSONB-Payload gespeichert und beim Reload rekonstruiert. |
| Aktive Projektion | Filterung erfolgt vor Offset- und Cursor-Paginierung; Einzelabruf liefert nach Ablauf 404. Zeitstempel werden beim Laden oder Erzeugen einmal geparst; der Request-Hot-Path vergleicht nur vorgeparste Werte. |
| Nebenprojektion | Account-Details verwenden denselben aktiven Fadenprädikat. |
| Darstellung | Die lineare Deckkraft wird aus vorgeparsten Millisekunden berechnet und minütlich als GeoJSON neu projiziert; der maximale Schritt beträgt weniger als 0,0001. Ein separater Einmal-Timer entfernt den nächsten Faden exakt bei `expires_at`. |
| Legacy | Datensätze ohne `expires_at` bleiben sichtbar; es wird keine rückwirkende Ablaufzeit geraten. |
| Korruption | Fehlende, ungültige oder nicht exakt 168 Stunden auseinanderliegende Zeitstempel werden fail-closed ausgeblendet. |
| Garn | Dauerhaft und ausgenommen, aber ohne geratenes Feld oder öffentliches CRUD; eigener Folgeauftrag. |

## Lokale Prüfbelege

- Web-Produktionsbuild einschließlich Route-Performance-Budget: bestanden.
- Web-CI: Budget-, Public-Asset-, Prettier-, ESLint- und Svelte-Checks bestanden.
- Web-Unit-Tests: 160 bestanden, 0 fehlgeschlagen; Lifecycle-Normalisierung, minütlicher Refresh, Offsetgrenzen und exakte Ablaufplanung sind getrennt getestet.
- API `cargo fmt`, `cargo clippy --all-targets --all-features -D warnings` und Build: bestanden.
- API-Testkorpus: alle nicht ignorierten Unit- und Integrationstests bestanden;
  darunter 370 Library-Tests, 28 Edge-Tests, 13 Account-Tests und die neuen
  Ablauf-/Paginierungs-/Account-Projektionstests.
- `cargo deny check`: Advisories, Bans, Lizenzen und Quellen bestanden.
- Domain-Contracts: alle sechs Schemas sowie alle Beispiele bestanden.
- Demo-Daten-Vertrag und Repository-Lint: bestanden.

## Grenzen und Folgetasks

- Abgelaufene Projektionen bleiben aus Chronik- und Idempotenzgründen
  persistiert; sichere Archivierung/Kompaktion ist separat registriert.
- Die feste Sieben-Tage-Frist besitzt keine Runtime-Oberfläche mehr; AppConfig
  weist die entfernten Schlüssel `fade_days` und `HA_FADE_DAYS` fail-closed ab.
- Garn und Verzwirnung benötigen einen eigenen Domänen-, Ereignis- und
  Persistenzvertrag.
- Endpoint-/Ablaufindexierung für sehr große Edge-Bestände ist als `WELTGEWEBE-EDGE-PROJECTION-INDEX-BENCH-V1` in Bureau-PR #649 registriert; sie erfordert zuerst eine reproduzierbare 500k-Messung.
- MapLibre-Feature-State ist als `WELTGEWEBE-MAP-EDGE-FEATURE-STATE-V1` in Bureau-PR #649 registriert und bleibt profilinggebunden, weil der auf 250 Fäden begrenzte minütliche `setData`-Pfad derzeit keinen belegten Engpass darstellt.
- Remote-CI- und Live-Evidence werden nach PR und Merge ergänzt; dieser Bericht
  behauptet bis dahin ausschließlich den lokal reproduzierten Stand.
