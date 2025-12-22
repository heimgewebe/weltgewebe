## Domain-Contracts lokal validieren

Weltgewebe nutzt JSON-Schemas, um die zentralen Domänenobjekte (`node`, `edge`, `conversation`, `message`)
konsistent zu halten. Zu jedem Schema existiert mindestens ein Beispiel unter `contracts/domain/examples/`.
CI prüft bei jedem Push sowohl die Schema-Syntax als auch die Beispieldateien – dieselbe Prüfung lässt sich
lokal ausführen.

### Voraussetzungen

- Node.js ≥ 20 (Vite & SvelteKit erfordern dies ohnehin)
- `ajv-cli` und `ajv-formats` global installiert:

  ```sh
  pnpm install -g ajv-cli ajv-formats
  ```

- Shell-Zugriff auf das Repo

### Ausführung

Die komplette Prüfung läuft über das interne Script:

```sh
just contracts-domain-check
```

oder ohne Just:

```sh
bash ./scripts/contracts-domain-check.sh
```

Das Script führt zwei Schritte aus:

1. **Schemas kompilieren**
   Alle Dateien unter `contracts/domain/*.schema.json` werden mit `ajv compile` gegen `ajv-formats` geprüft.

2. **Beispiele validieren**
   Jede Datei unter `contracts/domain/examples/*.example.json` wird automatisch dem passenden Schema
   zugeordnet und validiert.

Sind alle Checks erfolgreich, ist der Stand kompatibel zur CI-Validierung.

### Typische Fehler & Hinweise

- **„ajv: command not found“**
  → `ajv-cli` fehlt global. Installieren wie oben beschrieben.
- **„no schemas found“**
  → Ordnerstruktur prüfen (Pfad muss exakt `contracts/domain` lauten).
- **„strict mode violation“**
  → Das Schema enthält Felder, die nicht definiert oder verboten sind.
  Schema überarbeiten oder `additionalProperties` explizit setzen.

### Warum dieser Check?

Er verhindert Schema-Drift: Weltgewebe ist ein eigenständiges Projekt, aber die Domain-Contracts sind eine
stabile, externe Schnittstelle. Durch lokale Validierung bleibt alles synchron zu CI und Dokumentation.

### Mirror absichern

Wenn du Contracts aus dem Metarepo spiegelst (z. B. nach `contracts-mirror/json`),
nutze den Guard, um Drift zu vermeiden:

```bash
CANONICAL_CONTRACTS_DIR=/pfad/zum/metarepo/contracts \
MIRROR_DIR=contracts-mirror/json \
bash ./scripts/contracts-mirror-guard.sh
```

Der Guard schlägt fehl, sobald Spiegel und Kanon voneinander abweichen. Änderungen gehören immer zuerst in
den Kanon; der Mirror wird nur aktualisiert, um lokale Validierung zu ermöglichen.
