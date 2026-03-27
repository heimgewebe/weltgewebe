---
id: docs.policies.agent-reading-protocol
title: Agent Reading Protocol
doc_type: policy
status: canonical
relations:
  - type: relates_to
    target: repo.meta.yaml
  - type: relates_to
    target: AGENTS.md
scope: global
description: "Bindendes Lese- und Entscheidungsprotokoll für Agentenarbeit im Weltgewebe-Repository"
summary: "Bindendes Lese- und Entscheidungsprotokoll für Agentenarbeit im Weltgewebe-Repository"
---

# Agent Reading Protocol

## Zweck

Dieses Dokument definiert das **verbindliche Lese-, Entscheidungs- und Abbruchverhalten**
für alle Agenten, die mit diesem Repository arbeiten.

Ziel:

- deterministische Entscheidungen
- keine stille Interpolation
- klare Konfliktauflösung

---

## 1. Lesereihenfolge (bindend)

Agenten MÜSSEN in dieser Reihenfolge lesen:

1. `repo.meta.yaml`
2. `AGENTS.md`
3. `agent-policy.yaml`
4. Policies / Contracts / explizit kanonische Dokumente
5. `docs/index.md` (nur Navigation)
6. `docs/_generated/*` (nur Diagnose)

---

## 2. Quellenrangfolge bei Widerspruch (Canonical Hierarchy)

Kanonisch definiert im `truth_model.precedence` von `repo.meta.yaml`.

Bei Konflikten gilt strikt diese absteigende Priorität:

1. `domain_contracts` (e.g., JSON schemas)
2. `canonical_policies` (e.g., `repo.meta.yaml`, `AGENTS.md`)
3. `runtime_configs_and_code` (e.g., Apps, CI, Compose)
4. `normative_specifications` (e.g., Blueprints, ADRs, Specs)
5. `diagnostic_reports` (e.g., Manual audits)
6. `navigational_indices` (e.g., `docs/index.md`)
7. `generated_diagnostics` (e.g., `docs/_generated/*`)

`generated_diagnostics` zeigen Probleme und Drift, sind aber NIEMALS kanonisch.

---

## 3. Navigation ist keine Wahrheit

`docs/index.md` dient ausschließlich der Orientierung.

Es darf NICHT als Entscheidungsquelle verwendet werden.

---

## 4. _generated ist Diagnose, nicht Ursprung

Artefakte unter `docs/_generated/*`:

- spiegeln Zustand
- zeigen Drift
- sind NICHT kanonisch

---

## 5. Abbruchregel (kritisch)

Agenten MÜSSEN abbrechen, wenn:

- relevante Dateien fehlen
- Widersprüche nicht auflösbar sind
- Runtime-Wahrheit unklar ist
- kein Target-Proof möglich ist

Form:

- „X fehlt, nötig für Y“

---

## 6. Interpolationsregel

Interpolation ist VERBOTEN, wenn Informationen nachlieferbar sind.

Stattdessen:

- explizite Leerstelle benennen

---

## 7. Arbeitsprinzip

- kleine PRs
- klare Scope-Grenzen
- keine stille Glättung
- Widersprüche sichtbar halten

---

## Essenz

Dieses Protokoll priorisiert:

- Entscheidbarkeit über Vollständigkeit
- Wahrheit über Lesbarkeit
- Abbruch über Halluzination
