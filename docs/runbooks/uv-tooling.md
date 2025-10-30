# UV Tooling – Ist-Stand & Ausbauoptionen

Dieser Runbook-Eintrag fasst zusammen, wie der Python-Paketmanager
[uv](https://docs.astral.sh/uv/) heute im Repo eingebunden ist und welche
Erweiterungen sich anbieten.

## Aktueller Stand

- **Installation im Devcontainer:** `.devcontainer/post-create.sh` installiert `uv`
  per offizieller Astral-Installroutine und macht das Binary direkt verfügbar.
- **Toolchain-Pin:** `toolchain.versions.yml` pinnt `uv` aktuell auf v0.8.1; das
  Rollback von v0.8.2 verhindert 404-Fehler beim Download der Release-Assets in
  CI. Falls du lokal eine andere Version testen möchtest, kannst du das Script
  mit Override nutzen:

  ```bash
  UV_VERSION=0.8.1 scripts/tools/uv-pin.sh ensure
  ```

  (Beliebige Zielversion via `UV_VERSION=<ziel>` möglich.)
- **Dokumentation im Root-README:** Das Getting-Started beschreibt, dass `uv`
  im Devcontainer bereitgestellt wird und dass Lockfiles (`uv.lock`) eingecheckt
  werden sollen.
- **Python-Tooling-Workspace:** Unter `tools/py` liegt ein `pyproject.toml` mit
  Basiskonfiguration für Python-Helfer; zusätzliche Dependencies würden hier via
  `uv add` gepflegt.

Damit ist `uv` bereits für Tooling-Aufgaben vorbereitet, benötigt aber aktuell
noch keine Abhängigkeiten.

## Potenzial für Verbesserungen

1. **Lockfile etablieren:** Sobald der erste Dependency-Eintrag erfolgt, sollte
   `uv lock` ausgeführt und das entstehende `uv.lock` versioniert werden. Ein
   leeres Lockfile kann auch jetzt schon erzeugt werden, um den Workflow zu
   testen und künftige Änderungen leichter reviewen zu können.
2. **Just-Integration:** Ein `just`-Target (z. B. `just uv-sync`) würde das
   Synchronisieren des Tooling-Environments standardisieren – sowohl lokal als
   auch in CI.
3. **CI-Checks:** Ein optionaler Workflow-Schritt könnte `uv sync --locked`
   ausführen, um zu prüfen, dass das Lockfile konsistent ist, sobald Python-Tasks
   relevant werden.
4. **Fallback für lokale Maschinen:** Außerhalb des Devcontainers sollte das
   README kurz beschreiben, wie `uv` manuell installiert wird (z. B. per
   Installscript oder Paketmanager), damit Contributor:innen ohne Devcontainer
   den gleichen Setup-Pfad nutzen.

Diese Punkte lassen sich unabhängig voneinander umsetzen und sorgen dafür, dass
`uv` vom vorbereiteten Tooling-Baustein zu einem reproduzierbaren Bestandteil
von lokalen und CI-Workflows wird.
