### 📄 weltgewebe/docs/runbooks/README.md

**Größe:** 205 B | **md5:** `f3721cf652e50a843846daaaced3ed2f`

```markdown
# Runbooks

Anleitungen für wiederkehrende Aufgaben.

- [UV Tooling – Ist-Stand & Ausbauoptionen](uv-tooling.md)
- [Codespaces Recovery](codespaces-recovery.md)
- [Zurück zum Doku-Index](../README.md)
```

### 📄 weltgewebe/docs/runbooks/codespaces-recovery.md

**Größe:** 173 B | **md5:** `4a21868f0d5ab097c1c5e387c812d4a7`

```markdown
# Codespaces Recovery

– Rebuild Container
– remoteUser temporär entfernen
– overrideCommand: true testen
– creation.log prüfen (Pfad siehe postStart.sh Hinweise)
```

### 📄 weltgewebe/docs/runbooks/semantics-intake.md

**Größe:** 233 B | **md5:** `e1aaf4a53383d8fc78af5ff828f74a41`

```markdown

# Semantics Intake (manuell)

1) Von semantAH: `.gewebe/out/nodes.jsonl` und `edges.jsonl` ziehen.
2) In Weltgewebe ablegen unter `.gewebe/in/*.{nodes,edges}.jsonl`.
3) PR eröffnen → Workflow `semantics-intake` validiert Format.
```

### 📄 weltgewebe/docs/runbooks/uv-tooling.md

**Größe:** 2 KB | **md5:** `e5aef3d92b551c437d85b82424d258f6`

```markdown
# UV Tooling – Ist-Stand & Ausbauoptionen

Dieser Runbook-Eintrag fasst zusammen, wie der Python-Paketmanager
[uv](https://docs.astral.sh/uv/) heute im Repo eingebunden ist und welche
Erweiterungen sich anbieten.

## Aktueller Stand

- **Installation im Devcontainer:** `.devcontainer/post-create.sh` installiert `uv`
  per offizieller Astral-Installroutine und macht das Binary direkt verfügbar.
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
```

