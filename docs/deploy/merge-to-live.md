---
id: deploy-merge-to-live-contract
title: Merge-to-Live-Vertrag
status: active
doc_type: runbook
summary: Verbindlicher Pfad von origin/main bis zum öffentlich verifizierten Produktionsstand.
last_reviewed: "2026-07-15"
relations:
  - type: relates_to
    target: docs/deployment.md
  - type: relates_to
    target: docs/deploy/vps.md
  - type: relates_to
    target: scripts/ops/reconcile-production-main-vps.sh
  - type: relates_to
    target: scripts/ops/deploy-exact-commit-vps.sh
---

# Merge-to-Live-Vertrag

Ein Merge ist noch keine Auslieferung. Weltgewebe unterscheidet deshalb vier
Zustände:

1. `merged`: Der Commit liegt auf `origin/main`.
2. `building`: Eine flüchtige Container-Arbeitskopie wird aus dem Commit gebaut.
3. `deployed`: API, Webartefakt und Edge wurden für diesen Commit gestartet.
4. `verified`: Frontend und API liefern öffentlich exakt denselben vollständigen
   Commit wie `origin/main`.

Nur `verified` schließt eine Produktionsänderung ab.

## Selbständiger Produktions-Reconciler

`weltgewebe-production-reconcile.timer` läuft auf dem VPS alle zwei Minuten.
Der zugehörige root-eigene Dienst:

1. aktualisiert ausschließlich `refs/remotes/origin/main`;
2. liest den vollständigen Zielcommit;
3. beendet sich ohne Änderung, wenn Frontend, API und Build-Header diesen
   Commit bereits öffentlich liefern;
4. exportiert den Commit als root-eigenes, schreibgeschütztes Quellarchiv;
5. baut das Frontend vollständig im flüchtigen Arbeitsspeicher eines
   digestgepinnten Node-Containers;
6. übernimmt ausschließlich den begrenzten Archivstrom des statischen
   `build/`-Baums und prüft Typen, Pfade, Größe, Hash und Commitidentität;
7. prüft nach dem Build erneut, dass `main` nicht weitergewandert ist;
8. legt einen getrennten, root-eigenen Release-Worktree unter
   `/opt/weltgewebe-releases/<commit>` an und prüft dessen Git-Integrität;
9. bindet die kanonischen root-eigenen PMTiles schreibgeschützt ein und ruft
   den vorhandenen, fail-closed arbeitenden `weltgewebe-up`-Pfad auf;
10. liest Frontend und API öffentlich zurück und schreibt einen Receipt.

Der Produktionsserver benötigt dadurch weder den Heim-PC noch einen allgemein
berechtigten GitHub-Runner, um einen gemergten Stand auszuliefern.

## Sicherheitsgrenze

Der bestehende Checkout `/opt/weltgewebe` darf betriebliche Änderungen und
Sicherungsdateien enthalten. Der Reconciler verwendet ihn nur als
Git-Objektspeicher und als Quelle persistenter Kartenarchive. Er führt dort
weder `reset`, `clean`, `switch`, Merge noch Fast-Forward aus. Die persistenten
PMTiles müssen root-eigen und für Gruppe sowie Welt schreibgeschützt sein;
Release-Worktrees verweisen nur auf diesen kanonischen Datenbestand.

Der Webbau läuft nicht direkt als Root auf dem Host. Stattdessen gilt:

- digestgepinnter Node-Container;
- nicht privilegierter Hostbenutzer im Container;
- alle Linux-Capabilities entfernt;
- `no-new-privileges`;
- schreibgeschütztes Container-Dateisystem;
- begrenzte Prozess- und Speicherzahl;
- kein Heimverzeichnis, SSH-Agent, Laufzeitgeheimnis oder Docker-Socket;
- keine beschreibbare Host-Arbeitskopie; nur der begrenzte Archivstrom auf Standardausgabe verlässt den Container;
- der später von Root ausgeführte Release-Worktree wird erst getrennt erzeugt und bleibt für Buildskripte unerreichbar.

Das Webarchiv wird vor einer Root-Extraktion unabhängig geprüft:

- maximal 256 MiB komprimiert und 512 MiB entpackt;
- höchstens 20.000 Einträge;
- ausschließlich der Pfadbaum `build/`;
- keine Pfadflucht oder doppelten Namen;
- nur reguläre Dateien und Verzeichnisse;
- keine Links, Geräte oder erhöhten Berechtigungsbits;
- exakte SHA-256- und Commitbindung.

## Nebenläufigkeit und Weiterwanderung

Ein Host-Lock erlaubt nur einen Reconcile-Lauf gleichzeitig. Zusätzlich
verwendet der eigentliche Deploypfad einen eigenen Deploy-Lock. Wenn `main`
während des Containerbaus weiterwandert, wird der bereits gebaute Stand nicht
mehr ausgeliefert; der nächste Timerlauf beginnt mit dem neuen Commit.
Unmittelbar vor dem Deployment prüft der Root-Helfer `origin/main` erneut.

## Öffentlicher Nachweis

Der Workflow `Production live contract` vergleicht bei jedem Push auf `main`
und zusätzlich alle fünf Minuten:

- `https://weltgewebe.net/_app/version.json`;
- `https://weltgewebe.net/api/version`;
- `X-Weltgewebe-API-Build`;
- `X-Weltgewebe-Build`.

Bei einem Push wartet der Workflow begrenzt auf das Rollout. Danach schlägt er
fehlgeschlossen fehl und lädt den maschinenlesbaren Receipt auch im
Fehlerfall hoch. Ein stiller Zustand `main != live` ist damit nicht mehr grün.

## Belege

Root-eigene Produktionsbelege liegen unter
`/var/lib/weltgewebe-main-reconciler/receipts/`. Zusätzliche
Reconcile-Beobachtungen liegen unter
`/var/lib/weltgewebe-main-reconciler/reconcile-receipts/`. Sie enthalten den
vollständigen Commit, die SHA-256 des Webartefakts sowie Frontend- und
API-Readback.

## Einmalige Installation

Nach Merge und exakter Review wird der Reconciler auf dem VPS einmalig aus dem
geprüften Commit installiert:

```bash
sudo -n ./scripts/ops/install-production-reconciler.sh
```

Danach übernimmt der VPS-Timer alle weiteren `main`-Abgleiche selbständig.
