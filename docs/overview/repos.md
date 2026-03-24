---
id: overview.repos
title: Repository-Übersicht
doc_type: reference
status: active
summary: Übersicht aller Repositories der heimgewebe-Organisation mit Rolle, Sprache und Integrationsstatus.
relations:
  - type: relates_to
    target: docs/overview/inhalt.md
  - type: relates_to
    target: docs/overview/zusammenstellung.md
  - type: relates_to
    target: docs/x-repo/peers-learnings.md
---

# Repository-Übersicht (heimgewebe)

Die heimgewebe-Organisation umfasst 21 Repositories. Dieses Dokument listet alle Repositories
mit Rolle, Primärsprache und Kurzbeschreibung und ordnet sie in funktionale Cluster ein.

## Alle Repositories

| Repository | Sprache | Rolle | Kurzbeschreibung |
|---|---|---|---|
| **weltgewebe** | Rust, TypeScript, Svelte | Stack (Service) | Mobile-first Webprojekt mit SvelteKit, Rust/Axum, Postgres+Outbox, JetStream und Caddy. |
| **metarepo** | Shell | Control Plane | Zentrale Meta-Ebene für die Fleet-Verwaltung. Spiegelt kanonische Templates (Workflows, Justfile, Docs, WGX-Profile) in Sub-Repos. |
| **wgx** | Shell | Fleet Motor / CLI | Standalone-CLI für Git/Repo-Workflows. Orchestriert Dependencies, Task-Ausführung und Metriken über `.wgx/profile.yml`. |
| **contracts-mirror** | JavaScript | Schema-Spiegel | Spiegelt und validiert kanonische Contracts aus dem Metarepo. Enthält Proto/gRPC-Contracts, JSON-Schemas und Fixtures. |
| **hausKI** | Rust | KI-Orchestrator | Lokaler KI-Orchestrator für Workstations mit NVIDIA-RTX GPU. Rust-first, Offline-Default, GPU-aware. |
| **hausKI-audio** | Rust | Audio-Pipeline | Audio-Handling: Hi-Res Playback, Recording, Scripting/Automation CLI und Web-Panel-Fassade. |
| **semantAH** | Python | Semantik / Knowledge-Graph | Semantik-Index und Graph-Layer. Erstellt Embeddings, baut Indizes und Knowledge-Graphen aus Notizen. |
| **chronik** | Python | Event-Ingest | HTTP-Ingest-Service (FastAPI) für strukturierte Events als JSON. Speichert Domain-Events in JSONL. |
| **heimgeist** | TypeScript | Meta-Agent | System-Selbstreflexions-Engine. Orchestriert Agenten (sichter, wgx, hausKI, heimlern) und analysiert Repos und CI-Pipelines. |
| **mitschreiber** | Python | Context Writer | On-Device Context Writer. Erfasst aktive Anwendungen und Kontext. Offline-first, Privacy-first. |
| **leitwerk** | Shell | Enforcement-Organ | Koordinations- und Enforcement-Organ für agentive Arbeit. Entscheidet, ob Vorschläge umgesetzt werden. |
| **agent-control-surface** | Python | Git-Workflow-UI | Lokale Web-UI für Jules-CLI-Sessions und sichere Git-Workflows. Rendert Diffs, verwaltet Branches. |
| **aussensensor** | Shell | Feed-Kurator | Kuratiert externe Informationsquellen (Newsfeeds, Wetter, Status) und liefert konsistentes Event-Format für chronik. |
| **plexer** | TypeScript | Event-Router | Event-Netzwerk für Heimgewebe. Routet Events an Consumers (Heimgeist, Chronik, Leitstand, hausKI). |
| **sichter** | Python | Code-Reviewer | Autonomer Code-Reviewer und Auto-PR-Engine. Analysiert Diffs, generiert Vorschläge, bewertet Risiken. |
| **lenskit** | Python | Repo-Scanner | Merger und Scanner für strukturierte Repository-Aufbereitung. Bereitet Repos für LLMs auf. |
| **snippet-engine-control** | TypeScript | Text-Expansion | Engine-neutrale Steuerungs- und Diagnose-Ebene für Text-Expansion-Systeme (z. B. Espanso). |
| **heimlern** | Rust | Policy-Engine | Lernbare Policies für Haushaltsumgebung. Bandit-Agenten mit Explore/Exploit, Snapshots und Audit-Trail. |
| **leitstand** | TypeScript | Dashboard | Dashboard und Leitstelle für den Heimgewebe-Organismus. Täglicher System-Digest und Steuer-Interface. |
| **vault-gewebe** | JavaScript | Knowledge Vault | Persönliches und geteiltes Wissens-Vault (Obsidian). Konsumiert Schemas, produziert semantischen Index. |
| **obsidian-bridge** | Python | Obsidian-CLI | Obsidian als UI-Layer für Maschinen-Artefakte (Observatorium). Deterministische CLI-Interfaces. |

## Funktionale Cluster

### Kern-Stack

Das Herzstück der Plattform:

- **weltgewebe** – Web-App und API (SvelteKit + Rust/Axum)
- **metarepo** – Fleet-Verwaltung und kanonische Templates
- **wgx** – CLI-Motor für Task-Ausführung und Metriken
- **contracts-mirror** – Schema-Validierung und Contract-Spiegel

### KI & Semantik

Lokale Intelligenz und Wissensverarbeitung:

- **hausKI** – KI-Orchestrator (GPU-aware, Offline-first)
- **hausKI-audio** – Audio-Pipeline und Telemetrie
- **semantAH** – Knowledge-Graph und Embedding-Engine
- **heimlern** – Lernbare Policy-Engine mit Bandit-Agenten

### Event-Infrastruktur

Eventgetriebene Kommunikation zwischen Services:

- **chronik** – Event-Ingest und Persistenz (JSONL)
- **plexer** – Event-Router mit Fanout an Consumers
- **aussensensor** – Feed-Kurator für externe Quellen
- **mitschreiber** – On-Device Context Writer

### Agenten & Steuerung

Autonome Agenten und Koordination:

- **heimgeist** – Meta-Agent und Selbstreflexion
- **sichter** – Code-Review und Auto-PR-Engine
- **leitwerk** – Enforcement-Organ für agentive Arbeit
- **agent-control-surface** – Git-Workflow-UI für sichere Operationen
- **lenskit** – Repository-Scanner und LLM-Aufbereitung

### Wissen & Oberflächen

Wissensmanagement und Benutzeroberflächen:

- **leitstand** – Dashboard und System-Digest
- **vault-gewebe** – Obsidian-basiertes Knowledge Vault
- **obsidian-bridge** – CLI-Interface für Obsidian-Artefakte
- **snippet-engine-control** – Text-Expansion-Steuerung

## Integrationsmuster

### Workflow-Delegation

Weltgewebe konsumiert wiederverwendbare Workflows aus drei Quellen:

| Quelle | Workflow | Zweck |
|---|---|---|
| metarepo | `wgx-metrics.yml` | Metriken-Erfassung |
| metarepo | `heimgewebe-command-dispatch.yml` | PR-Kommando-Verarbeitung |
| wgx | `wgx-guard.yml` | Kanonische Guard-Prüfungen |
| wgx | `wgx-smoke.yml` | Smoke-Tests |
| contracts-mirror | `contracts-ajv-reusable.yml` | JSON-Schema-Validierung |

### Event-Fluss

```
aussensensor → plexer → chronik (Persistenz)
mitschreiber ──┘    ├──→ heimgeist (Analyse)
                    ├──→ leitstand (Dashboard)
                    └──→ hausKI (KI-Verarbeitung)
```

### Contract-Kette

```
metarepo (Source of Truth)
  └──→ contracts-mirror (Spiegel + Validierung)
         └──→ weltgewebe, hausKI, ... (Konsumenten)
```

## Hinweise

- **Eigenständigkeit:** Weltgewebe ist ein eigenständiges Projekt. Die übrigen Repositories sind
  optionale Quellen und Werkzeuge, keine monolithische Codebasis.
- **semantAH-Integration:** Aktuell ausgesetzt (ADR-0042). Reaktivierung erfordert eine neue ADR.
- **Vollständigkeit:** Diese Übersicht spiegelt den Stand aller öffentlichen Repositories der
  heimgewebe-Organisation wider.
