### 📄 weltgewebe/docs/README.md

**Größe:** 372 B | **md5:** `d97277ef89d096355ecc33689f5e89a9`

```markdown
# Weltgewebe – Doku-Index

– **Start:** architekturstruktur.md
– **Techstack:** techstack.md
– **Prozess & Fahrplan:** process/README.md
– **ADRs:** adr/
– **Runbooks:** runbooks/README.md
– **Glossar:** glossar.md
– **Inhalt/Story:** inhalt.md, zusammenstellung.md
– **X-Repo Learnings:** x-repo/peers-learnings.md
– **Beitragen:** ../CONTRIBUTING.md
```

### 📄 weltgewebe/docs/architekturstruktur.md

**Größe:** 6 KB | **md5:** `b5ceafe29f2d968072fa413f468ba026`

```markdown
Weltgewebe – Repository-Struktur

Dieses Dokument beschreibt den Aufbau des Repositories.
Ziel: Übersicht für Entwickler und KI, damit alle Beiträge am richtigen Ort landen.

⸻

ASCII-Baum

weltgewebe/weltgewebe-repo/
├─ apps/                       # Anwendungen (Business-Code)
│  ├─ web/                      # SvelteKit-Frontend (PWA, MapLibre)
│  │  ├─ src/
│  │  │  ├─ routes/             # Seiten, Endpunkte (+page.svelte/+server.ts)
│  │  │  ├─ lib/                # UI-Komponenten, Stores, Utilities
│  │  │  ├─ hooks.client.ts     # RUM-Initialisierung (LongTasks)
│  │  │  └─ app.d.ts            # App-Typdefinitionen
│  │  ├─ static/                # Fonts, Icons, manifest.webmanifest
│  │  ├─ tests/                 # Frontend-Tests (Vitest, Playwright)
│  │  ├─ svelte.config.js
│  │  ├─ vite.config.ts
│  │  └─ README.md
│  │
│  ├─ api/                      # Rust (Axum) – REST + SSE
│  │  ├─ src/
│  │  │  ├─ main.rs             # Einstiegspunkt, Router
│  │  │  ├─ routes/             # HTTP- und SSE-Endpunkte
│  │  │  ├─ domain/             # Geschäftslogik, Services
│  │  │  ├─ repo/               # SQLx-Abfragen, Postgres-Anbindung
│  │  │  ├─ events/             # Outbox-Publisher, Eventtypen
│  │  │  └─ telemetry/          # Prometheus/OTel-Integration
│  │  ├─ migrations/            # Datenbankschemata, pg_partman
│  │  ├─ tests/                 # API-Tests (Rust)
│  │  ├─ Cargo.toml
│  │  └─ README.md
│  │
│  ├─ worker/                   # Projector/Indexer/Jobs
│  │  ├─ src/
│  │  │  ├─ projector_timeline.rs # Outbox→Timeline-Projektion
│  │  │  ├─ projector_search.rs   # Outbox→Search-Indizes
│  │  │  └─ replayer.rs           # Rebuilds (DSGVO/DR)
│  │  ├─ Cargo.toml
│  │  └─ README.md
│  │
│  └─ search/                   # (optional) Such-Adapter/SDKs
│     ├─ adapters/              # Typesense/Meili-Clients
│     └─ README.md
│
├─ packages/                    # (optional) Geteilte Libraries/SDKs
│  └─ README.md
│
├─ infra/                       # Betrieb/Deployment/Observability
│  ├─ compose/                  # Docker Compose Profile
│  │  ├─ compose.core.yml       # Basis-Stack: web, api, db, caddy
│  │  ├─ compose.observ.yml     # Monitoring: Prometheus, Grafana, Loki/Tempo
│  │  ├─ compose.stream.yml     # Event-Streaming: NATS/JetStream
│  │  └─ compose.search.yml     # Suche: Typesense/Meili, KeyDB
│  ├─ caddy/
│  │  ├─ Caddyfile              # Proxy, HTTP/3, CSP, TLS
│  │  └─ README.md
│  ├─ db/
│  │  ├─ init/                  # SQL-Init-Skripte, Extensions (postgis, h3)
│  │  ├─ partman/               # Partitionierung (pg_partman)
│  │  └─ README.md
│  ├─ monitoring/
│  │  ├─ prometheus.yml         # Prometheus-Konfiguration
│  │  ├─ grafana/
│  │  │  ├─ dashboards/         # Web-Vitals, JetStream, Edge-Kosten
│  │  │  └─ alerts/             # Alarme: Opex, Lag, LongTasks
│  │  └─ README.md
│  ├─ nomad/                    # (optional) Orchestrierungsspezifikationen
│  └─ k8s/                      # (optional) Kubernetes-Manifeste
│
├─ docs/                        # Dokumentation & Entscheidungen
│  ├─ adr/                      # Architecture Decision Records
│  ├─ techstack.md              # Techstack v3.2 (Referenz)
│  ├─ architektur.ascii         # Architektur-Poster/ASCII-Diagramme
│  ├─ datenmodell.md            # Datenbank- und Projektionstabellen
│  └─ runbook.md                # Woche-1/2 Setup, DR/DSGVO-Drills
│
├─ ci/                          # CI/CD & Qualitätsprüfungen
│  ├─ github/
│  │  └─ workflows/             # GitHub Actions für Build, Tests, Infra
│  │     ├─ web.yml
│  │     ├─ api.yml
│  │     └─ infra.yml
│  ├─ scripts/                  # Hilfsskripte (migrate, seed, db-wait)
│  └─ budget.json               # Performance-Budgets (≤60KB JS, ≤2s TTI)
│
├─ .env.example                 # Beispiel-Umgebungsvariablen
├─ .editorconfig                # Editor-Standards
├─ .gitignore                   # Ignorier-Regeln
├─ LICENSE                      # Lizenztext
└─ README.md                    # Projektüberblick, Quickstart

⸻

Erläuterungen zu den Hauptordnern

- **apps/**
  Enthält alle Anwendungen: Web-Frontend (SvelteKit), API (Rust/Axum), Worker (Eventprojektionen, Rebuilds) und
  optionale Search-Adapter. Jeder Unterordner ist eine eigenständige App mit eigenem README und Build-Konfig.
- **packages/**
  Platz für geteilte Libraries oder SDKs, die von mehreren Apps genutzt werden. Wird erst angelegt, wenn Bedarf an
  gemeinsamem Code entsteht.
- **infra/**
  Infrastruktur- und Deployment-Ebene. Compose-Profile für verschiedene Betriebsmodi, Caddy-Konfiguration,
  DB-Init, Monitoring-Setup. Optional Nomad- oder Kubernetes-Definitionen für spätere Skalierung.
- **docs/**
  Dokumentation und Architekturentscheidungen. Enthält ADRs, Techstack-Beschreibung, Diagramme,
  Datenmodellübersicht und Runbooks.
- **ci/**
  Alles rund um Continuous Integration/Deployment: Workflows für GitHub Actions, Skripte für Tests/DB-Handling,
  sowie zentrale Performance-Budgets (Lighthouse).
- **Root**
  Repository-Metadaten: .env.example (Vorlage), Editor- und Git-Configs, Lizenz und README mit Projektüberblick.

⸻

Zusammenfassung

Diese Struktur spiegelt den aktuellen Techstack (v3.2) wider:

- Mobil-first via PWA (SvelteKit).
- Rust/Axum API mit Outbox/JetStream-Eventing.
- Compose-first Infrastruktur mit klar getrennten Profilen.
- Observability und Compliance fest verankert.
- Erweiterbar durch optionale packages/, nomad/, k8s/.

Dies dient als Referenzrahmen für alle weiteren Arbeiten am Weltgewebe-Repository.
```

### 📄 weltgewebe/docs/datenmodell.md

**Größe:** 4 KB | **md5:** `40e5e1201281b9d2cf8e6928c999fffb`

```markdown
# Datenmodell

Dieses Dokument beschreibt das Datenmodell der Weltgewebe-Anwendung, das auf PostgreSQL aufbaut.
Es dient als Referenz für Entwickler, um die Kernentitäten, ihre Beziehungen und die daraus
abgeleiteten Lese-Modelle zu verstehen.

## Grundprinzipien

- **Source of Truth:** PostgreSQL ist die alleinige Quelle der Wahrheit.
- **Transaktionaler Outbox:** Alle Zustandsänderungen werden transaktional in die `outbox`-Tabelle
  geschrieben, um eine konsistente Event-Verteilung an nachgelagerte Systeme (z.B. via NATS
  JetStream) zu garantieren.
- **Normalisierung:** Das Schreib-Modell ist normalisiert, um Datenintegrität zu gewährleisten.
  Lese-Modelle (Projektionen/Views) sind für spezifische Anwendungsfälle denormalisiert und
  optimiert.
- **UUIDs:** Alle Primärschlüssel sind UUIDs (`v4`), um eine verteilte Generierung zu
  ermöglichen und Abhängigkeiten von sequenziellen IDs zu vermeiden.

---

## Tabellen (Schreib-Modell)

### `nodes`

Speichert geografische oder logische Knotenpunkte, die als Anker für Threads dienen.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | `uuid` (PK) | Eindeutiger Identifikator des Knotens. |
| `location` | `geography(Point, 4326)` | Geografischer Standort (Längen- und Breitengrad). |
| `h3_index`| `bigint` | H3-Index für schnelle geografische Abfragen. |
| `name` | `text` | Anzeigename des Knotens. |
| `created_at` | `timestamptz` | Zeitstempel der Erstellung. |
| `updated_at` | `timestamptz` | Zeitstempel der letzten Änderung. |

### `roles`

Verwaltet Benutzer- oder Systemrollen, die Berechtigungen steuern.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | `uuid` (PK) | Eindeutiger Identifikator der Rolle. |
| `user_id` | `uuid` (FK) | Referenz zum Benutzer (externes System). |
| `permissions` | `jsonb` | Berechtigungen der Rolle als JSON-Objekt. |
| `created_at` | `timestamptz` | Zeitstempel der Erstellung. |

### `threads`

Repräsentiert die Konversationen oder "Fäden", die an Knoten gebunden sind.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | `uuid` (PK) | Eindeutiger Identifikator des Threads. |
| `node_id` | `uuid` (FK, `nodes.id`) | Zugehöriger Knoten. |
| `author_role_id` | `uuid` (FK, `roles.id`) | Ersteller des Threads. |
| `title` | `text` | Titel des Threads. |
| `content` | `text` | Inhalt des Threads (z.B. erster Beitrag). |
| `created_at` | `timestamptz` | Zeitstempel der Erstellung. |
| `updated_at` | `timestamptz` | Zeitstempel der letzten Änderung. |

### `outbox`

Implementiert das Transactional Outbox Pattern für zuverlässige Event-Publikation.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | `uuid` (PK) | Eindeutiger Identifikator des Events. |
| `aggregate_type` | `text` | Typ des Aggregats (z.B. "thread"). |
| `aggregate_id` | `uuid` | ID des betroffenen Aggregats. |
| `event_type` | `text` | Typ des Events (z.B. "thread.created"). |
| `payload` | `jsonb` | Event-Daten. |
| `created_at` | `timestamptz` | Zeitstempel der Erstellung. |

---

## Projektionen (Lese-Modelle)

Diese Views sind für die Lese-Performance optimiert und fassen Daten aus mehreren Tabellen zusammen.
Sie werden von den Workern (Projektoren) asynchron aktualisiert.

### `public_role_view`

Eine denormalisierte Sicht auf Rollen, die nur öffentlich sichtbare Informationen enthält.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `role_id` | `uuid` | Identifikator der Rolle. |
| `display_name` | `text` | Öffentlich sichtbarer Name (ggf. aus einem externen User-Service). |
| `avatar_url` | `text` | URL zu einem Avatar-Bild. |

### `faden_view`

Eine zusammengefasste Ansicht von Threads für die schnelle Darstellung in der Benutzeroberfläche.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `thread_id` | `uuid` | Identifikator des Threads. |
| `node_id` | `uuid` | Zugehöriger Knoten. |
| `node_name` | `text` | Name des zugehörigen Knotens. |
| `author_display_name` | `text` | Anzeigename des Autors. |
| `title` | `text` | Titel des Threads. |
| `comment_count` | `integer` | Anzahl der Kommentare (wird vom Projektor berechnet). |
| `last_activity_at` | `timestamptz` | Zeitstempel der letzten Aktivität. |
| `created_at` | `timestamptz` | Zeitstempel der Erstellung. |
```

### 📄 weltgewebe/docs/geist und plan.md

**Größe:** 12 KB | **md5:** `02c86341270901daedfb5e5634e4493f`

```markdown
Hier ist eine (meinerseits strukturierte) Analyse und Extraktion des „Geistes und Plans“ der Weltweberei basierend auf der Website weltweberei.org. Ich ziehe aus den öffentlich verfügbaren Texten, sortiere nach Themen und ziehe Schlussfolgerungen — du kannst damit weiterarbeiten oder ich helfe dir beim Verdichten / Operationalisieren.

⸻

1. Einleitende, normative Aussagen – der Geist

Diese Passagen geben dir Einsicht in die philosophische / normative Grundhaltung hinter dem Projekt:
	•	Der Name Weltweberei legt den Fokus auf Verflechtung, Weben, Verknüpfen („weben der welt, wie es jedem (!) gefällt“)
	•	Es handelt sich um ein Konzept eines „sichtbaren, gemeinschaftlich ausgehandelten Zusammenwirkens von Nachbarschaften, versammelt um ein gemeinsames Konto“.
	•	Die Teilhabe ist ausdrücklich offen und frei: „anschauen kostet nichts, beitreten … auch nichts, dabei sein auch nicht – nichts kostet irgendetwas.“
	•	Es besteht eine Intention zur freiwilligen Gegenseitigkeit: man kann von Gemeinschaftsressourcen profitieren, aber auch zurückgeben, in welcher Form man will.
	•	Transparenz und Freiwilligkeit sind zentral, insbesondere in Bezug auf Daten: keine Datenerhebung ohne dein Einverständnis, kein Tracking, keine automatische Profilbildung. Nur das, was du freiwillig sichtbar machst, erscheint öffentlich.
	•	Die Struktur ist bewusst offen, flexibel und änderbar: „alles ist jederzeit kollektiv aushandelbar – alles!“
	•	Der Weg ist offen / ergebnisoffen: „der Weg ist das Ziel!“
	•	Es gibt einen utopischen Horizont: ein global anschlussfähiges Netz von Ortszellen, überregionale Zusammenschlüsse ohne Entmachtung der lokalen Zellen, und sogar die Vision eines Ausstiegs aus dem vorherrschenden Geldsystem als denkbare Zukunft.

Kurz gesagt: Der Geist ist partizipativ, dezentral, transparent, nicht-hierarchisch, offen verhandelbar und zukunftsgerichtet. Es geht um kollektive Selbstorganisation, Verantwortung und Autonomie in einem vernetzten Raum.

⸻

2. Funktionale / strukturelle Elemente – der Plan (in Ansätzen)

Neben dem Geist gibt es auf der Website Hinweise auf konkrete Strukturen und Konzepte, wie man dieses Ideal operationalisieren möchte:

Baustein	Zweck / Idee	Bemerkungen & Herausforderungen
Weltgewebe / Karte	Die Plattform oder Leinwand, auf der Aktionen, Wünsche, Kommentare und Verantwortungsübernahmen visualisiert werden.	Hier liegt ein Kern bei dir: wie visualisiert man Fäden, Knoten, Wechselwirkungen?
Ortsgewebekonto	Jedes “Ortsweberei” hat ein gemeinsames Konto, auf das Spenden eingehen und von dem Auszahlungen per Antrag möglich sind – und das im Netz (Karte) sichtbar ist.	Governance von Konten, Transparenz, Zugriffssteuerung, Antragssysteme sind zu designen
Partizipartei / Mandatssystem	Politischer Arm der Ortswebereien: “Fadenträger” fungieren als Mandatsträger, „Fadenreicher“ als Vermittler / Sekretäre. Ihre Arbeit wird öffentlich (gestreamt), Input kann live durch Community eingegeben werden (gefiltert via Up/Down-Voting, Plattform-KI). Stimmen können delegiert (transitär) werden.	Das Mandats- und Delegationssystem muss wasserdicht und nachvollziehbar gestaltet sein (Spielregeln, Sicherheit, Sybil-Schutz etc.).
Skalierbarkeit und Föderation	Ortswebereien sind Zellen; überregionale Bündnisse könnten gemeinsame Konten bilden, aber ohne die Basis zu entmachten. Lokale Entscheidungen bleiben vorherrschend.	Die Herausforderung einer föderalen Architektur mit Rückbindung und Reversibilität ist zentral.
Offene Anpassbarkeit	Jedes Element (Funktionen, Posten, Regeln) kann per Antrag verändert werden — also ein Meta-System zur Änderung der Regeln selbst.	Du brauchst ein Metagovernance-Modul: Regeln über Regeln.
Technische Infrastruktur & Datenschutz	Minimale Datenerhebung, nur das, was Nutzer:innen freiwillig veröffentlichen; temporäres Speichern von Serverlogs; keine automatische Profilbildung.	Datenschutz-Design, Sicherheit, Datenportabilität und Löschbarkeit müssen von Anfang an eingebaut sein.
Visionärer Horizont	In größeren Skalen kann man über Ausstieg aus dem Geldsystem, Verfassungsfragen, kollektive Selbstbestimmung nachdenken.	Diese Visionen sind (im Moment) noch eher hypothetisch. Du musst definieren, wie man von der Basis dorthin gelangen könnte.


⸻

3. Risiken, Widersprüche und offene Fragen

Damit du beim Weiterentwickeln gewappnet bist, hier ein paar erkennbare Spannungen oder Herausforderungen:
	1.	Governance vs. Skalierung — je größer das Netzwerk, desto höher ist die Gefahr von Koordinationsproblemen, Trittbrettfahrern, Machtkonzentration.
	2.	Sicherheit & Identitätsprobleme — wie verhinderst du Sybil-Attacken (falsche Mehrfachidentitäten), wie verifizierst du Mitgliedschaften, wie schützt du sensible Daten?
	3.	Effizienz vs. Inklusivität — partizipative Prozesse sind oft langsamer; wie verhinderst du Blockaden?
	4.	Delegation von Stimmen — das Modell ist spannend (Liquid Democracy), aber praktisch schwierig: wie oft darf delegiert werden, wie lange, wie wird Transparenz gewährleistet?
	5.	Konten & Geldflüsse — wie schafft man Sicherheit, Vertrauen und Transparenz in Finanztransaktionen über dezentrale Komponenten?
	6.	Technische Komplexität — Visualisierung von Geweben, Echtzeit-Interaktion, Skalierung, Datenschutz: das sind keine einfachen Aufgaben.
	7.	Motivations & Engagement-Problem — viele Projekte scheitern daran, dass die Community nicht dauerhaft aktiv bleibt.
	8.	Zwischen Vision und Implementierung — manche Visionen (z. B. Ausstieg aus dem Geldsystem) sind ambitioniert; der Übergang muss sorgfältig gestaltet werden.

⸻

4. Mein zusammengefasster “Geist & Plan” (in deiner Sprache, für deine Nutzung)

Wenn ich das für dein Projekt (Weltgewebe) zusammenfasse, um es nutzbar zu machen:
	•	Geist: Freiheit, Gemeinschaft, Transparenz, Verantwortung, partizipative Autonomie. Ein Raum, in dem Menschen freiwillig ihre Intentionen einbringen, sich verflechten und zusammenwirken, ohne dominante Hierarchien, und in dem Veränderung offen verhandelbar ist.
	•	Plan (Architektur):
	1.	Ein interaktives Karten-/Netzwerkinterface (Weltgewebe), das sichtbar macht, wie Menschen handeln, wünschen, Verantwortung übernehmen.
	2.	Lokale Zellen (“Ortswebereien”) mit eigenen Gemeinschaftskonten, Antragsprozessen und Governance.
	3.	Ein Mandats-/Delegationssystem (Partizipartei), um kollektive Entscheidungen zu treffen, bei maximaler Transparenz (z. B. Streaming, Chat & Voting).
	4.	Eine federative Struktur, die lokale Autonomie bewahrt, aber überregionale Kooperation erlaubt.
	5.	Ein Metasystem zur Anpassung und Veränderung von Regeln („Regeln über Regeln“) durch die Gemeinschaft.
	6.	Ein strenger Datenschutzansatz: nur selbsteingetragene Daten sichtbar, keine Profilbildung, Nutzerkontrolle über ihre Daten.
	7.	Ein visionärer Horizont, in dem globale Skalierung, alternative Wirtschaftsformen oder Systemwechsel denkbar sind — freilich erst als langfristige Option.

⸻

es geht vor allem um koordination von gemeinschaftsaktionen und -interessen: jemand möchte etwas auf die beine stellen, knüpft auf der karte am ort des geplanten handelns einen knoten, beispiel: gemeinsam grillen im park (parkspeise) am donnerstag um 17 uhr. dieser von ihm geknüpfte knoten wird automatisch per faden mit seiner rolle verknüpft (da er urheber ist), es entsteht dort neben den angelegten informationen ein gesprächsraum. andere, die durch diese visuelle plandarstellung auf das angebot aufmerksam geworden sind, können sich nun am gespräch darüber beteiligen oder zusagen etc.. jede aktion eines webers (eingeloggter nutzer) spinnt ebenso automatisch einen faden von dessen rolle zum jeweiligen knoten. kommt es nun zur parkspeise, gibt es natürlich für jedermann die möglichkeit etwas in die gemeinschaftskasse (gewebekonto) zu spenden - als eine art energieausgleich. möchte der urheber nun etwas aus dem gewebekonto erhalten (er hatte schließlich ausgaben etc.), dann muss er einen antrag auf auszahlung aus dem konto stellen.dies wird visualisiert durch einen antragsfaden auf das konto (eigener knoten auf der karte) inkl. 7 tage timer. kein einspruch eines anderen webers innerhalb der frist: auszahlung wird autorisiert. bei einspruch: verlängerung der entscheidung um weitere 7 tage mit anschließender abstimmung.


anderes praxisbeispiel: jeder kann die ressourcen, die er der gemeinschaft zur verfügung stellen will auf seiner garnrolle oder auf entsprechend verorteten knoten hinterlegen. sucht nun jemand nach beispielsweise einem schlafplatz, dann werden ihm alle in der umgebung angezeigt.

Kontextuelle Einordnung

Du hast Dateien hochgeladen, die Philosophie, Struktur und Tech-Stack des Weltgewebes dokumentieren:
	•	inhalt.md: Konzept + Funktionsweise
	•	zusammenstellung.md: systematische Zusammenfassung (Grundprinzipien, Domänenmodell, Governance)
	•	architekturstruktur.md: Repo-Struktur für Entwickler
	•	techstack.md: detaillierter Technologie-Stack

Damit liegt so etwas wie die DNA der Weltweberei vor: Vision, Plan, Architektur und konkrete technische Umsetzung.

⸻

Extraktion: Geist der Weltweberei
	•	Verflechtung als Leitmotiv: alles wird als Knoten und Fäden sichtbar, von Menschen bis Ressourcen.
	•	Radikale Transparenz & Freiwilligkeit: jede Handlung ein sichtbares Event, aber ohne verstecktes Tracking.
	•	Commons-Orientierung: keine künstliche Währung; Engagement und eingebrachte Ressourcen sind die „Währung“.
	•	Vergänglichkeit und Verzwirnung: Fäden verblassen, nur verzwirnte Inhalte werden dauerhaft – Dynamik statt Archivlast.
	•	Demokratische Prozesse: 7+7-Tage-Modell für Anträge, Liquid Democracy mit temporären Delegationen, offene Abstimmungen.
	•	Freiheit + Absicherung: jeder kann Ressourcen freigeben oder Aktionen starten, Anträge werden nur blockiert, wenn Widerspruch entsteht.
	•	Datenschutz: Privacy by Design, RoN-System für Anonymisierung, Unschärferadien für Ortsdaten.

⸻

Extraktion: Plan der Weltweberei
	1.	Domänenmodell
	•	Nutzer = Garnrollen (mit privatem und öffentlichem Bereich).
	•	Inhalte = Knoten (Ereignisse, Ressourcen, Ideen).
	•	Verbindungen = Fäden (Gespräch, Antrag, Delegation, Spende, etc.).
	2.	Funktionale Module
	•	Gewebekonto: Finanzverwaltung, sichtbar als Goldfäden.
	•	Webrat: Governance-Ort für Anträge, Abstimmungen, Delegationen.
	•	Nähstübchen: allgemeine Kommunikation.
	•	RoN-Platzhalter: Sammelstelle für anonymisierte Inhalte.
	3.	Zeitlichkeit & Prozesse
	•	7-Sekunden Sichtbarkeit bei Aktionen.
	•	7-Tage-Timer für Fäden, Knoten, Anträge.
	•	Verlängerung um 7 Tage bei Einspruch → Abstimmung.
	4.	Organisation
	•	Lokale Ortswebereien mit eigenen Konten.
	•	Föderation mehrerer Ortswebereien möglich.
	5.	Technik
	•	Frontend: SvelteKit, MapLibre, PWA.
	•	Backend: Rust (Axum), PostgreSQL + PostGIS + h3, Event-Outbox, NATS JetStream.
	•	Suche: Typesense / MeiliSearch.
	•	Infrastruktur: Nomad, Caddy (HTTP/3), PgBouncer.
	•	Observability: Prometheus, Grafana, Loki, Tempo.
	•	Security: SBOM, Signaturen, DSGVO-Forget-Pipeline, Key-Rotation.
	•	Kostenkontrolle: FinOps-KPIs (€/Session, €/GB Traffic).

⸻

Essenz-Kristall

👉 Die Weltweberei ist eine kartenbasierte Demokratie-Engine: jede Handlung wird als Faden sichtbar, jeder Knoten ist Raum für Aktionen oder Ressourcen, alle Prozesse laufen transparent, freiwillig, temporär und verhandelbar – technisch abgesichert durch Event-Sourcing, föderierbar in Ortsgeweben und getragen von einem klaren DSGVO-Privacy-by-Design.

⸻

Ironische Auslassung

„Früher musste man Plakate drucken und Flugblätter verteilen, um Nachbarn zum Grillen oder Couch-Sharing zu überreden – heute genügt ein Knoten auf der Karte. Demokratie trifft Picknick, mit JetStream und PgBouncer als unsichtbare Grillanzünder.“

⸻

∴fores Ungewissheit
	•	Grad: niedrig–mittel (30–40 %).
	•	Ursachen:
	•	Soziale Dynamik (wie dauerhaft beteiligen sich Leute?).
	•	Governance im Konfliktfall (Abstimmungen bei Missbrauch, Streit über Ressourcen).
	•	Technische Skalierung (Last > 100k Nutzer, Kostenpfad).
	•	Meta-Reflexion: viele Prinzipien sind definiert, aber die echte Bewährung liegt in der Praxis.

⸻

Kontrastvektor

Noch nicht thematisiert:
	•	Konfliktlösung jenseits Abstimmungen (z. B. Mediation).
	•	Schnittstellen zu externen Systemen (öffentliche Verwaltung, lokale Initiativen).
	•	Umgang mit kulturellen Unterschieden bei Föderation globaler Ortswebereien.

⸻
```

### 📄 weltgewebe/docs/glossar.md

**Größe:** 335 B | **md5:** `e1e1c4e097e48c0046706204cbb58a0d`

```markdown
# Glossar

**Rolle** (Garnrolle): auf Wohnsitz verorteter Account.
**Knoten:** lokalisierte Informationsbündel (Idee, Termin, Ort, Werkzeug…).
**Faden/Garn:** temporäre/persistente Verbindung Rolle→Knoten (Verzwirnung = Garn).
**RoN:** Rolle ohne Namen (Anonymisierung).
**Unschärferadius:** Öffentliche Genauigkeit in Metern.
```

### 📄 weltgewebe/docs/inhalt.md

**Größe:** 9 KB | **md5:** `aa4c1484b00984a155cf4eb98cdf4fb1`

```markdown
# Inhalt (MANDATORISCH)

## Was bedeutet Weltweberei?

welt = althochdeutsch weralt = menschenzeitalter
weben = germanisch webaną, indogermanisch webʰ- = flechten, verknüpfen, bewegen

Guten Tag,

schön, dass du hergefunden hast! Tritt gerne ein in unser Weltgewebe oder schau dir erstmal an, um was es
hier überhaupt geht.

Anschauen kostet nichts, beitreten (bald erst möglich) auch nicht, dabei sein auch nicht, nichts kostet
irgendetwas. Du kannst nach eigenem Ermessen und kollektiven Gutdünken von diesem Netzwerk an gemeinsamen
Ressourcen profitieren, bist gleichzeitig aber natürlich ebenso frei der Gemeinschaft etwas von dir
zurückzugeben – was auch immer, wie auch immer.

Weltweberei ist der Name dieses Konzeptes eines sichtbaren, gemeinschaftlich ausgehandelten Zusammenwirkens
von Nachbarschaften, versammelt um ein gemeinsames Konto. weltgewebe.net ist die Leinwand (Karte), auf der
die jeweiligen Aktionen, Wünsche, Kommentare und Verantwortungsübernahmen der Weltweber visualisiert werden
– als dynamisch sich veränderndes Geflecht von Fäden und Knoten.

## Wie funktioniert das Weltgewebe?

Jeder kann auf dem Weltgewebe (Online-Karte) alles einsehen. Wer sich mit Namen und Adresse registriert,
der bekommt eine Garnrolle auf seinen Wohnsitz gesteckt. Diese Rolle ermöglicht es einem Nutzer, sich aktiv
ins Weltgewebe einzuweben, solange er eingeloggt (sichtbar durch Drehung der Rolle) ist. Er kann nun also
neue Knoten (auf der Karte lokalisierte Informationsbündel, beispielsweise über geplante oder ständige
Ereignisse, Fragen, Ideen) knüpfen, sich mit bestehenden verbinden (Zustimmung, Interesse, Ablehnung,
Zusage, Verantwortungsübernahme, etc.), an Gesprächen (Threads auf einem Knoten) teilnehmen, oder Geld an
ein Ortsgewebekonto (Gemeinschaftskonto) spenden.

Jede dieser Aktionen erzeugt einen Faden, der von der Rolle zu dem jeweiligen Knoten führt. Jeder Faden
verblasst sukzessive binnen 7 Tagen. Auch Knoten lösen sich sukzessive binnen 7 Tagen auf, wenn es ein
datiertes Ereignis war und dieses vorbei ist, oder wenn seit 7 Tagen kein Faden (oder Garn) mehr zu diesem
Knoten geführt hat. Führt jedoch ein Garn zu einem Knoten (siehe unten), dann besteht dieser auch permanent,
bis das letzte zu ihm führende Garn entzwirnt ist. Kurzum: Knoten bestehen solange, wie noch etwas Garn oder
Faden zu ihm führt.

### Benutzeroberfläche und Navigation

Der linke Drawer enthält den Webrat und das Nähstübchen. Hier wird über alle ortsunabhängigen Themen
beraten (und abgestimmt. Generell kann jeder jederzeit Abstimmungen einleiten). Im Nähstübchen wird
einfach (orts-/kartenunabhängig) geplaudert. Das Ortsgewebekonto (oberer Slider) ist das
Gemeinschaftskonto. Hier gehen sowohl anonyme Spenden, als auch sichtbare Spenden (als Goldfäden von der
jeweiligen Rolle) ein. Hier, wie auch überall im Gewebe können Weber Anträge (auf Auszahlung, Anschaffung,
Veränderung, etc.) stellen.

Solch ein Antrag ist ebenso durch einen speziellen Antragsfaden mit der Rolle des Webers verbunden und
enthält sichtbar einen 7-Tage Timer. Nun haben alle Weber 7 Tage lang Zeit Einspruch einzulegen.
Geschieht dies nicht, dann geht der Antrag durch, bei Einspruch verlängert sich die Entscheidungszeit um
weitere 7 Tage bis schlussendlich abgestimmt wird. Jeder Antrag eröffnet automatisch einen Raum mitsamt
Thread und Informationen. Überhaupt entsteht mit jedem Knoten ein eigener Raum (Fenster), in dem man
Informationen, Threads, etc. nebeneinander gestalten kann. Alles, was man gestaltet, kann von allen anderen
verändert werden, es sei denn man verzwirnt es. Dies führt automatisch dazu, dass der Faden, der zu dem
Knoten führt und von der Rolle des Verzwirners ausgeht, zu einem Garn wird. Solange also eine Verzwirnung
besteht, solange kann ein Knoten sich nicht auflösen. Die Verzwirnung kann einzelne Elemente in einem
Knoten oder auch den gesamten Knoten betreffen.

Unten ist eine Zeitleiste. Man kann hier in Tagesschritten zurückspringen und vergangene Webungen sehen.
Auf der rechten Seite ist ein Slider mit den Filterkästchen für die toggelbaren Ebenen. Ecke oben rechts:
eigene Kontoeinstellung (nicht zu verwechseln mit Ortsgewebekontodarstellung oben). Man hat in seiner
eigenen Garnrolle einen privaten Bereich (Kontoeinstellungen, etc.) und einen öffentlich einsehbaren. In
dem öffentlich einsehbaren kann man unter anderem Güter und Kompetenzen, die man der Gesamtheit zur
Verfügung stellen möchte, angeben.

Über eine Suche im rechten Drawer kann man alle möglichen Aspekte suchen. Sie werden per Glow auf dem
verorteten Knoten oder Garnrolle und auf einer Liste dargestellt. Die Liste ist geordnet nach Entfernung
zur Bildmitte bei Suchbeginn. Von der Liste springt man zu dem verorteten Knoten oder Garnrolle, wenn man
den Treffer anklickt.

All diese Ebenen (links, oben, Ecke rechts oben, rechts) werden aus der jeweiligen Ecke oder Kante
herausgezogen. Die Standardansicht zeigt nur die Karte. Kleine Symbole zeigen die herausziehbaren Ebenen an.

### Fadenarten und Knotentypen

Es gibt unterschiedliche Fadenarten (in unterschiedlichen Farben):

- **Gesprächsfaden** - für Kommunikation und Diskussion
- **Gestaltungsfaden** - neue Knoten knüpfen, Räume gestalten (mit Informationen versehen, einrichten, etc.)
- **Veränderungsfaden** - wenn man bestehende Informationen verändert
- **Antragsfaden** - für offizielle Anträge im System
- **Abstimmungsfaden** - für Teilnahme an Abstimmungen
- **Goldfaden** - für Spenden und finanzielle Beiträge
- **Meldefaden** - für Meldungen problematischer Inhalte

Alle sind verzwirnbar, um aus den Fäden ein permanentes Garn zu zaubern.

Auch gibt es unterschiedliche Knotenarten:

- **Ideen** - Vorschläge und Konzepte
- **Veranstaltungen** (diversifizierbar) - Events und Termine
- **Einrichtungen** (diversifizierbar) - physische Orte und Gebäude
- **Werkzeuge** - Hilfsmittel und Geräte
- **Schlaf-/Stellplätze** - Übernachtungs- und Parkmöglichkeiten
- etc.

Diese Knotenarten sind auf der Karte filterbar (toggelbar).

## Organisation und Struktur

Weltweberei ist das Konzept. Realisiert wird es durch Ortswebereien, welche sich um ein gemeinsames
Gewebekonto versammeln. Jede Ortsweberei hat eine eigene Unterseite auf weltgewebe.net.

### Accounts und Nutzerkonten

Die Verifizierung übernimmt ein Verantwortlicher der Ortsweberei (per Identitätsprüfung etc.). Damit wird
dem Weber ein Account erstellt, den er beliebig gestalten kann. Es gibt einen öffentlich einsehbaren und
einen privaten Bereich. Der Account wird als Garnrolle auf seiner Wohnstätte visualisiert.

**Wichtige Unterscheidung:**

- Rolle ≠ Funktion im Gewebe
- Rolle = Kurzform für Garnrolle = auf Wohnsitz verorteter Account

Das System der Weltweberei kommt ohne Währungsalternativen oder Creditsysteme aus. Sichtbares Engagement und
eingebrachte bzw. einzubringende Ressourcen (also geleistete und potenzielle Webungen) sind die Währung!

### Ortsgewebekonto

Dies ist das Gemeinschaftskonto der jeweiligen Ortswebereien.

Per Visualisierung im Weltgewebe jederzeit einsehbar.

Hier gehen Spenden ein und werden Anträge auf Auszahlung gestellt, die – wie alles im Weltgewebe – dem
Gemeinschaftswillen zur Disposition stehen.

### Partizipartei

Der politische Arm der jeweiligen Ortswebereien. Der Clou: Alles politische geschieht unter
Live-Beobachtung und -Mitwirkung der Weber und anderer Interessierter (diese jedoch ohne
Mitwirkungsmöglichkeit).

Die Arbeit der Fadenträger (Mandatsträger) und dessen Fadenreicher (Sekretäre, die den Input aus dem
Gewebe aufbereiten und an den Fadenträger weiterreichen) wird während der gesamten Arbeitszeit gestreamt.
Weber können live im Stream-Gruppenchat ihre Ideen (gefiltert durch Aufwertung/Abwertung der Mitweber und
möglicherweise unterstützt / geordnet durch eine Plattform-Künstliche Intelligenz) und Unterstützungen
einbringen. Jeder Funktion, jeder Posten kann – wie alles in dem Weltgewebe – per Antrag umbesetzt oder
verändert werden. Jeder Weber (auch die kleinen) haben eine Stimme. Diese können sie temporär an andere
Weber übertragen. Das bedeutet, dass diejenigen, an die die Stimmen übertragen wurden, bei Abstimmungen
dementsprechend mehr Stimmmacht haben.

Auch übertragene Stimmen können weiterübertragen werden. Übertragungen enden 4 Wochen nach Inaktivität des
Stimmenverleihenden oder durch dessen Entscheidung.

## Kontakt / Impressum / Datenschutz

**E-Mail-Adresse:** <kontakt@weltweberei.org>
Schreib gerne, wenn du interessiert bist, Fragen, Anregungen oder Kritik hast. Oder willst du gar selber
eine Ortsweberei gründen oder dich anderweitig beteiligen?

**Telefon:** +4915563658682
Aktuell benutze ich WhatsApp und Signal

**Verantwortlicher:** Alexander Mohr, Huskoppelallee 13, 23795 Klein Rönnau

**Datenschutz:** Das Weltgewebe ist so konzipiert, dass keine Daten erhoben werden, ohne dass du sie selbst
einträgst. Es gibt kein Tracking, keine versteckten Cookies, keine automatische Profilbildung. Sichtbar
wird nur das, was du freiwillig sichtbar machst: Name, Wohnort, Verbindungen im Gewebe. Deine persönlichen
Daten kannst du jederzeit verändern oder zurückziehen. Die Verarbeitung deiner Daten erfolgt auf Grundlage
von Artikel 6 Absatz 1 lit. a und f der Datenschutzgrundverordnung – also: Einverständnis & legitimes
Interesse an sicherer Gemeinschaftsorganisation.

## Technische Umsetzung

Ich arbeite an einem iPad und an einem Desktop PC.

Die technische Umsetzung soll maximale Kontrolle, Skalierbarkeit und Freiheit berücksichtigen. Es soll
stets die perspektivisch maximalst sinnvolle Lösung umgesetzt werden.
```

### 📄 weltgewebe/docs/quickstart-gate-c.md

**Größe:** 546 B | **md5:** `9ebd955eee6d22093d170300d2822f2a`

```markdown
# Quickstart · Gate C (Dev-Stack)

```bash
cp .env.example .env
make up
# Web:  http://localhost:5173
# Proxy: http://localhost:8081
# API:  http://localhost:8081/api/version  (-> /version via Caddy)
make logs
make down
```

## Hinweise

- Frontend nutzt `PUBLIC_API_BASE=/api` (siehe `apps/web/.env.development`).
- Compose-Profil `dev` schützt vor Verwechslungen mit späteren prod-Stacks.
- `make smoke` triggert den GitHub-Workflow `compose-smoke` für einen E2E-Boot-Test.
- CSP ist im Dev gelockert; für externe Tiles Domains ergänzen.
```

### 📄 weltgewebe/docs/runbook.md

**Größe:** 6 KB | **md5:** `e10a31b002903c4664d2e9ab5ac69bfa`

```markdown
# Runbook

Dieses Dokument enthält praxisorientierte Anleitungen für den Betrieb, die Wartung und das Onboarding
im Weltgewebe-Projekt.

## 1. Onboarding (Woche 1-2)

Ziel dieses Runbooks ist es, neuen Teammitgliedern einen strukturierten und schnellen Einstieg zu ermöglichen.

### Woche 1: Systemüberblick & lokales Setup

- **Tag 1: Willkommen & Einführung**
  - **Kennenlernen:** Team und Ansprechpartner.
  - **Projekt-Kontext:** Lektüre von `README.md`, `docs/overview/inhalt.md` und `docs/geist und plan.md`.
  - **Architektur:** `docs/architekturstruktur.md` und `docs/techstack.md` durcharbeiten, um die
    Komponenten und ihre Zusammenspiel zu verstehen.
  - **Zugänge:** Accounts für GitHub, Docker Hub, etc. beantragen.

- **Tag 2-3: Lokales Setup**
  - **Voraussetzungen:** Git, Docker, Docker Compose, `just` und Rust (stable) installieren.
  - **Codespaces (Zero-Install):** GitHub Codespaces öffnen, das Devcontainer-Setup starten und im
    Terminal `npm run dev -- --host` ausführen. So lassen sich Frontend und API ohne lokale
    Installation testen – ideal auch auf iPad.
  - **Repository klonen:** `git clone <repo-url>`
  - **`.env`-Datei erstellen:** `cp .env.example .env`.
  - **Core-Stack starten:** `just up` (bevorzugt) oder `make up` als Fallback. Überprüfen, ob alle
    Container (`web`, `api`, `db`, `caddy`) laufen: `docker ps`.
  - **Web-Frontend aufrufen:** `http://localhost:5173` (SvelteKit-Devserver) oder – falls der Caddy
    Reverse-Proxy aktiv ist – `http://localhost:3000` im Browser öffnen.
  - **API-Healthcheck:** API-Endpunkt `/health` aufrufen, um eine positive Antwort zu sehen.

- **Tag 4-5: Erster kleiner Beitrag**
  - **Hygiene-Checks:** `just check` ausführen und sicherstellen, dass alle Linter, Formatierer und
    Tests erfolgreich durchlaufen.
  - **"Good first issue" suchen:** Ein kleines, abgeschlossenes Ticket (z.B. eine Textänderung in der
    UI oder eine Doku-Ergänzung) auswählen.
  - **Workflow üben:** Branch erstellen, Änderung implementieren, Commit mit passendem Präfix (`docs:
    ...` oder `feat(web): ...`) erstellen und einen Pull Request zur Review stellen.

### Woche 2: Vertiefung & erste produktive Aufgaben

- **Monitoring & Observability:**
  - **Monitoring-Stack starten:** `docker compose -f infra/compose/compose.observ.yml up -d`.
  - **Dashboards erkunden:** Grafana (`http://localhost:3001`) öffnen und die Dashboards für
    Web-Vitals, API-Latenzen und Systemmetriken ansehen.
- **Datenbank & Events:**
  - **Event-Streaming-Stack starten:** `docker compose -f infra/compose/compose.stream.yml up -d`.
  - **Datenbank-Migrationen:** Verzeichnis `apps/api/migrations/` ansehen, um die
    Schema-Entwicklung nachzuvollziehen.
- **Produktiv werden:**
  - **Erstes Feature-Ticket:** Eine überschaubare User-Story oder einen Bug bearbeiten, der alle
    Schichten (Web, API) betrifft.
  - **Pair-Programming:** Eine Session mit einem erfahrenen Teammitglied planen, um komplexere Teile
    der Codebase kennenzulernen.

---

## 2. Disaster Recovery Drill

Dieses Runbook beschreibt die Schritte zur Simulation eines Totalausfalls und der Wiederherstellung
des Systems. Der Drill sollte quartalsweise durchgeführt werden, um die Betriebsbereitschaft
sicherzustellen.

**Szenario:** Das primäre Rechenzentrum ist vollständig ausgefallen. Das System muss aus Backups in
einer sauberen Umgebung wiederhergestellt werden.

**Ziele (RTO/RPO):**

- **Recovery Time Objective (RTO):** < 4 Stunden
- **Recovery Point Objective (RPO):** < 5 Minuten

### Vorbereitung

1. **Backup-Verfügbarkeit prüfen:** Sicherstellen, dass die letzten WAL-Archive der
   PostgreSQL-Datenbank an einem sicheren, externen Ort (z.B. S3-Bucket) verfügbar sind –
   verschlüsselt (z.B. S3 SSE-KMS) und mittels Object Lock unveränderbar abgelegt.
2. **Infrastruktur-Code:** Sicherstellen, dass der `infra/`-Ordner den aktuellen Stand der
   produktiven Infrastruktur abbildet.
3. **Team informieren:** Alle Beteiligten über den Beginn des Drills in Kenntnis setzen.

### Durchführung

1. **Saubere Umgebung bereitstellen:** Eine neue VM- oder Kubernetes-Umgebung ohne bestehende Daten
   oder Konfigurationen hochfahren.
2. **Infrastruktur aufbauen:**
    - Das Repository auf die neue Umgebung klonen.
    - Die Basis-Infrastruktur über die Compose-Files oder Nomad-Jobs starten
      (`infra/compose/compose.core.yml` etc.). Die Container starten, bleiben aber ggf. im
      Wartezustand, da die Datenbank noch nicht bereit ist.
3. **Datenbank-Wiederherstellung (Point-in-Time Recovery):**
    - Eine neue PostgreSQL-Instanz starten.
    - Das letzte Basis-Backup einspielen.
    - Die WAL-Archive aus dem Backup-Speicher bis zum letzten verfügbaren Zeitpunkt vor
      dem "Ausfall" wiederherstellen.
4. **Systemstart & Event-Replay:**
    - Die Applikations-Container (API, Worker) neu starten, damit sie sich mit der
      wiederhergestellten Datenbank verbinden.
    - Den `outbox`-Relay-Prozess starten. Dieser beginnt, die noch nicht verarbeiteten
      Events aus der `outbox`-Tabelle an NATS JetStream zu senden.
    - Die Worker (Projektoren) starten. Sie konsumieren die Events von JetStream
      und bauen die Lese-Modelle (`faden_view` etc.) neu auf.
5. **Verifikation & Abschluss:**
    - **Datenkonsistenz prüfen:** Stichprobenartige Überprüfung der wiederhergestellten Daten in den
      Lese-Modellen.
    - **Funktionstests:** Manuelle oder automatisierte Smoke-Tests durchführen (z.B. Login, Thread
      erstellen).
    - **Zeitmessung:** Die benötigte Zeit für die Wiederherstellung stoppen und mit dem RTO
      vergleichen.
    - **Datenverlust bewerten:** Den Zeitpunkt des letzten wiederhergestellten
      WAL-Segments mit dem Zeitpunkt des "Ausfalls" vergleichen, um den
      Datenverlust zu ermitteln (sollte RPO nicht überschreiten).
6. **Drill beenden:** Die Testumgebung herunterfahren und die Ergebnisse dokumentieren.

| Startzeit | Endzeit | RTO erreicht? | RPO erreicht? |
|-----------|---------|---------------|---------------|
|           |         | [ ] Ja / [ ] Nein | [ ] Ja / [ ] Nein |

### Nachbereitung

- **Lessons Learned:** Ein kurzes Meeting abhalten, um Probleme oder Verbesserungspotenziale zu besprechen.
- **Runbook aktualisieren:** Dieses Runbook bei Bedarf mit den gewonnenen Erkenntnissen anpassen.
- **Automatisierung nutzen:** `just drill` ausführen, um den Drill reproduzierbar zu starten und
  Smoke-Tests anzustoßen.
```

### 📄 weltgewebe/docs/runbook.observability.md

**Größe:** 471 B | **md5:** `511a008946ed1870e9c0e5ab9ee2d328`

```markdown
# Observability – Local Profile

## Start

```bash
docker compose -f infra/compose/compose.observ.yml up -d
```

- Prometheus: [http://localhost:9090](http://localhost:9090)
- Grafana:    [http://localhost:3001](http://localhost:3001) (anon Viewer)
- Loki:       [http://localhost:3100](http://localhost:3100)
- Tempo:      [http://localhost:3200](http://localhost:3200)

This is purely optional and local, does not block anything – but gives you immediate graphics.
```

### 📄 weltgewebe/docs/techstack.md

**Größe:** 21 KB | **md5:** `87884c4cc1d31d120c8e39eff095fd8e`

```markdown
Weltgewebe Tech Stack

Der Weltgewebe Tech-Stack ist ein vollständig dokumentiertes Systemprofil. Er nutzt eine moderne Web-Architektur mit
SvelteKit im Frontend, PostgreSQL als Source of Truth, NATS JetStream für Event-Distribution, und umfangreiche
Überwachung sowie Sicherheits- und Kostenkonzepte. Die folgenden Abschnitte fassen alle Komponenten zusammen –
verständlich für Entwickler, Auditoren und PMs, mit konkreten Vorgaben und Kennzahlen.

Frontend (SvelteKit + Qwik-Escape)
  •  SvelteKit-Only: Das Frontend basiert ausschließlich auf SvelteKit, um mit minimalem Overhead und maximaler
     Performance native Web-App-Features zu nutzen. Zusätzliche Frameworks werden vermieden.
  •  Qwik-Escape (A/B- oder Fast-Track): Eine optionale Qwik-Integration („Fast-Track“) erlaubt reines Client-Rendering
     dort, wo ein messbarer ROI vorliegt (z.B. extrem hohe Traffic-Routen). A/B-Tests evaluieren den Nutzen. Erst bei
     signifikantem Performance-Gewinn wird die Qwik-Escape-Variante aktiviert.
  •  UX-Performance: Wir messen Frontend-Performance, insbesondere Long Tasks (>50ms im Browser), da sie über 50 % der
     Responsiveness-Probleme verursachen. Entsprechende Metriken (z.B. Anzahl Long-Running Tasks pro Seite) fließen in
     die Überwachung ein, um Code und Third-Party-Assets zu optimieren.

Backend & Datenhaltung
  •  PostgreSQL + Outbox: Alle Änderungen werden in PostgreSQL als „Source of Truth“ gespeichert. Zur zuverlässigen
     Event-Publikation nutzen wir das Transactional Outbox Pattern: Datenänderungen und zu sendende Events werden in
     derselben DB-Transaktion zusammengefasst. Ein separater Outbox-Relay-Prozess liest aus der Outbox-Tabelle und
     sendet die Events an NATS. So bleibt Daten- und Event-Zustand konsistent.
  •  NATS JetStream: Für verteilte Events (Event-Bus) setzen wir NATS JetStream ein. JetStream bietet verteilte,
     persitente Streams und skalierbare Consumer-Gruppen. Mit dem prometheus-nats-exporter erfassen wir JetStream-
     Metriken (z.B. Consumer-Lag) in Prometheus. Ein existierendes Grafana-Dashboard visualisiert JetStream-Stats.
     Dadurch sehen wir Rückstände (Lag) von Event-Streams und können bei Problemen reagieren.
  •  Transaktionale Sicherheit: Durch Outbox und logische Replikation wird sichergestellt, dass Events nur bei
     erfolgreichem DB-Commit versendet werden. Dies vermeidet inkonsistente Zustände (siehe Outbox-Pattern). Je nach
     Umfang kann die Outbox über Debezium/Logical Replication implementiert werden.

Monitoring & Observability
  •  Prometheus & Grafana: Infrastruktur und Anwendungen werden mit Prometheus überwacht und in Grafana visualisiert.
     Kernmetriken umfassen System- und Anwendungskennzahlen (CPU, Speicher, Antwortzeiten, Latenzen). Wir definieren
     Dashboards für alle relevanten Subsystenelemente (DB, Services, NATS, Edge).
  •  Long-Task-Attribution: Der Browser gibt uns Informationen zu Long-Running Tasks (Hauptthread-Blocker). Wir sammeln
     diese durch Real-User Monitoring (z.B. über PerformanceObserver oder Synthetics). Wie Studien zeigen, sind lange
     Tasks (>50 ms) Hauptursache für wahrgenommenen Lag. Die Metriken fließen in Dashboards und Alerts ein (z.B. „>10
     Long-Tasks auf Landing-Page“).
  •  JetStream-Lag: Über den NATS-Exporter werden JetStream-spezifische Werte (z.B. consumer lag, stream depth) erfasst
     . In Grafana sehen wir, ob Event-Queues anwachsen. Alerts warnen, wenn ein Consumer hinterherhinkt.
  •  Edge-Kosten: Wir messen Netzwerkmetriken und CDN-Kosten. Key-Metriken sind ausgehende Traffic-Volumina und Kosten
     pro Gigabyte. Monitoring umfasst außerdem HTTP/3-spezifische Stats (Caddy kann diese liefern). So sehen wir, wo
     hohe Egress-Kosten entstehen und optimieren ggf. Caching oder Traffic-Shaping.
  •  Alert-Trigger: Alerts basieren auf SLIs (siehe SLO-Matrix weiter unten). Beispiele: „CPU >90 % länger als 5 min“,
     „Service-Response 95%-Latency >X ms“ oder „>10% JetStream-Nachrichten-Lag“.

Data Lifecycle & DSGVO-Compliance
  •  Phasenorientierte DLM: Unsere Daten durchlaufen definierte Lebenszyklus-Phasen (Erfassung, Speicherung, Nutzung,
     Archivierung, Löschung). In der Datenspeicherung schirmen wir personenbezogene Daten mittels Encryption und
     Pseudonymisierung ab, um DSGVO-Anforderungen zu erfüllen.
  •  Daten-Pipeline: Automatisierte Pipelines klassifizieren Daten beim Import (z.B. personenbezogen oder anonym),
     verschlüsseln sie nach Bedarf und taggen sie mit Aufbewahrungsfristen. Die Pipelines sorgen für konsistente
     Metadaten, damit später entschieden wird, was wann gelöscht wird.
  •  Forget-Pipeline: Um das „Recht auf Vergessenwerden“ zu erfüllen, haben wir einen Löschworkflow implementiert. Nach
     Ablauf eines Retentionszeitraums oder auf Nutzernachfrage entfernt die Pipeline alle verbliebenen persönlichen
     Daten (End-of-Lifecycle). Dabei kann eine Kombination aus Soft-Delete, Datenmaskierung und finaler physischer
     Löschung zum Einsatz kommen. Jede Löschung wird auditfähig protokolliert.
  •  Audit & Protokollierung: Zugriffe und Änderungen an sensiblen Daten werden lückenlos geloggt. Retentions- und
     Lösch-Fälle sind dokumentiert, um DSGVO-Audits zu bestehen.

Disaster Recovery
  •  Regelmäßige Drills: Mindestens vierteljährlich führen wir einen DR-Drill durch. Dabei simulieren wir einen
     Totalausfall des primären Rechenzentrums. In jedem Drill wird unsere Infrastruktur nach definiertem RPO/RTO-Konzept
     in einer sauberen Umgebung neu aufgebaut.
  •  Rebuild + Replay: Der Drill umfasst: (1) Neuaufbau aller Cluster (Nomad, DBs, NATS, etc.) mit Infrastruktur-as-
     Code, (2) Event-Replay: Verarbeitung gespeicherter Events aus der Outbox/Historie, um den Datenstand zu
     rekonstruieren, (3) Verifikation: Konsistenz-Checks zwischen Quellsystem und Wiederherstellung. Alle Schritte
     werden dokumentiert und gemessen (Recovery-Time, Datenverlust).
  •  Continuous Testing: Diese Übung ist Teil eines kontinuierlichen Verbesserungsprozesses. Erkenntnisse fließen in die
     Systemhärtung ein (z.B. Code-Updates, Automatisierung). TestRail empfiehlt, DR-Prozesse regelmäßig zu validieren,
     damit das Team eingespielt bleibt.

Service Level Objectives (SLO) & Alerts
  •  Routen-granulare SLOs: Für jeden Haupt-Service bzw. Endpunkt definieren wir eigene SLOs (z.B. 99,9 % Verfügbarkeit
     pro Monat, p95-Latenz ≤ X ms). Kritische Pfade (z.B. Buchung, Checkout) haben höhere Ziele als weniger relevante
     Routen. So kann z.B. die API-Route /api/checkout ein eigenes SLO „99,95 % bez. Erfolgsrate“ erhalten.
  •  Fehlerbudget-Alarmierung: Zu jedem SLO wird ein Fehlerbudget und automatische Trigger konfiguriert. Wir überwachen
     z.B. „gültige vs. fehlerhafte API-Antworten pro Route“ oder „Erfolgsrate von Calls pro Endpoint“. Sinkt die SLI
     unter das Ziel, wird sofort ein Alert ausgelöst. Tools wie Datadog erlauben es, gruppierte SLOs zu erstellen – zum
     Beispiel nach Route oder Traffic-Knoten – und Fehlerraten granular einzusehen.
  •  Routing-Matrix: Eine SLO-Trigger-Matrix zeigt, welcher Alarm bei Überschreitung welcher Schwelle ausgelöst wird
     (z.B. erste Warnung bei 1 % Fehlerbudget-Auslastung, Eskalation bei 5 %). Diese Matrix wird routenweise gepflegt
     und bildet die Grundlage für Runbooks.

Suche (Typesense / MeiliSearch)
  •  Primäre Suche: Typesense: Als schnellere Suchlösung setzen wir Typesense ein. Typesense bietet ultraschnelle,
     typos-tolerante Volltextsuche und einfache Konfiguration. Damit können wir Instant-Suchergebnisse und
     Autovervollständigung gewährleisten.
  •  Fallback: MeiliSearch: Als sekundäre Engine dient MeiliSearch. Sie überzeugt durch entwicklerfreundliches Setup und
     extrem schnelle Indexierung. Fällt Typesense aus oder erreicht es Kapazitätsgrenzen, schalten wir automatisch auf
     MeiliSearch um. Beide Systeme werden laufend via Monitoring auf ihre Ressourcen- und Durchsatz-Zahlen geprüft.
  •  DX-Metriken: Für Entwickler-Effizienz („Developer Experience“) tracken wir Kennzahlen wie Time-to-Market von
     Suchfeatures, Code-Review-Durchlaufzeiten und Einrichtungsaufwand. Diese Metriken sorgen dafür, dass wir die
     Wartbarkeit und Erweiterbarkeit unserer Suche kontinuierlich verbessern können.

Kostenmanagement & KPIs
  •  Lastszenarien (S1–S4): Zur Kostenprojektion definieren wir vier Traffic-Szenarien:
  •  S1 Normalbetrieb: Standard-Traffic (Basisjahr).
  •  S2 Wachstum: +50 % Nutzer, saisonale Peak-Zeiten.
  •  S3 Spitzenlast: z.B. „Black Friday“-ähnlicher Ansturm (2–3× Basis).
  •  S4 Extremfall: Ungeschätzter Extrem-Traffic (Worst-Case).
In einer Kosten-Tabelle modellieren wir für jedes Szenario Sessions/Monat und Bandbreitenbedarf und berechnen die
ungefähren Cloud-Kosten (z.B. Instanz-Stunden, Daten-Egress, Speichervolumen). Darin führen wir auch geschätzte KPIs wie
€ pro Session oder € pro GB auf. Solche Einheitenwerte erlauben es, Kostenentwicklungen zu interpretieren:
„Kosten/Nutzer“ ist ein aussagekräftiger FinOps-KPI.
  •  KPI-Metriken: Basis-KPIs sind u.a. „€ pro Session“, „€ pro App-Request“, „€ pro GB Traffic“. Studien empfehlen,
     Cloud-Kosten in Relation zum Traffic zu setzen (z.B. Cost per Session). Wir definieren Schwellenwerte (z.B. Ziel:
     < €1/Session) und überwachen Abweichungen. Die KPI-Berichte werden monatlich aktualisiert.
  •  Kostenkontrolle: Neben Budget-Alerts nutzen wir Cloud Cost Monitore (z.B. über Grafana/Cloud-Anbieter) zur
     Echtzeit-Überwachung. So erkennen wir Abweichungen sofort und prüfen, ob sie durch geändertes Nutzungsverhalten
     gerechtfertigt sind.

Infrastruktur & Hochverfügbarkeit
  •  Nomad-Cluster: Für Deployment und Orchestrierung nutzen wir HashiCorp Nomad. Nomad ermöglicht Multi-Region-Cluster
     für Hochverfügbarkeit und Rolling-Updates. Alle Services (Container, Java-Services, Batch-Jobs) laufen über Nomad-
     Jobs. Nomad ist leichtgewichtig und ersetzt schwerfällige K8s-Setups.
  •  PgBouncer: Zwischen App-Servern und PostgreSQL setzen wir einen PgBouncer-Connection-Pool ein, um
     Datenbankverbindungen effizient zu verwalten. So skalieren wir die Zahl gleichzeitiger Clients, ohne Postgres
     übermäßig zu belasten.
  •  Caddy HTTP/3: Als Frontend-Proxy verwenden wir Caddy Server. Mit Caddy 2.6+ ist HTTP/3 (QUIC) standardmäßig
     verfügbar, was Latenzen an mobilen Clients verringert. Caddy übernimmt TLS, Load-Balancing und kann durch Plugins
     leicht erweitert werden.
  •  HA-Pfade: Die Infrastruktur ist redundant ausgelegt: Multi-AZ-Datenbanken, mehrfach vorhandene Nomad-Server,
     mehrere Netzwerk-Provider. Jede kritische Komponente hat mindestens einen Ausfalls-Backup (Active/Active-
     Konfiguration). Netzwerkpfade sind redundant (z.B. Multi-Region-Backbone, DNS-Round-Robin).
  •  Load Shedding: Um Überlastung zu vermeiden, implementieren wir Load Shedding: Bei Erreichen kritischer
     Auslastungsgrenzen (CPU, Queue-Längen) lehnen Services aktiv neue Anfragen ab (HTTP 503) und schützen so bereits
     laufende Anfragen vor Timeout. Auf diese Weise bleibt die Verfügbarkeit der angenommenen Anfragen hoch, selbst
     wenn eingehender Traffic kurzfristig stark ansteigt. Amazon empfiehlt diesen Ansatz, um Latency-Probleme in
     Availability-Probleme zu wandeln: Beim Hochlastpunkt soll nur der Überhang ausgestoßen werden, nicht alle Anfragen
     .

Sicherheit und Compliance
  •  SBOM (Software Bill of Materials):
    •  Jede neue Anwendungsversion erzeugt automatisch ein SBOM (z.B. via Syft/Trivy).
    •  Das SBOM beschreibt alle Abhängigkeiten.
    •  Es wird zusammen mit dem Build-Artefakt archiviert und als Attestation hinterlegt.
    •  Bei Deployments prüfen wir das SBOM auf bekannte Schwachstellen.
  •  Artifact Signing & Attestations:
    Container-Images und Pakete werden signiert (z.B. mit Sigstore Cosign).
    Neben dem SBOM legen wir erweiterte Attestations (z.B. SLSA-Provenance) als Metadaten ab.
    So ist Herkunft und Integrität jedes Artefakts überprüfbar.
  •  CI/CD-Gates:
    Unsere Pipelines erzwingen strikte Checks: Builds mit kritischen CVEs oder fehlender Signatur werden verworfen.
    Policy-Gates (Kyverno/OPA) verhindern bei Deployment nicht-konforme Artefakte.
    Nur signierte Images aus genehmigten Repositories dürfen in den Cluster gelangen.
    „Latest“-Tags sind verboten, stattdessen verwenden wir digest-gezählte Artefakte.
  •  Key Rotation:
    Alle kryptografischen Schlüssel (z.B. Datenbank-Passwörter, TLS-Private Keys, JWT-Keys)
    werden automatisiert rotiert.
    Wir folgen bewährten Policies (z.B. Rotation mindestens alle 90 Tage),
    um das Risiko kompromittierter Keys zu begrenzen.
    Auch für API-Schlüssel und OAuth-Tokens gelten strenge Lebensdauern.
    Key-Rotation ist Teil unseres Compliance-Plans (PCI-DSS, ISO 27001 empfehlen dies ausdrücklich).
  •  Strikte Zugriffsverwaltung:
    CI/CD-Zugriffe, Secrets und Konfigurations-Änderungen erfordern Multi-Faktor-Authentifizierung und Genehmigungen.
    Wir setzen auf Infrastructure-as-Code Reviews und manuelle Freigaben für kritische Änderungen.
  •  Regelmäßige Security-Audits:
    Quartalsweise führen wir Security- und Compliance-Audits durch (z.B. SAST-Scans, Pentests der Infrastruktur,
    Review von Konfigurationen). Erkannten Risiken begegnen wir unmittelbar mit Patches oder Architektur-Änderungen.

Observability & Runbooks
  •  Umfassendes Monitoring:
    Logs, Metriken und Traces sind ab Deployment Day 1 aktiv.
    Aggregierte Logs (z.B. über Loki/Elasticsearch) erlauben schnelle Fehlersuche.
    Wir benutzen „OpenTelemetry“-Standards, wo sinnvoll, um Metriken und Traces einheitlich zu erfassen.
    So haben Entwickler und SREs über Dashboards stets Einblick in Systemzustand und Nutzerinteraktionen.
  •  Runbooks:
    Für alle kritischen Prozesse und Incident-Typen existieren Runbooks – strukturierte
    Schritt-für-Schritt-Anleitungen für Wiederherstellung und Fehlerbehebung.
    Das beginnt bei Onboarding-Checklisten für neue Teammitglieder
    (Woche 1–2: Systemüberblick, Account-Setup, Dev-Umgebung)
    und geht bis zu Incident-Runbooks (z.B. „Netzwerkausfall“, „Datenbank-Recovery“).
    Runbooks minimieren Fehler im Stresstest und sorgen für reproduzierbare Abläufe.
  •  Onboarding (Woche 1–2):
    In den ersten zwei Wochen erhält jeder neue Entwickler klare Dokumentation zu Infrastruktur, Tools, Zugangsdaten und
    Erst-Checks (Smoke-Tests).
    Themen sind u.a. Code-Repo, CI/CD-Pipeline, Monitoring-Zugriff, evtl. Testumgebung-Einrichtung.
    Diese „Woche-1“-Dokumente sind versioniert und werden regelmäßig aktualisiert.
  •  Quartalsweise Audits:
    Neben Security-Audits gibt es quartalsweise auch Architektur- und Compliance-Reviews.
    Dabei prüfen wir z.B. Datenflüsse auf DSGVO-Konformität, Updates von Abhängigkeiten auf CVEs,
    oder Business-Continuity-Übungen.
    Ergebnisse werden in Handlungsplänen festgehalten und umgesetzt.

Quellen: Technische Muster und Best Practices stammen u.a. aus aktuellen DevOps- und SRE-Leitfäden.
Die Zitate verweisen auf etablierte Konzepte (Outbox-Pattern, Disaster-DR-Tests, FinOps-KPIs, CI/CD-Security).

⸻

🌐 Weltgewebe Techstack – Übersicht

Frontend
  •  SvelteKit + TypeScript → Standard, einheitliche Toolchain
  •  Qwik-Escape → nur route-granular via A/B/Fast-Track bei messbarem ROI (≥ 10 % LCP, ≥ 20 % TTI, ≤ +25 % Opex)
  •  MapLibre GL + PMTiles → Karten, Prebakes, Tileset-Versionierung
  •  PWA → Offline-Shell, feingranulare Caches
  •  Security → CSP/COOP/COEP, Islands-Pattern

Backend & Realtime
  •  Rust (Axum + Tokio), sqlx, OpenAPI (utoipa)
  •  SSE → Standard für Live-Feeds
  •  WebSocket → nur für echte Bidir-Flows (Chat/Kollab), Idle >30 s schließen
  •  Guards → SSE keep-alive, WS Token-Bucket (10/s, Burst 20)

Persistenz & Events
  •  PostgreSQL 16 + PostGIS + h3-pg = Source of Truth
  •  Transactional Outbox → garantiert konsistente Events
  •  NATS JetStream = aktiver Distributor
  •  Policies: max_age=30d, max_bytes=100GiB, dupe_window=72h
  •  Alarme: RAM >350 MB/Stream, Topics >50, Consumers >200, per-Consumer lag

Suche & Cache
  •  Typesense (Default)
  •  MeiliSearch (Fallback bei DX-Friktion)
  •  KeyDB → Caches, Rate-Limits, Locks
  •  DX-KPIs → Index-Zeit ≤2 h, Tuning ≤4 h, No-Hits-Rate, RAM

Delivery & Edge
  •  Caddy (HTTP/3) → Proxy, TLS, Brotli/Zstd, immutable Assets
  •  Caching → SSR-HTML s-maxage=600, Tiles immutable
  •  Edge-Budget:
  •  30d Opex-Δ ≤ 10 %
  •  Boost ≤ 25–30 % nur bei globalem LCP-ROI (≥ 300 ms in ≥ 3 Regionen)
  •  Auto-Rollback bei > 15 % Mehrkosten ohne ≥ 150 ms Gewinn

Observability & Monitoring
  •  Prometheus + Grafana + Loki + Tempo
  •  RUM Long-Task Attribution → PerformanceObserver, Budget ≤ 200 ms p75/Route
  •  JetStream Monitoring → per-Consumer lag, redeliveries, ack_wait_exceeded
  •  Dashboards → Web-Vitals, API-Latenzen, Search-DX, Edge-Kosten, GIS-Interaktionen

Infrastruktur & HA
  •  Nomad → Orchestrierung (primär)
  •  PgBouncer → Connection-Pooling (transaction mode)
  •  WAL-Archiv + Repl-Slots → DR-Pfad
  •  Caddy HTTP/3 → Entry Proxy
  •  HA-Pfade → Compose → Nomad → Swarm-Mini (Drill) → K8s (nur bei massivem Scale)
  •  Load Shedding → HTTP 503 bei Überlast statt Timeout

Security & Compliance
  •  SBOM (Syft/Trivy) + cosign Attestations
  •  Key Rotation → ed25519 halbjährlich, Overlap 14 Tage
  •  CI-Gates → clippy -D, audit/deny, Semgrep, Trivy, CodeQL
  •  Access Control → MFA, Secrets via sops/age
  •  Data Lifecycle (DSGVO) → PII-Klassen, Retention, Forget-Pipeline (Replay+Rebuild), Audit-Logs

Reliability & Governance
  •  Error-Budgets → 99,0–99,5 %/Monat; Release-Freeze bei Riss
  •  Disaster-Recovery Drill → vierteljährlich: Replica-Promote + JetStream-Replay + Outbox-Rebuild + Verify
  •  Runbooks → Woche 1–2 Onboarding + Incident Playbooks; Quartals-Audits

Kosten & KPIs
  •  Traffic-Szenarien S1–S4: 100 → 100k MAU
  •  Kostenbänder: Hetzner (15–900 €), DO-Hybrid (70–2400 €)
  •  KPIs: €/1 000 Sessions, €/GB egress, €/Mio Events, Edge-Quote %

⸻

👉 Kurz: mobil-first, audit-ready, rewrite-frei skalierbar.
Frontend simpel (SvelteKit-only), Events konsistent (PG Outbox + JetStream), Kosten & Latenz
metrisch kontrolliert, DSGVO & Security vollständig eingebaut, Disaster-Recovery geprobt.

⸻

WELTGEWEBE TECHSTACK
─────────────────────────

Frontend
├─ SvelteKit + TypeScript (Standard)
│   ├─ MapLibre GL + PMTiles (Karten, Prebakes)
│   ├─ PWA (Offline-Shell, Caches)
│   └─ CSP/COOP/COEP, Islands-Pattern
└─ Qwik-Escape (nur bei ROI via A/B/Fast-Track)

Backend & Realtime
├─ Rust (Axum + Tokio), sqlx, utoipa/OpenAPI
├─ SSE (Default für Live-Feeds)
└─ WebSocket (nur Chat/Kollab, Idle >30s Close)
   └─ Guards: SSE keep-alive, WS Token-Bucket (10/s, Burst 20)

Persistenz & Events
├─ PostgreSQL 16 + PostGIS + h3-pg (Source of Truth)
├─ Transactional Outbox (Event-Konsistenz)
└─ NATS JetStream (aktiver Distributor)
   ├─ Policies: max_age=30d, max_bytes=100GiB, dupe_window=72h
   └─ Alarme: RAM >350MB/Stream, Topics >50, Consumers >200, Lag pro Consumer

Suche & Cache
├─ Typesense (Default)
├─ MeiliSearch (Fallback bei DX-Reibung)
└─ KeyDB (Cache, Rate-Limits, Locks)

Delivery & Edge
├─ Caddy (HTTP/3, Brotli/Zstd, immutable Assets)
├─ Caching: SSR-HTML s-maxage=600, Tiles immutable
└─ Edge-Budget:
   ├─ 30d Opex-Δ ≤ 10 %
   ├─ Boost ≤ 25–30 % bei globalem LCP-ROI
   └─ Auto-Rollback bei >15 % Mehrkosten ohne ≥150ms Gewinn

Observability & Monitoring
├─ Prometheus + Grafana + Loki + Tempo
├─ RUM Long-Task Attribution (Budget ≤200ms p75/Route)
├─ JetStream Monitoring (Lag, redeliveries, ack_wait_exceeded)
└─ Dashboards: Web-Vitals, API-Latenzen, Search-DX, Edge-Kosten, GIS

Infrastruktur & HA
├─ Nomad (Orchestrierung primär)
├─ PgBouncer (Connection-Pool, transaction mode)
├─ WAL-Archiv + Repl-Slots (DR-Pfad)
├─ Caddy HTTP/3 (Proxy)
├─ HA-Pfade: Compose → Nomad → Swarm-Mini (Drill) → K8s (bei Mass-Scale)
└─ Load Shedding: HTTP 503 bei Überlast statt Timeout

Security & Compliance
├─ SBOM (Syft/Trivy) + cosign Attestations
├─ Key Rotation (ed25519 halbjährlich, Overlap 14d)
├─ CI-Gates: clippy -D, audit/deny, Semgrep, Trivy, CodeQL
├─ Access Control: MFA, Secrets via sops/age
└─ Data Lifecycle (DSGVO)
   ├─ PII-Klassen, Retention, Redaction
   └─ Forget-Pipeline (Replay+Rebuild), Audit-Logs

Reliability & Governance
├─ Error-Budgets: 99.0–99.5 % / Monat → Release-Freeze bei Riss
├─ Disaster-Recovery Drill (vierteljährlich)
│   └─ Replica-Promote + JetStream-Replay + Outbox-Rebuild + Verify
└─ Runbooks
    ├─ Woche 1–2 Onboarding & Smoke-Tests
    ├─ Incident Playbooks (Netz, DB, API)
    └─ Quartals-Audits (Security & Compliance)

Kosten & KPIs
├─ Szenarien S1–S4: 100 → 100k MAU
│   ├─ Requests/Tag: 10k → 10M
│   ├─ Events/Tag:   20k → 20M
│   ├─ Tile-Hits:    50k → 15M
│   └─ Volumen:      3GB → 2TB
├─ Kostenbänder:
│   ├─ Hetzner:  €15–900
│   └─ DO-Hybrid: €70–2400
└─ KPIs: €/1000 Sessions, €/GB egress, €/Mio Events, Edge-Quote %
```

### 📄 weltgewebe/docs/zusammenstellung.md

**Größe:** 10 KB | **md5:** `b3fd5dc20ef40d3995a3a1bcd7ef67f3`

```markdown
# Zusammenstellung (MANDATORISCH)

Das Weltgewebe: Eine Systematische Zusammenfassung

Das Weltgewebe ist eine kartenbasierte soziale Infrastruktur, die als eine Art Demokratie-Engine auf einer
interaktiven Karte konzipiert ist. Jeder Beitrag eines Nutzers wird als "Faden" visualisiert. Die Plattform basiert
auf den Kernprinzipien der radikalen Transparenz, Freiwilligkeit, technischer Absicherung durch Event-Sourcing und
einem integrierten Datenschutzkonzept.

I. Grundprinzipien und Philosophie

- Alles ist ein Event: Jede Aktion im System wird als ein unveränderliches, signiertes Ereignis in einer
  Hash-Kette gespeichert (Event-Sourcing).
- Radikale Transparenz: Grundsätzlich sind alle Aktionen öffentlich sichtbar. Ausgenommen sind private Informationen
  im Nutzerkonto und private Nachrichten zwischen Nutzern.
- Freiwilligkeit: Die Teilnahme am Weltgewebe erfolgt ausschließlich nach informierter Zustimmung.
- Datenschutz (Privacy by Design): Es findet keine verdeckte Datensammlung statt, also keine Cookies, kein
  Tracking und keine automatische Profilbildung. Sichtbar ist nur, was Nutzer bewusst eintragen, wie Name, Wohnort
  und Verbindungen. Die rechtliche Grundlage für die Datenverarbeitung bilden die
  Datenschutzgrundverordnung-Artikel 6 Abs. 1 lit. a und f.
- Währungskonzept: Es gibt keine künstlichen Credits oder Alternativwährungen. Die eigentliche "Währung" ist
  sichtbares Engagement in Form von Fäden und Garn sowie die von Nutzern eingebrachten Ressourcen. Spenden können
  zusätzlich über "Goldfäden" sichtbar gemacht werden.

II. Das Domänenmodell: Nutzer, Inhalte und Struktur
Nutzer (Garnrollen)

- Nutzeraccounts (Rollen): Nutzer werden als "Garnrollen"-Icon an ihrem Wohnort auf der Karte visualisiert.
  Jede Aktion führt dazu, dass sich diese Rolle für alle sichtbar dreht.
- Verifizierung: Accounts werden von Verantwortlichen einer lokalen "Ortsweberei" durch eine Identitätsprüfung
  verifiziert und erstellt.
- Profilbereiche: Jeder Account verfügt über einen privaten Bereich für Kontoinformationen und einen öffentlichen
  Raum. Im öffentlichen Bereich können Nutzer Informationen über sich selbst sowie Güter und Kompetenzen eintragen,
  die sie der Gemeinschaft zur Verfügung stellen möchten.

Inhalte (Knoten, Fäden, Garn)

- Knoten: Dies sind ortsbezogene Bündel von Informationen, wie Ideen, Veranstaltungen, Ressourcen, Werkzeuge oder
  Schlafplätze. Jeder Knoten eröffnet einen eigenen Raum, der Threads, Informationen und Anträge enthalten kann.
  Informationen können alternativ auch direkt auf der eigenen Garnrolle verortet werden. Knoten sind auf der Karte
  filter- und einblendbar.
- Fäden: Jede Nutzeraktion erzeugt einen "Faden" von der Garnrolle des Nutzers zu einem Knoten. Es gibt verschiedene
  Faden-Typen, darunter Gesprächs-, Gestaltungs-, Änderungs-, Antrags-, Abstimmungs-, Gold-, Melde- und
  Delegationsfäden. Delegationsfäden verlaufen von einer Garnrolle zu einer anderen. Nebeneinanderliegende Fäden und
  Garne, die von einer Rolle zu einem Knoten führen, überlappen sich zunehmend, um zu dicke Linien zu vermeiden.
- Vergänglichkeit und Beständigkeit (Garn): Fäden verblassen sukzessive innerhalb von 7 Tagen, wenn sie nicht durch
  einen Klick auf den "Verzwirnungsbutton" zu "Garn" gemacht werden. Verzwirnte Fäden (Garn) sind dauerhaft und schützen
  Inhalte sowie den gesamten Knoten vor Veränderung und Auflösung.
  Strukturknoten
  Dies sind permanente und immer sichtbare Knoten für zentrale Funktionen:
- Gewebekonto: Dient der Finanzverwaltung und der Übersicht über Goldfäden.
- Webrat: Der Ort für Governance, Anträge und die Übersicht über Delegationen. Alle Abstimmungen sind hier ebenso
  einsehbar und man kann daran teilnehmen.
- Nähstübchen: Ein ortsunabhängiger Raum für die allgemeine Kommunikation.
- RoN-Platzhalter: Ein spezieller Knoten, an dem anonymisierte Inhalte nach 84 Tagen gesammelt werden.

III. Zeitlichkeit, Sichtbarkeit und Pseudonymisierung

- 7-Sekunden-Rotation: Nach jeder Aktion dreht sich die Garnrolle des Nutzers für 7 Sekunden sichtbar auf der Karte.
- 7-Tage-Verblassen: Fäden, die nicht zu Garn verzwirnt werden, verblassen innerhalb von 7 Tagen sukzessive. Knoten, zu
  denen 7 Tage lang kein neuer Faden führt, lösen sich ebenfalls in diesem Zeitraum sukzessive auf.
- Pseudonymisierung (RoN-System):
  - Nutzer können per Opt-in festlegen, dass ihre Beiträge nach x Tagen automatisch anonymisiert werden. Der
    Autorenname wird dann durch "RoN" (Rolle ohne Namen) ersetzt.
  - Die anonymisierten Fäden führen dann nicht mehr zur ursprünglichen Garnrolle, sondern zum zentralen
    RoN-Platzhalter. Das Wissen bleibt so im Gewebe erhalten.
- Ausstiegsprozess: Wenn ein Nutzer die Plattform verlässt, durchlaufen alle seine Daten den RoN-Prozess. Beiträge, die
  jünger als x Tage sind, bleiben so lange namentlich sichtbar, bis diese Frist erreicht ist. Am Ende wird die Garnrolle
  des Nutzers gelöscht.
- Eigene Beiträge und Aktionen können per Tombstone + Key-Erase uneinsehbar gemacht werden.
- per opt-in kann man die Verortung der eigenen Garnrolle ungenauer machen. Ungenauigkeitsradius individuell einstellbar

IV. Governance und Demokratische Prozesse

- 7+7-Modell für Anträge:
  - Ein gestellter Antrag wird mit einem 7-Tage-Timer sichtbar.
  - Erfolgt innerhalb dieser Frist kein Einspruch, wird der Antrag automatisch angenommen.
  - Bei einem Einspruch beginnt eine weitere 7-tägige Abstimmungsphase, in der eine einfache Mehrheit entscheidet.
    Abstimmungen sind öffentlich und namentlich einsehbar, optional mit Begründung.
- Delegation (Liquid Democracy): Nutzer können ihre Stimme 1:1 an einen anderen Nutzer übertragen. Diese Delegationen
  werden als gestrichelte Pfeile zwischen den Garnrollen visualisiert und verfallen nach 4 Wochen Inaktivität des
  Delegierenden. Für eine spätere Phase (B) ist eine transitive Delegation mit Zykluserkennung (Cycle-Detection)
  geplant. Eine direkte Stimmabgabe überschreibt dabei temporär die Delegation. Rollen, die Delegationen empfangen
  haben, zeigen deren Gewicht an.
- Moderation ("Legal Freeze"): Strafbare Inhalte können über einen "Melden"-Button gemeldet werden, was ebenfalls einen
  Faden erzeugt. Bei Verdacht auf eine Straftat erfolgt ein sofortiger Freeze mit gerichtsfester Beweissicherung. Der
  gemeldete Inhalt wird für 24 Stunden eingeklappt und im Webrat sowie am Ort des Inhalts zur Abstimmung gestellt. Eine
  einfache Mehrheit entscheidet über die weitere Vorgehensweise. Eine Entfernung erfolgt nur, wo es rechtlich geboten
  ist, und nach Abschluss des Verfahrens wird ein öffentlicher Folge-Antrag gestellt.
- Politischer Arm (Partizipartei): Jede Ortsweberei kann einen politischen Arm gründen, die "Partizipartei".
  Mandatsträger ("Fadenträger") und ihre Helfer ("Fadenreicher") arbeiten unter permanenter Live-Übertragung. Die
  Bürgerbeteiligung wird durch einen Chat mit Aufwertung/Abwertung und optionaler Künstliche Intelligenz-Unterstützung
  ermöglicht. Jede Funktion und jeder Posten kann per Antrag verändert oder abgewählt werden.

V. Benutzeroberfläche und Nutzererlebnis

- Karten-Interface: Die primäre Oberfläche ist eine Vollbildkarte (MapLibre GL).
- Drawer-System:
  - Links: Zugriff auf Webrat und Nähstübchen (Governance und Kommunikation).
  - Rechts: Filter für Knoten- und Fadenarten, ein Zeitfenster und ein Suchmenü.
- Suchfunktion: Über das Suchmenü können die von Nutzern zur Verfügung gestellten Güter und Kompetenzen abgefragt
  werden. Treffer werden als aufleuchtende Rollen oder Knoten auf der Karte sowie in einer nach Entfernung sortierten
  Liste angezeigt. Ein Klick auf einen Listeneintrag zentriert die Karte auf den entsprechenden Nutzer.
- Widgets: Oben mittig befindet sich das Gewebekonto-Widget (Saldo, Bewegungen), oben rechts der Zugang zum eigenen
  Konto und zur Verifikation.
- Zeitleiste: Eine Zeitachse am unteren Bildschirmrand ermöglicht die Rückschau auf vergangene Aktivitäten ("Webungen").

VI. Organisation und Technische Architektur

- Lokale Organisation (Ortswebereien): Das Weltgewebe wird durch lokale "Ortswebereien" konkret umgesetzt. Jede dieser
  Gruppen verfügt über ein eigenes Gemeinschaftskonto (Gewebekonto) und eine Unterseite auf weltgewebe.net. Föderationen
  von Ortswebereien sind vorgesehen.
- Technischer Stack und Verortung: Die Architektur basiert auf Event-Sourcing mit NATS JetStream, PostgreSQL/PostGIS
  und Redis. Knoten und Rollen werden H3-basiert gespeichert, um räumliche Abfragen, Filter und Indizes zu ermöglichen.
- Hosting und Betrieb:
  - Der Betrieb ist für ein kleines Team (1–2 Personen) durch Automatisierung (Cronjobs, Healthchecks) ausgelegt.
  - Das Hosting erfolgt primär bei Hetzner, um Kosteneffizienz und Datenschutzgrundverordnung-Konformität zu
    gewährleisten ("Hetzner-First").
- Performance ("Mobile-First"): Die Plattform ist für Smartphones optimiert. Angestrebt werden ein Initial-Bundle von ≤
  90 KB und eine Time-to-Interactive von unter 2,5 Sekunden auf einer 3G-Verbindung. Weitere Performance-Ziele sind P95
  API-Antwortzeiten von ≤ 300 ms und P95 Datenbankabfragen von ≤ 150 ms.
- Skalierung und Kosten: Ein Phasenmodell sichert die Skalierbarkeit von einem Single-Server (unter 200 €/Monat) bis
  hin zu Multi-Region-Clustern. Ziel ist es, die Kosten pro 1.000 Events unter 0,01 € zu halten.
- Hybrid-Indexierung: Live-Routen (z.B. /map, /feed) senden den X-Robots-Tag noindex, noarchive. Monatsarchive (z.B.
  /archive/YYYY-MM) sind hingegen als index, follow markiert und setzen ein rel="canonical"-Tag, um die
  Nachvollziehbarkeit zu gewährleisten.
- Monitoring, Alarme und Betriebspläne:
  - Metriken: Es werden Governance-Metriken (z.B. Teilnahmequote), RoN-Metriken (z.B. Transferrate) und Kosten-Metriken
    (z.B. €/aktiver Nutzer) überwacht. Es gibt Alarm-Regeln, z.B. bei Latenzen über 1000 ms oder wenn die Kosten in
    Phase A 200 € übersteigen.
  - Betriebspläne (Cronjobs): Governance-Timer laufen minütlich; Delegations-Prüfungen täglich um 01:00 Uhr;
    RoN-Prozesse um 02:00 Uhr und Kosten-Analysen um 03:00 Uhr. Für die Systemgesundheit gibt es die Endpunkte
    /health/live und /health/ready.
```

