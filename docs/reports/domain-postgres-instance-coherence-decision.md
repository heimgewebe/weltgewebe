---
id: reports.domain-postgres-instance-coherence-decision
title: "Domain PostgreSQL Instance Coherence Decision — DOMAIN-PG-002"
doc_type: report
status: active
lifecycle_state: active
lifecycle: audit
owner_task: DOMAIN-PG-002
review_after: 2026-12-18
created: 2026-06-18
last_reviewed: 2026-06-19
lang: de
summary: >
  DOMAIN-PG-002 entscheidet für den aktuellen PostgreSQL-Domain-Pfad Option A:
  höchstens eine API-Instanz innerhalb dieser Kohärenzgrenze. Prozesslokale
  Domain- und Auth-Zustände besitzen keine getestete instanzübergreifende
  Invalidierung. Ein statischer Guard blockiert klar erkennbare Scale-out-Drift.
relations:
  - type: relates_to
    target: docs/blueprints/domain-data-postgres-cutover.md
  - type: relates_to
    target: docs/tasks/index.json
  - type: relates_to
    target: docs/tasks/board.md
  - type: relates_to
    target: apps/api/src/state.rs
  - type: relates_to
    target: scripts/guard/domain-single-instance-guard.sh
  - type: relates_to
    target: scripts/tests/test_domain_single_instance_guard.sh
---

# Domain PostgreSQL Instance Coherence Decision

- Task: `DOMAIN-PG-002`
- Entscheidung: **Option A — Single-Instance-Invariante**
- Status: `done / decision-recorded / guard-backed`

## Kurzurteil

Für den aktuellen PostgreSQL-Domain-Pfad darf innerhalb dieser Kohärenzgrenze
höchstens eine API-Instanz laufen. Der Normalbetrieb erwartet eine lebende
API-Instanz. Horizontale API-Skalierung bleibt ausgeschlossen, bis entweder
prozesslokale autoritative Domain-Caches entfallen oder eine getestete
instanzübergreifende Invalidierungs- beziehungsweise Kohärenzlösung existiert.

`scale: 0`, `deploy.replicas: 0` und `docker compose --scale api=0` verletzen
die Kohärenzgrenze nicht. Die Entscheidung ist daher kein Verfügbarkeitsbeweis.
Sie ist auch keine Multi-Instance-Kohärenzimplementierung.

## Problem

`nodes`, `edges` und `accounts` werden beim Start geladen und anschließend aus
prozesslokalen `Arc<RwLock<…>>`-Strukturen gelesen. Optionale PostgreSQL-
Schreibpfade aktualisieren PostgreSQL und den lokalen Cache derselben Instanz.
Eine zweite Instanz sieht diesen lokalen Cache-Write nicht automatisch.

Auch Teile des Auth-Zustands bleiben prozesslokal: Magic-Link-Tokens,
Step-up-Tokens, Challenges und Passkey-Zwischenzustände. Ohne explizite
Invalidierung entsteht bei mehreren Instanzen ein stiller Cache-Split-Brain.

## Geprüfte Evidenz

Runtime und State:

- `apps/api/src/state.rs`
- `apps/api/src/lib.rs`
- `apps/api/src/domain_db.rs`
- `apps/api/src/routes/accounts.rs`
- `apps/api/src/routes/nodes.rs`
- `apps/api/src/routes/edges.rs`
- `apps/api/src/routes/auth.rs`
- `apps/api/src/auth/accounts.rs`
- `apps/api/src/auth/session.rs`
- `apps/api/src/auth/session_db.rs`
- `apps/api/src/auth/tokens.rs`
- `apps/api/src/auth/step_up_tokens.rs`
- `apps/api/src/auth/challenges.rs`
- `apps/api/src/auth/passkeys.rs`

Deployment und Automatisierung:

- `infra/compose/compose.core.yml`
- `infra/compose/compose.prod.yml`
- `infra/compose/compose.prod.override.yml`
- `infra/compose/compose.heimserver.override.yml`
- `infra/caddy/Caddyfile*`
- `scripts/weltgewebe-up`
- `.github/workflows/compose-smoke.yml`
- `Makefile`, `Justfile`, `.devcontainer`

## Zustandsmatrix

| Oberfläche | Prozesslokal | DB-gestützt | Instanzübergreifende Invalidierung | Konsequenz |
|---|---:|---:|---:|---|
| accounts | ja | Read/Write opt-in | nein | Single-Instance-Grenze |
| nodes | ja | Read/Write opt-in | nein | Single-Instance-Grenze |
| edges | ja | Read/Write opt-in | nein | Single-Instance-Grenze |
| sessions | ohne `DATABASE_URL` | mit `DATABASE_URL` | PostgreSQL ist gemeinsame Wahrheit | allein nicht ausreichend |
| magic-link tokens | ja | nein | nein | Single-Instance-Grenze |
| step-up tokens | ja | nein | nein | Single-Instance-Grenze |
| challenges | ja | nein | nein | Single-Instance-Grenze |
| Passkey-Zwischenzustände | ja | nein | nein | Single-Instance-Grenze |
| `nats_client` | optional | nicht zutreffend | kein Domain-Invalidierungspfad | keine Kohärenzlösung |

DB-gestützte Sessions heben die Grenze nicht auf, weil Domain-Caches und weitere
Auth-Zustände weiterhin prozesslokal bleiben. NATS wird nur als optionale
Infrastruktur beziehungsweise im Readiness-Kontext verwendet; ein getesteter
Publish-/Subscribe-Invalidierungspfad für Domain-Caches existiert nicht.

## Topologiebefund

In den geprüften Compose-, Caddy-, Script-, CI- und Dokumentationsflächen wurde
keine beabsichtigte API-Skalierung gefunden. Die vorhandenen Caddy-Routen nutzen
jeweils einen API-Upstream. `scripts/weltgewebe-up` skaliert nur Caddy auf null,
nicht die API.

Das ist ein statischer Repo-Befund. Er beweist weder den aktuellen Live-
Containerstand noch die Laufzeitkorrektheit.

## Entscheidung

Option A wird verbindlich gewählt:

1. Der aktuelle Domain-Pfad unterstützt höchstens eine API-Instanz.
2. Eine zweite Instanz darf nicht allein durch Konfigurationsdrift entstehen.
3. Multi-Instance-Betrieb benötigt einen neuen Task und eigenen Proof.
4. Die Entscheidung wird vorzeitig überprüft, sobald Domain-Reads vollständig
   DB-gestützt sind oder eine Invalidierungs-/Kohärenzschicht eingeführt wird.

## Operative Folgen

- Kein `api.scale` größer als eins.
- Kein `api.deploy.replicas` größer als eins.
- Kein direkter `api.replicas`-Key; diese Form ist auch mit `0` oder `1`
  unzulässig.
- Kein konkretes `docker compose --scale api=<value>`,
  `docker compose scale api=<value>` oder `docker-compose`-Äquivalent mit
  einem Wert ungleich null oder eins auf ausführbaren Flächen.
- Kein geschützter API-Upstream zusammen mit einem weiteren Upstream auf
  derselben Caddy-`reverse_proxy`- oder `to`-Direktivzeile.
- Optionale NATS-Verfügbarkeit gilt nicht als Cache-Kohärenz.

## Statischer Guard

`scripts/guard/domain-single-instance-guard.sh` wird über
`scripts/guard/run.sh` und den unabhängigen Job `Core Guard Tests` in
`.github/workflows/ci.yml` ausgeführt. Dieser Job hängt nicht vom
Markdown-/Docs-Filter des schweren `ci`-Jobs ab.
`scripts/tests/test_domain_single_instance_guard.sh` ruft stets den echten
Guard über einen `REPO_ROOT`-Override auf.

Der Guard prüft:

### Compose

Für blockartig geschriebenes Compose-YAML werden nur strukturell relevante Keys
unter `services.api` ausgewertet:

- direkter Key `scale`;
- direkter Key `replicas` als immer unzulässige Fehlkonfigurationsfläche;
- direkter Key `deploy.replicas`.

Nur die Literale `0` und `1`, optional vollständig einfach oder doppelt zitiert,
sind an `scale` und `deploy.replicas` erlaubt. Leere, numerisch größere,
symbolische, Alias- und expandierte Werte werden an diesen erkannten Keys
blockiert. Zitierte Mapping-Keys wie `"services"`, `'api'`, `"deploy"` und
`'replicas'` werden wie unzitierte Keys behandelt. Gleichnamige Keys unter
`environment`, `labels` oder tieferen Unterobjekten werden ignoriert.

Nicht statisch beweisbare Formen am `api`-Service oder seinem `deploy`-Block
werden fail-closed blockiert: ein Inline-Flow-Mapping (`api: { … }`,
`deploy: { … }`), ein Alias als vollständiger Wert (`api: *anchor`,
`deploy: *deployment`) und ein Merge-Key (`<<: *anchor`) auf API- oder
Deploy-Ebene. Reine Block-Anchor-Definitionen wie `api: &defaults` oder
`deploy: &deployment` sind erlaubt; die darunterliegenden Kinder werden
weiterhin geprüft. Eine vollständige YAML-Anker-/Merge-Auflösung findet bewusst
nicht statt.

### Docker-Compose-CLI

Auf ausführbaren Flächen (`scripts`, `infra`, `.github/workflows`,
`.devcontainer`, `Makefile`, `Justfile`) sind für API-Skalierungsargumente
hinter einem tokenbasiert erkannten `docker compose`- oder `docker-compose`-
Kommando nur `0` und `1` erlaubt. Erkannt werden insbesondere
`docker compose up --scale api=1`, `docker compose up --scale api 1`,
`docker compose scale api=1`, `docker compose scale api 1` und die
entsprechenden `docker-compose`-Formen. Fehlende, symbolische, expandierte oder
andere Werte werden blockiert. Zeilen wie `some compose scale api=2` oder
`some-tool --scale api=2` gelten nicht als Docker-Compose-Kommando.

In `docs` sind zusätzlich ausschließlich die abstrakten Platzhalter `N` und
`<value>` erlaubt. Die dokumentierte Positivliste ist damit `0`, `1`, `N` und
`<value>`. Alles andere bleibt blockiert, insbesondere `<N>`, `banana`,
`*alias`, `-1`, `1.5`, `<whatever>`, `${API_SCALE}` und `2`. Konkrete
ungültige Dokumentationswerte werden nicht als Platzhalter glattgebügelt.

Der CLI-Scan schließt `.git`, `node_modules`, `target`, `.venv` und
`docs/_generated` aus. `docs/_generated` ist eine generierte diagnostische
Oberfläche und wird nicht durch manuelle Guard-Reparaturen erzwungen.

Der CLI-Scanner ist kein vollständiger Shell-Parser. Quoted Strings, `echo`,
Shell-Aliase und komplexe Pipeline-Semantik bleiben bewusst außerhalb dieses
Schnitts.

### Caddy

Kommentare werden entfernt, bevor eine Direktive erkannt wird. Gezählt werden
`host:port`-Upstreams auf einer einzelnen `reverse_proxy`- oder `to`-Zeile,
inklusive optionalem `http://` beziehungsweise `https://` und geklammerter IPv6-
Adressen. Als geschützte API-Hosts gelten `api`, `weltgewebe-api` und ihre
numerisch suffigierten Instanznamen wie `api-2`, `api_2`, `api.2` oder
`weltgewebe-api-1`. Namen wie `api-gateway`, `capital-api` oder `myapi` gelten
nicht als diese API.

Nummerierte `weltgewebe-api`-Formen werden konservativ als potenzielle
API-Instanzidentitäten erkannt. Das macht sie nicht zu erlaubten oder stabilen
Routing-Aliasen; kanonischer stabiler Alias bleibt `weltgewebe-api`.

### Scanfehler und Exitcodes

Die Exitcodes sind getrennt: `0` = keine Verletzung, `1` = Single-Instance-
Policy verletzt, `2` = interner Fehler (ein Scanner wie `find`, `grep` oder
`awk` ist gescheitert oder eine Prüfung konnte nicht laufen). Interner Fehler
hat Vorrang vor der Policy-Verletzung. Ein gescheiterter oder abgestürzter
Scanner führt damit zu `2` (inconclusive), niemals zu einem stillen Pass und
niemals zu einem bestandenen Negativtest. Die Scanner sind über `FIND_BIN`,
`GREP_BIN` und `AWK_BIN` überschreibbar, damit Tests Fehlerfälle erzwingen
können.

## Bewusste Grenzen

Der Guard ist kein vollständiger YAML-, Shell- oder Caddy-Parser. Nicht belegt
sind insbesondere:

- vollständige Auflösung von Compose-Inline-Maps, YAML-Ankern und Merge-Keys
  (diese Formen werden am `api`-Service fail-closed blockiert, nicht aufgelöst);
- vollständige Shell-Semantik, Shell-Aliase, Quoting-Kontexte, `echo`-Beispiele
  und komplexe Pipeline-Auswertung;
- mehrzeilige Caddy-`to`-Blöcke mit einem Upstream pro Zeile;
- Caddy-Upstreamformen außerhalb der erkannten `host:port`-Tokens;
- alternative API-Aliasnamen außerhalb der dokumentierten Hostkonvention;
- der reale Live-Containerstand;
- Cross-Instance-Kohärenz oder Runtime-Korrektheit.

Diese Grenzen sind Claim-Grenzen, keine stillen Versprechen. Ein AST-basierter
Guard wäre ein eigener Toolchain- und CI-Schnitt.

## Review-Trigger

`review_after: 2026-12-18` ist nur ein Kalender-Backstop. Früher prüfen, wenn:

- Domain-Reads nicht mehr aus autoritativen Prozesscaches bedient werden;
- ein Invalidierungs-/Kohärenzmechanismus eingeführt wird;
- horizontale API-Skalierung gewünscht wird;
- Compose- oder Caddy-Topologie grundlegend geändert wird;
- die dokumentierten Parsergrenzen praktisch relevant werden.

## Folgearbeiten, nicht Teil von DOMAIN-PG-002

- optionaler YAML-AST-Guard mit gepinnter Toolchain;
- optionaler Caddy-AST-Guard über `caddy adapt`;
- gemeinsame Guard-Helper erst bei tatsächlich wiederholter stabiler Struktur;
- Runtime-Singleton-/Lease-Mechanismus nur als eigener Architekturentscheid;
- Claim-/Freshness-Integration für diese Invariante.

## Verwandte Blocker

- `DOMAIN-PG-001` bleibt durch `DB-PROOF-001` und die FK-vs-Guard-Entscheidung
  blockiert.
- `AUTH-PG-001` und `AUTH-PG-002` dürfen nur unter dieser Grenze fortschreiten.
- `OPT-ARC-001` bleibt `partial`.

## Nicht-Ziele

- keine Rust-Runtime-Änderung;
- keine SQL-Migration;
- keine Edge-FK-/Guard-Implementierung;
- keine Auth-Persistenzimplementierung;
- keine Redis-/PubSub-/NATS-Invalidierung;
- kein Multi-Instance-Kohärenz-Claim.
