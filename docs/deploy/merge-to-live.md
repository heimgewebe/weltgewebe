---
id: deploy-merge-to-live-contract
title: Merge-to-Live-Vertrag
status: active
doc_type: runbook
summary: Verbindlicher Pfad von origin/main bis zum öffentlich verifizierten Produktionsstand.
last_reviewed: "2026-07-16"
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

Ein Merge ist noch keine Auslieferung. Weltgewebe unterscheidet deshalb:

1. `merged`: Der Commit liegt auf `origin/main`.
2. `building`: Eine flüchtige Container-Arbeitskopie wird aus dem Commit gebaut.
3. `artifact_validated`: Das statische Webarchiv ist begrenzt, typgeprüft und
   an den Commit gebunden.
4. `deploying`: API, Webartefakt und Edge werden für diesen Commit gestartet.
5. `verified`: Frontend und API liefern öffentlich exakt denselben vollständigen
   Commit, der nach dem Readback weiterhin `origin/main` ist.
6. `superseded_*`: Der Commit wurde zwar gebaut oder ausgeliefert, aber `main`
   ist weitergewandert; dieser Stand darf nicht als aktuell grün gelten.

Nur `verified` schließt eine Produktionsänderung ab.

## Selbständiger Produktions-Reconciler

`weltgewebe-production-reconcile.timer` startet den root-eigenen Dienst nach
jedem abgeschlossenen Lauf erneut mit einem Abstand von zwei Minuten. Der Dienst:

1. aktualisiert ausschließlich `refs/remotes/origin/main`;
2. liest den vollständigen Zielcommit;
3. beendet sich ohne Änderung, wenn Frontend, API und Build-Header diesen
   Commit bereits öffentlich liefern;
4. prüft mindestens 4 GiB freien Platz und einen vollständig root-eigenen,
   nicht für Gruppe oder Welt beschreibbaren Git-Objektspeicher;
5. exportiert den Commit als vorübergehendes root-eigenes Quellarchiv;
6. baut das Frontend im flüchtigen Arbeitsspeicher eines digestgepinnten
   Node-Containers;
7. übernimmt ausschließlich den begrenzten Archivstrom des statischen
   `build/`-Baums und prüft Typen, kanonische Pfade, Einzel- und Gesamtgrößen,
   Pflichtdateien, Hash und Commitidentität;
8. löscht das Quellarchiv unmittelbar nach dem Build und prüft erneut, dass
   `main` nicht weitergewandert ist;
9. legt einen getrennten root-eigenen Release-Worktree unter
   `/opt/weltgewebe-releases/<commit>` an und prüft dessen Git-Integrität;
10. bindet die kanonischen root-eigenen PMTiles schreibgeschützt ein und ruft
    den vorhandenen fail-closed arbeitenden `weltgewebe-up`-Pfad auf;
11. liest Frontend, API und beide Build-Header über begrenzte GET-Anfragen
    öffentlich zurück;
12. aktualisiert den Zeiger auf den verifizierten Stand nur, wenn ein letzter
    Remote-Readback weiterhin denselben `origin/main`-Commit ergibt.

Der Produktionsserver benötigt dadurch weder den Heim-PC noch einen allgemein
berechtigten GitHub-Runner, um einen gemergten Stand auszuliefern.

## Sicherheitsgrenze

Der bestehende Checkout `/opt/weltgewebe` darf betriebliche Änderungen und
Sicherungsdateien enthalten. Der Reconciler verwendet seinen Arbeitsbaum nicht
als Releasequelle. Installierte Helfer und Releases werden aus dem exakten
Git-Objekt des geprüften Commits erzeugt. Weder `reset`, `clean`, `switch`,
Merge noch Fast-Forward verändern den bestehenden Checkout.

Der Git-Objektspeicher, die persistenten PMTiles, Releases und installierten
Helfer müssen root-eigen und für Gruppe sowie Welt nicht beschreibbar sein.
Release-Worktrees verweisen nur auf den kanonischen Kartenbestand.

Der Webbau läuft nicht direkt als Root auf dem Host. Stattdessen gilt:

- digestgepinnter Node-Container;
- nicht privilegierter Hostbenutzer im Container;
- alle Linux-Capabilities entfernt;
- `no-new-privileges`;
- schreibgeschütztes Container-Dateisystem;
- begrenzte Prozess-, CPU- und Speicherzahl;
- kein Heimverzeichnis, SSH-Agent, Laufzeitgeheimnis oder Docker-Socket;
- keine beschreibbare Host-Arbeitskopie;
- nur der begrenzte Archivstrom auf Standardausgabe verlässt den Container;
- der später von Root ausgeführte Release-Worktree bleibt für Buildskripte
  unerreichbar.

Das Webarchiv wird vor einer Root-Extraktion unabhängig geprüft:

- maximal 256 MiB komprimiert und 512 MiB entpackt;
- maximal 64 MiB je Datei;
- höchstens 20.000 Einträge;
- ausschließlich kanonische UTF-8-Pfade unter `build/`;
- begrenzte Pfadlänge, Komponentlänge und Verzeichnistiefe;
- keine Pfadflucht, Steuerzeichen oder doppelten kanonischen Namen;
- nur reguläre Dateien und Verzeichnisse;
- keine Links, Geräte oder erhöhten Berechtigungsbits;
- Pflichtdateien `build/index.html` und `build/_app/version.json`;
- exakte SHA-256- und Commitbindung.

## Nebenläufigkeit und Weiterwanderung

Ein Host-Lock erlaubt nur einen Reconcile-Lauf gleichzeitig. Zusätzlich
verwendet der eigentliche Deploypfad einen eigenen Deploy-Lock. `origin/main`
wird nach Build, unmittelbar vor Deployment und nach öffentlichem Readback neu
abgerufen.

Wandert `main` während des Builds weiter, wird das alte Artefakt nicht
installiert. Wandert `main` während oder unmittelbar nach dem Deployment weiter,
wird ein `superseded_after_deploy`- oder `superseded_after_verify`-Beleg
geschrieben. Der alte Commit wird nicht als aktueller Produktionsstand markiert;
der nächste Lauf nimmt den neuen Commit auf.

## Speicherlebenszyklus

Quellarchive werden unmittelbar nach dem Containerbau gelöscht. Webarchive
werden auf höchstens 20 Exemplare und grundsätzlich sieben Tage begrenzt.
Release-Worktrees werden frühestens nach 14 Tagen entfernt. Der aktuelle und der
vorherige Release bleiben geschützt. Ein Worktree wird nur ohne `--force`
entfernt, wenn er root-eigen, commitförmig, unverändert und nicht einer der zwei
geschützten Releases ist.

## Öffentlicher Nachweis

Der Workflow `Production live contract` vergleicht bei jedem Push auf `main`
und zusätzlich alle fünf Minuten:

- `https://weltgewebe.net/_app/version.json`;
- `https://weltgewebe.net/api/version`;
- `X-Weltgewebe-API-Build`;
- `X-Weltgewebe-Build`.

Push- und Zeitplanbeobachter verwenden dieselbe GitHub-Concurrency-Gruppe. Ein
Zeitplanlauf kann daher nicht während eines noch laufenden Push-Rollouts einen
erwartbaren Fehlalarm erzeugen. Manuelle Läufe lösen ausdrücklich `main` auf.

Bei einem Push wartet der Workflow begrenzt auf das Rollout. Danach schlägt er
fehlgeschlossen fehl und lädt den maschinenlesbaren Receipt auch im Fehlerfall
hoch. Ein stiller Zustand `main != live` ist damit nicht grün.

## Belege und Vertragsgrenze

Root-eigene Deploymentbelege liegen unter
`/var/lib/weltgewebe-main-reconciler/receipts/`. Reconcile-Zustände und
öffentliche Readbacks liegen unter
`/var/lib/weltgewebe-main-reconciler/reconcile-receipts/`. Das
Installationsmanifest bindet die installierten Helfer und Units zusätzlich an
SHA-256.

`verified` belegt die Code- und Webartefaktidentität. Laufzeitkonfiguration und
Karteninhalt bleiben bewusst außerhalb dieser Commitidentität; ihre Belegung
erfolgt über die bestehenden Produktions- und Kartenmanifeste.

## Einmalige Installation

Nach Merge und exakter Review wird der Reconciler auf dem VPS einmalig aus dem
vollständigen geprüften `main`-Commit installiert:

```bash
sudo -n ./scripts/ops/install-production-reconciler.sh \
  --commit <vollständiger-main-commit> \
  --build-user alex
```

Der Installer liest die Helfer nicht aus dem möglicherweise veränderten
Arbeitsbaum, sondern direkt aus dem angegebenen Git-Objekt, prüft, dass dieser
Commit weiterhin `origin/main` ist, kompiliert und validiert die Dateien und
schreibt ein root-eigenes Hashmanifest. Danach übernimmt der VPS-Timer alle
weiteren `main`-Abgleiche selbständig.
