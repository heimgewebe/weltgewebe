---
id: deploy-merge-to-live-contract
title: Merge-to-Live-Vertrag
status: active
doc_type: runbook
summary: Verbindlicher Pfad von origin/main bis zum öffentlich verifizierten Produktionsstand.
last_reviewed: "2026-07-19"
relations:
  - type: relates_to
    target: docs/deployment.md
  - type: relates_to
    target: docs/deploy/vps.md
  - type: relates_to
    target: scripts/ops/reconcile-production-main-vps.sh
  - type: relates_to
    target: scripts/ops/deploy-exact-commit-vps.sh
  - type: relates_to
    target: scripts/ops/activate-production-reconciler-from-release.sh
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
10. bindet die kanonischen root-eigenen PMTiles schreibgeschützt ein, führt
    den idempotenten, API-begrenzten Migrations-Scope aus, hält dessen Abschluss
    als nicht-terminalen Zeitstempel im bestehenden Deployment-Receipt fest und
    prüft danach erneut, dass `origin/main` unverändert ist;
11. ruft erst anschließend den vollständigen fail-closed arbeitenden
    `weltgewebe-up`-Pfad auf; ein späterer Wiederholungsversuch prüft die
    Migration erneut und überspringt sie niemals allein aufgrund des Receipts;
12. liest Frontend, API und beide Build-Header über begrenzte GET-Anfragen
    öffentlich zurück;
13. aktualisiert den Zeiger auf den verifizierten Stand nur, wenn ein letzter
    Remote-Readback weiterhin denselben `origin/main`-Commit ergibt.

Der Produktionsserver benötigt dadurch weder den Heim-PC noch einen allgemein
berechtigten GitHub-Runner, um einen gemergten Stand auszuliefern.

Vor dem Start oder der Änderung von Docker-Containern eines commitgebundenen
VPS-Releases aktiviert `scripts/weltgewebe-up` außerdem den Operatorvertrag aus
genau diesem Release.
Der Aktivator akzeptiert nur den vollständigen root-eigenen Pfad
`/opt/weltgewebe-releases/<commit>`, prüft dessen Git-HEAD und ruft den offiziellen
Installer im verzögerten Modus auf. „Verzögert“ bedeutet: Helfer, Units,
Environment-Datei und Hashmanifest werden atomar ersetzt und unmittelbar
hashgeprüft, der bereits aktive Timer bleibt erhalten, aber es wird kein zweiter
Reconciler innerhalb des laufenden Deployments gestartet. Der nächste reguläre
Timerlauf verwendet damit den neu gemergten Operatorvertrag. Reine
`--plan-only`-Läufe bleiben ohne diese Betriebsänderung.

## Sicherheitsgrenze

Der bestehende Checkout `/opt/weltgewebe` darf betriebliche Änderungen und
Sicherungsdateien enthalten. Der Reconciler verwendet seinen Arbeitsbaum nicht
als Releasequelle. Installierte Helfer und Releases werden aus dem exakten
Git-Objekt des geprüften Commits erzeugt. Weder `reset`, `clean`, `switch`,
Merge noch Fast-Forward verändern den bestehenden Checkout.

Der Git-Objektspeicher, die persistenten PMTiles, Releases und installierten
Helfer müssen root-eigen und für Gruppe sowie Welt nicht beschreibbar sein.
Release-Worktrees verweisen nur auf den kanonischen Kartenbestand.

Dass der Migrations-Scope bei einem bereits fehlenden Caddy arbeiten darf, ist
nur ein Wiederherstellungsverhalten für einen ausgefallenen Frontdoor-Pfad. Es
ist keine zusätzliche Berechtigung: Der Produktionspfad bleibt root-, Lock-,
Commit- und Artefakt-gebunden. Ein bloßer Environment-Schalter würde hier keine
Sicherheitsgrenze schaffen, weil ein bereits zur Docker-Deploymentausführung
berechtigter Aufrufer ihn selbst setzen könnte.

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

Eine gemeinsame Kernel-Sperre erlaubt nur einen Produktionsvorgang gleichzeitig.
Der Reconciler hält sie durch Build, Migration, Deployment und öffentlichen
Readback; der innere Deploy-Helfer verwendet denselben geerbten Deskriptor.
`origin/main` wird nach Build, unmittelbar vor Deployment und nach öffentlichem
Readback neu abgerufen.

Wandert `main` während des Builds weiter, wird das alte Artefakt nicht
installiert. Wandert `main` während oder unmittelbar nach dem Deployment weiter,
wird ein `superseded_after_deploy`- oder `superseded_after_verify`-Beleg
geschrieben. Der alte Commit wird nicht als aktueller Produktionsstand markiert;
der nächste Lauf nimmt den neuen Commit auf.

## Gemeinsame Produktionssperre

Alle unterstützten Produktions-Einstiege gehören zur Lock-Domäne
`weltgewebe-production-deployment-v1`. Der Reconciler öffnet und hält
`/var/lib/weltgewebe-main-reconciler/production-deployment.lock` vom ersten
Zustandsreadback bis zum abschließenden öffentlichen Beleg. Timer und Installer
starten ausschließlich dieselbe systemd-Unit; sie besitzen keinen separaten
Deploypfad.

Der Reconciler übergibt seinen bereits gesperrten Dateideskriptor an
`weltgewebe-deploy-exact-commit`. Der Helfer prüft Domäne, Deskriptornummer und
das tatsächliche `/proc`-Ziel, bevor er die geerbte Sperre verwendet. So bleibt
die gesamte Kette atomar, ohne dass der innere Helfer dieselbe Sperre nochmals
unabhängig anfordert und sich selbst blockiert. Der Helfer schließt den
Lock-Deskriptor gezielt für `weltgewebe-up`; dadurch können dessen mögliche
Hintergrundprozesse die Produktionssperre nicht unbeabsichtigt festhalten.

Jede Übergabe an den Deploy-Helfer erhält zusätzlich eine neue zufällige
Aufruf-ID. Terminale Deployment-Belege und Konkurrenzbelege binden diese ID.
Ein Beleg eines früheren Aufrufs darf deshalb selbst beim selben Commit keinen
neuen Exit 79 oder 80 legitimieren. Exit 75 bleibt grundsätzlich ein Fehler:
Der Reconciler unterscheidet nur anhand sicherer, root-eigener und nicht von
Gruppe oder Welt beschreibbarer Belege, ob der aktuelle Kindaufruf bereits als
fehlgeschlagen protokolliert wurde oder tatsächlich eine Sperrkonkurrenz meldete.
Diese Diagnose erweitert nicht die Lock-Wahrheit; Besitz wird weiterhin nur
durch die Kernel-Sperre bestimmt.

Alle autorisierenden Deployment- und Konkurrenzbelege werden in einem
root-eigenen, nicht gruppen- oder weltbeschreibbaren Verzeichnis über exklusiv
angelegte, symlinkfreie Deskriptoren geschrieben. Der Modus wird unabhängig von
der aufrufenden `umask` auf `0600` gesetzt; vor dem atomaren Austausch werden
Dateityp, Eigentümer und einfache Linkzahl per `fstat` geprüft. Beim Lesen werden
die Sicherheitsmetadaten und die begrenzten JSON-Bytes über denselben mit
`O_NOFOLLOW` geöffneten Deskriptor ausgewertet. Dadurch kann ein Pfadtausch
zwischen Prüfung und Auswertung keinen anderen Beleg unterschieben.

Ein ausdrücklich unterstützter direkter Recovery-Aufruf des Deploy-Helfers erwirbt
dieselbe Sperre selbst. Bei Konkurrenz verändert der abgewiesene Lauf weder
Container noch öffentliche Zustände. Der Reconciler endet geordnet mit Exit 0;
der direkte Helfer verwendet bei Konkurrenz `EX_TEMPFAIL` 75. Fachliche
Überholung nach Migration beziehungsweise Volldeploy verwendet intern die
getrennten Codes 79 und 80. Bei einem geerbten Handoff schreibt der Helfer den
autoritativen `already_running`-Beleg zunächst aufrufspezifisch nach
`receipts/contention/<deploy-invocation-id>.json`. Zusätzlich aktualisiert er für
die unmittelbare Rolling-Kompatibilität den gemeinsamen Diagnosepfad
`receipts/last-contention.json`. Ein direkter Recovery-Aufruf ohne Aufruf-ID
schreibt ausschließlich diesen gemeinsamen Pfad. Der Reconciler greift nur dann
auf den gemeinsamen Beleg zurück, wenn der aufrufspezifische Beleg fehlt; ein
vorhandener widersprüchlicher Aufrufbeleg bleibt fail-closed. Diese Belege sind
Diagnoseflächen, keine zweite Zustandswahrheit. Maßgeblich für Besitz ist
ausschließlich die vom Kernel gehaltene
`flock`-Sperre. Eine liegengebliebene Lockdatei ohne offenen Besitzer blockiert
daher keinen späteren Lauf.

Die früheren Dateien `reconcile.lock` und `deploy.lock` werden nicht mehr gelesen.
Ihre bloße Existenz besitzt keine Semantik. Die innere Compose-Wirkungssperre von
`scripts/weltgewebe-up` bleibt als untergeordneter Schutz gegen konkurrierende
Compose-Effekte bestehen; sie ersetzt nicht die gemeinsame Produktionsdomäne.

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

Root-eigene Deploymentbelege einschließlich des letzten direkten
Lock-Konflikts liegen unter
`/var/lib/weltgewebe-main-reconciler/receipts/`. Reconcile-Zustände, der letzte
Reconciler-Konflikt und öffentliche Readbacks liegen unter
`/var/lib/weltgewebe-main-reconciler/reconcile-receipts/`. Das
Installationsmanifest bindet die installierten Helfer und Units zusätzlich an
SHA-256.

Ist der exakte aktuelle Commit bereits öffentlich belegt, aber sein ursprünglicher
Deploymentbeleg fehlt, repariert der Reconciler die Zustandszeiger mit einem
`verified_observed`-Beleg. Dabei werden fehlende historische Werte wie
Webartefakt-Hash oder Startzeit ausdrücklich als unbekannt ausgewiesen und nicht
erfunden.

Schema-5-Belege werden fehlgeschlossen gegen eine geschlossene Feldmatrix
validiert. Beide Ergebnisarten enthalten ausschließlich
`schema_version`, `environment`, `commit`, `web_artifact_sha256`, `started_at`,
`completed_at`, `api_commit`, `frontend_commit`,
`observed_main_after_deploy`, `migration_completed_at`, `lock_domain`,
`lock_owner_entrypoint`, `lock_handoff`, `result` und
`deploy_invocation_id`. Nur `verified_observed` ergänzt `evidence_boundary`.
Unbekannte Zusatzfelder machen den Beleg ungültig.

| Schema-5-Ergebnis | Zeitvertrag | Evidenzgrenze |
| --- | --- | --- |
| `verified` | `started_at`, `migration_completed_at` und `completed_at` sind zeitzonenbehaftete ISO-Zeitpunkte; nach sicherer UTC-Normalisierung gilt `started_at <= migration_completed_at <= completed_at` | Webartefakt-Hash ist ein kleingeschriebener SHA-256; direkter Lock besitzt keine Aufruf-ID, geerbter Lock eine SHA-256-gebundene Aufruf-ID |
| `verified_observed` | nur `completed_at` ist ein zeitzonenbehafteter ISO-Zeitpunkt; `started_at` und `migration_completed_at` bleiben ausdrücklich `null` | Webartefakt-Hash und Aufruf-ID bleiben `null`; `evidence_boundary` ist ein nichtleerer Text und begrenzt die Aussage auf den öffentlichen Readback |

Zeitpunkte ohne Zeitzone, syntaktisch ungültige Werte, UTC-Überläufe und eine
widersprüchliche Reihenfolge werden nicht als aktueller Deploymentbeleg
akzeptiert. Der Reconciler ersetzt einen solchen, dateisystemseitig sicheren
Beleg erst nach einem frischen öffentlichen Readback durch `verified_observed`.

`verified` belegt die Code- und Webartefaktidentität. Laufzeitkonfiguration und
Karteninhalt bleiben bewusst außerhalb dieser Commitidentität; ihre Belegung
erfolgt über die bestehenden Produktions- und Kartenmanifeste.

## Initiale Installation

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
weiteren `main`-Abgleiche selbständig. Spätere Releases aktualisieren diesen
installierten Operatorvertrag über den oben beschriebenen Release-Aktivator;
ein erneuter manueller Installerlauf ist dafür nicht erforderlich.

## Bedrohungsmodell und Beweisgrenzen

Der Vertrag schützt gegen einen weiterwandernden `main`-Branch, parallele Reconciler,
manipulierte oder übergroße Webarchive, unerwartete Release-Worktree-Zustände und
einen öffentlichen Readback, der nicht exakt zum Zielcommit passt.

Er setzt weiterhin folgende Vertrauensanker voraus:

- Der root-eigene Git-Objektspeicher auf dem VPS ist unverändert und authentisch.
- Kernel, Docker-Daemon und Root-Kontext des VPS sind nicht kompromittiert.
- Das digestgepinnte Node-Basisimage und die über den Lockfile aufgelösten Pakete
  sind für den Build vertrauenswürdig.
- Der Build darf derzeit aus dem Bridge-Netz laden, weil `pnpm install
  --frozen-lockfile` innerhalb des flüchtigen Containers läuft. Ein vollständig
  netzloser Build benötigt das in `WELTGEWEBE-OS-V1-T015` geplante,
  repositoryeigene Buildimage mit vorab gebundenem Paketbestand.

`SOURCE_DATE_EPOCH`, der vollständige Commit und das digestgepinnte Basisimage
verbessern die Deterministik. Sie beweisen jedoch keine byteidentische
Reproduzierbarkeit des gesamten Node-Ökosystems. Deshalb bindet `verified` den
öffentlich gelesenen Code- und Webartefaktstand, nicht eine unabhängig
reproduzierte Buildgleichheit. Ein kompromittierter VPS-Root kann Receipts und
Laufzeit gleichermaßen manipulieren; dagegen hilft nur eine zusätzliche externe
Attestierungs- und Produktionsidentitätsachse, die in
`WELTGEWEBE-OS-V1-T014` weitergeführt wird.
