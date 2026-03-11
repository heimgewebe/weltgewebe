---
id: docs.techstack
title: Techstack
doc_type: architecture
status: active
canonicality: canonical
summary: >
  Dokumentation des verwendeten Technologie-Stacks.
---
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
     Totalausfall des primären Rechenzentrums.
     In jedem Drill wird unsere Infrastruktur nach definiertem RPO/RTO-Konzept
     in einer sauberen Umgebung neu aufgebaut.
  •  Rebuild + Replay: Der Drill umfasst: (1) Neuaufbau aller Cluster (Nomad, DBs, NATS, etc.) mit Infrastruktur-as-
     Code, (2) Event-Replay: Verarbeitung gespeicherter Events aus der Outbox/Historie, um den Datenstand zu
     rekonstruieren, (3) Verifikation: Konsistenz-Checks zwischen Quellsystem und Wiederherstellung. Alle Schritte
     werden dokumentiert und gemessen (Recovery-Time, Datenverlust).
  •  Continuous Testing: Diese Übung ist Teil eines kontinuierlichen Verbesserungsprozesses.
     Erkenntnisse fließen in die
     Systemhärtung ein (z.B. Code-Updates, Automatisierung).
     TestRail empfiehlt, DR-Prozesse regelmäßig zu validieren, damit das Team eingespielt bleibt.

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
  •  Fallback: MeiliSearch: Als sekundäre Engine dient MeiliSearch.
     Sie überzeugt durch entwicklerfreundliches Setup und extrem schnelle Indexierung.
     Fällt Typesense aus oder erreicht es Kapazitätsgrenzen, schalten wir automatisch auf
     MeiliSearch um.
     Beide Systeme werden laufend via Monitoring auf ihre Ressourcen- und Durchsatz-Zahlen geprüft.
  •  DX-Metriken: Für Entwickler-Effizienz („Developer Experience“) tracken wir Kennzahlen wie Time-to-Market von
     Suchfeatures, Code-Review-Durchlaufzeiten und Einrichtungsaufwand. Diese Metriken sorgen dafür, dass wir die
     Wartbarkeit und Erweiterbarkeit unserer Suche kontinuierlich verbessern können.

Kostenmanagement & KPIs
  •  Lastszenarien (S1–S4): Zur Kostenprojektion definieren wir vier Traffic-Szenarien:
  •  S1 Normalbetrieb: Standard-Traffic (Basisjahr).
  •  S2 Wachstum: +50 % Nutzer, saisonale Peak-Zeiten.
  •  S3 Spitzenlast: z.B. „Black Friday“-ähnlicher Ansturm (2–3× Basis).
  •  S4 Extremfall: Ungeschätzter Extrem-Traffic (Worst-Case).
  In einer Kosten-Tabelle modellieren wir für jedes Szenario Sessions/Monat und Bandbreitenbedarf
  und berechnen die ungefähren Cloud-Kosten (z.B. Instanz-Stunden, Daten-Egress, Speichervolumen).
  Darin führen wir auch geschätzte KPIs wie € pro Session oder € pro GB auf.
  Solche Einheitenwerte erlauben es, Kostenentwicklungen zu interpretieren:
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
      In den ersten zwei Wochen erhält jeder neue Entwickler klare Dokumentation zu Infrastruktur,
      Tools, Zugangsdaten und Erst-Checks (Smoke-Tests).
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
