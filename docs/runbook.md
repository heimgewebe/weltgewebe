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
