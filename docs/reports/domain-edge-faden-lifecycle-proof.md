---
id: reports.domain-edge-faden-lifecycle-proof
title: "Domain Edge — Faden-Lifecycle-Proof"
doc_type: report
status: active
lifecycle_state: active
lifecycle: proof
owner_task: WELTGEWEBE-FADEN-VERFALL-V1-T001
created: 2026-07-17
review_after: 2026-10-17
canonicality: evidence
lang: de
summary: >
  Lokaler, diffgebundener Implementierungs- und Regressionstest für den
  exakt 168 Stunden langen Lebenszyklus neu abgeleiteter, unverzwirnter Fäden.
  Belegt sind servereigene Ablaufzeit, JSONL-/PostgreSQL-Mapping, Filterung vor
  Paginierung, 404 nach Ablauf, Account-Projektion und lineares Kartenverblassen.
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
| Aktive Projektion | Filterung erfolgt vor Offset- und Cursor-Paginierung; Einzelabruf liefert nach Ablauf 404. |
| Nebenprojektion | Account-Details verwenden denselben aktiven Fadenprädikat. |
| Darstellung | Deckkraft fällt linear von 1 auf 0; der Kartenzeitpunkt wird minütlich aktualisiert. |
| Legacy | Datensätze ohne `expires_at` bleiben sichtbar; es wird keine rückwirkende Ablaufzeit geraten. |
| Korruption | Fehlende, ungültige oder nicht exakt 168 Stunden auseinanderliegende Zeitstempel werden fail-closed ausgeblendet. |
| Garn | Dauerhaft und ausgenommen, aber ohne geratenes Feld oder öffentliches CRUD; eigener Folgeauftrag. |

## Lokale Prüfbelege

- Web-Produktionsbuild einschließlich Route-Performance-Budget: bestanden.
- Web-CI: Budget-, Public-Asset-, Prettier-, ESLint- und Svelte-Checks bestanden.
- Web-Unit-Tests: 159 bestanden, 0 fehlgeschlagen.
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
- Die alte `fade_days`-Konfiguration ist nicht die Zeitautorität des festen
  Fadenvertrags und muss separat bereinigt oder eindeutig umgewidmet werden.
- Garn und Verzwirnung benötigen einen eigenen Domänen-, Ereignis- und
  Persistenzvertrag.
- Remote-CI- und Live-Evidence werden nach PR und Merge ergänzt; dieser Bericht
  behauptet bis dahin ausschließlich den lokal reproduzierten Stand.
