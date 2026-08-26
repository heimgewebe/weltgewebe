---
id: adr.0014-accountable-collective-node-mutations
title: ADR-0014 — Nachvollziehbare kollektive Knotenmutationen
doc_type: reference
status: active
summary: Optimistische Konflikterkennung, private Mutationsbelege, permanente Node-Entfernung, getrennte Missbrauchsgrenzen und datensparsame Messbarkeit.
relations:
  - type: relates_to
    target: docs/specs/objektlebenszyklen-und-loeschwirkungen.md
  - type: relates_to
    target: architecture/security.md
  - type: relates_to
    target: docs/specs/ui-interaction.md
---
# ADR-0014: Nachvollziehbare kollektive Knotenmutationen

## Status

accepted

## Kontext

Alle authentifizierten Weber dürfen gemeinsam gepflegte Knoten unmittelbar
bearbeiten und aus dem aktiven Gewebe entfernen. Eigentumsbasierte Sperren würden
diesen Kollektivgutvertrag brechen. Ohne zusätzliche technische Grenzen könnten
jedoch parallele Änderungen überschrieben, erfolgreiche Mutationen keinem Akteur
zugeordnet, Löschwirkungen missverstanden oder die Endpunkte missbraucht werden.

## Entscheidung

### Konflikte

`PATCH`, `PUT` und `DELETE` bleiben optimistisch nebenläufig. Der Client sendet
den zuletzt gelesenen `ETag` als `If-Match`. Fehlt er, antwortet die API mit
HTTP 428. Ist er veraltet, antwortet sie mit HTTP 412 und der aktuellen
Knotenprojektion. PostgreSQL-Advisory-Lock und JSONL-Prozesslock verhindern, dass
zwei bereits akzeptierte Mutationen desselben Knotens gleichzeitig persistieren.

### Privater Mutationsbeleg

Jeder erfolgreiche vollständige Ersatz – einschließlich eines inhaltlich
unveränderten, aber akzeptierten PUT – und jede erfolgreiche Entfernung erzeugt
einen privaten, nicht über die Node-API lesbaren Beleg mit:

- zufälliger Operations-ID,
- Operation `replace` oder `delete`,
- Ziel-ID und UTC-Zeitpunkt,
- domänenseparatem SHA-256 der Account-ID,
- Vorher- und gegebenenfalls Nachher-Hash der kanonischen Knotenprojektion.

PostgreSQL schreibt Fachmutation und Beleg in derselben Transaktion. Im
JSONL-Betrieb wird ein fsync-gesicherter `prepared`-Beleg vor der Mutation und ein
finaler `committed`- oder `aborted`-Beleg danach geschrieben. Beim Start werden
liegengebliebene Vorbereitungen anhand der aktuellen Knotenprojektion
reconciled; ein dritter, nicht erklärbarer Zustand stoppt fail-closed.

Die JSONL-Belegdatei liegt **laufzeitrelativ zum Elternverzeichnis von `GEWEBE_IN_DIR`** unter `.node-mutation-audit/events.jsonl`; das Verzeichnis hat Modus 0700, die Datei 0600. Symlink-Ziele werden abgelehnt.

### Löschentscheidung

Das normale Node-DELETE ist **permanentes Entfernen aus der aktiven Welt**, kein
Soft-Delete und kein zeitlich begrenztes Undo. Es entfernt den aktiven Knoten und
seine abgeleiteten Node-Fäden. Nichtleere Conversations, Beiträge sowie die
private Audit-/Outboxgeschichte bleiben nach dem kanonischen Lebenszyklusvertrag
erhalten. JSONL-Write-ahead-Journal und PostgreSQL-Transaktion machen einen
fehlgeschlagenen oder unterbrochenen Löschversuch rückrollbar; eine bereits
erfolgreich abgeschlossene Nutzerlöschung wird nicht über die öffentliche API
wiederhergestellt.

Ein physischer Purge der erhaltenen Geschichte ist nicht implementiert und wird
nicht als Route exponiert. Er benötigt vor einer späteren Aktivierung einen
eigenen Hochrisikovertrag für Primärdaten, Replikate, Indizes, Exporte und
Backups.

### Aufbewahrung

Die privaten Mutationsbelege besitzen in diesem Vertragsstand **keinen automatischen
TTL**. Sie werden mit den betrieblichen Zellbelegen aufbewahrt, bis ein eigener,
rechtlich und technisch geprüfter Purgevertrag ihre Entfernung autorisiert. Das
ist eine ausdrückliche fail-closed Aufbewahrungsentscheidung und keine Behauptung,
dass unbegrenzte Speicherung in jedem Rechtsraum zulässig wäre.

Gespeichert werden keine Knotentexte, Titel, Adressen oder Roh-Account-IDs,
sondern nur Operationsmetadaten und domänenseparierte Fingerprints. Backups dürfen
die Belege nur innerhalb des bestehenden privaten Backupvertrags übernehmen. Ein
späterer Retentions- oder Purgebeschluss muss Primärdaten, JSONL-Datei,
PostgreSQL, Replikate und Backups gemeinsam behandeln.

### Missbrauchsgrenzen

Knotenmutationen besitzen eigene, accountgebundene Minuten- und Stunden-Buckets:

- Replace/Patch: 30 pro Minute, 300 pro Stunde,
- Delete: 10 pro Minute, 50 pro Stunde.

Alle vier Grenzwerte müssen größer als null bleiben; `0` wird beim Start
fail-closed abgelehnt. Die Werte sind konfigurierbar. Diese Buckets verwenden weder Login-E-Mail- noch
IP-Zähler. Ein Administrator kann die Mutationslimits nur umgehen, wenn
`admin_emergency_bypass` ausdrücklich aktiviert ist; der Standard ist `false`.
Jeder solche Bypass wird als eigene Metrik gezählt.

### Messbarkeit

Prometheus erhält ausschließlich feste Labels für Operation, Ergebnis und
Recovery-Ausgang. Gemessen werden Anzahl, Konflikte, Latenz, Rate-Limit-/Fehlerklasse,
Admin-Bypass und JSONL-Recovery. Knoteninhalt, Knoten-ID und Account-ID sind als
Labels verboten.

## Folgen

- Die offene Weber-Bearbeitbarkeit bleibt unverändert.
- Konflikte werden sichtbar statt still überschrieben.
- Ein fehlender Auditbeleg verhindert PostgreSQL-Mutationen atomar.
- JSONL kann nach einem Prozessabbruch deterministisch abschließen oder stoppt
  bei nicht erklärbarer Divergenz.
- Die private Belegspur ist pseudonym, aber nicht anonym; Zugriff und Aufbewahrung
  bleiben deshalb Sicherheits- und Datenschutzaufgabe.
- Ein allgemeines Undo oder Purge entsteht durch diese Entscheidung ausdrücklich
  nicht.

## Nicht entschieden

- kein öffentlicher Auditbrowser,
- keine öffentliche Wiederherstellungsroute,
- kein rechtlicher oder administrativer Purge,
- keine eigentumsbasierte Einschränkung gemeinsamer Knoten.
