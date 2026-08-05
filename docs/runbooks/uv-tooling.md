---
id: runbooks.uv-tooling
title: UV-Tooling
doc_type: reference
status: active
summary: Anleitung zum Einsatz von uv als Python-Paketmanager.
relations:
  - type: relates_to
    target: docs/runbooks/README.md
---
# UV Tooling – Ist-Stand & Ausbauoptionen

Dieser Runbook-Eintrag fasst zusammen, wie der Python-Paketmanager
[uv](https://docs.astral.sh/uv/) heute im Repo eingebunden ist und welche
Erweiterungen sich anbieten.

## Aktueller Stand

- **Installation im Devcontainer:** `.devcontainer/post-create.sh` installiert `uv`
  per offizieller Astral-Installroutine und macht das Binary direkt verfügbar.
- **Toolchain-Pin:** `toolchain.versions.yml` pinnt `uv` aktuell auf v0.8.0.  \
  In CI wird `uv` deterministisch über das offizielle Install-Script installiert,
  sodass keine fehleranfälligen Release-Asset-URLs mehr nötig sind. Falls du
  lokal eine andere Version testen möchtest, kannst du das Script
  mit Override nutzen:

  ```bash
  UV_VERSION=0.8.0 scripts/tools/uv-pin.sh ensure
  ```

  (Beliebige Zielversion via `UV_VERSION=<ziel>` möglich.)
- **Dokumentation im Root-README:** Das Getting-Started beschreibt, dass `uv`
  im Devcontainer bereitgestellt wird und dass Lockfiles (`uv.lock`) eingecheckt
  werden sollen.
- **Python-Tooling-Workspace:** Unter `tools/py` liegt das zentrale
  `pyproject.toml` für Repository-Helfer. `PyYAML==6.0.2` ist dort als erste
  Tooling-Abhängigkeit deklariert; `tools/py/uv.lock` bindet die zugelassenen
  Distributionsartefakte an SHA-256-Hashes.
- **Agent-Contract-Ausführung:** `just agent-contract-check` und
  `make agent-contract-check` / der volle `make validate`-Pfad nutzen
  `uv run --project tools/py --locked`. Direkte Teilaufrufe und Make teilen
  dieselbe Abhängigkeitsauflösung; fehlendes `uv`, Lock- oder Interpreterdrift
  sowie fehlende gebundene Abhängigkeiten enden fail-closed.
- **Plattform- und Policy-Checks:** `make platform-check` sowie die Workflows
  `kubernetes-platform`, `kubernetes-platform-proof`, `kubernetes-proof-oci-mirror`
  und `policycheck` binden PyYAML über dasselbe `tools/py/uv.lock` (nicht über
  ungebundene `pip install`-Versionen).

Damit ist `uv` der reproduzierbare Dependency-Pfad für Agent-, Vertrags- und
Plattform-Python-Tooling im Make- und CI-Pfad.

## Potenzial für Verbesserungen

1. **Dependency-Update:** Den Pin in `tools/py/pyproject.toml` ändern und mit der
   in `toolchain.versions.yml` gepinnten uv-Version `uv lock --project tools/py`
   ausführen. Danach den vollständigen PyYAML-Artefaktsatz und seine SHA-256-Hashes
   reviewen; nie ein ungebundenes `pip install` ergänzen.
2. **Lock-Beweis:** `uv sync --project tools/py --locked` sowie die negativen
   Lock-Fixtures aus `scripts/agent/tests/test_agent_tooling_lock.py` ausführen.
   Falsche oder fehlende Hashes und eine vom Lock abweichende Version müssen
   fail-closed enden.
3. **Weitere Tooling-Abhängigkeiten:** Nur in demselben Workspace ergänzen und das
   Lockfile im gleichen Commit aktualisieren. Separate Workflow-Pins würden wieder
   konkurrierende Dependency-Wahrheiten erzeugen.
4. **Fallback für lokale Maschinen:** Außerhalb des Devcontainers stellt
   `scripts/tools/uv-pin.sh ensure` die in `toolchain.versions.yml` dokumentierte
   uv-Version bereit.

Diese Punkte lassen sich unabhängig voneinander umsetzen und sorgen dafür, dass
`uv` vom vorbereiteten Tooling-Baustein zu einem reproduzierbaren Bestandteil
von lokalen und CI-Workflows wird.
