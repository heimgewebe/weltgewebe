---
id: runbook.gewebezelle-two-operator-pilot-v1
title: Zwei-Betreiber-GewebeZelle-Pilotvertrag v1
doc_type: runbook
status: active
summary: >
  Beschreibt die fail-closed strukturelle Vorbereitung eines realen Zwei-Betreiber-Piloten auf Basis des kanonischen maschinenlesbaren Zellvertrags.
relations:
  - type: depends_on
    target: platform/cell-pilot/two-operator-pilot.contract.json
  - type: depends_on
    target: scripts/platform/validate_two_operator_pilot.py
  - type: relates_to
    target: docs/runbooks/gewebezelle-manual-pilot.md
  - type: relates_to
    target: docs/proofs/gewebezelle-two-operator-pilot-contract-v1.md
  - type: relates_to
    target: docs/tasks/board.md
---

# Zwei-Betreiber-GewebeZelle-Pilotvertrag v1

## Zweck

Der Vertrag schließt die Lücke zwischen dem manuellen Einzelzellenprofil und einem späteren realen WAN-Pilot. Er macht die Struktur eines gemeinsamen Aktivierungskandidaten zweier voneinander unabhängiger Betreiber prüfbar, ohne einen Operator, eine CRD, Self-Service oder einen Kubernetes-Produktionscutover vorwegzunehmen.

Die kanonischen Artefakte sind:

- `platform/cell-profile.contract.json` als allgemeine Mindestgrenze;
- `platform/cell-pilot/two-operator-pilot.contract.json` als versionierter Zwei-Betreiber-Vertrag;
- `platform/cell-pilot/two-operator-pilot.example.invalid.json` als absichtlich nicht aktivierbare Vorlage;
- `scripts/platform/validate_two_operator_pilot.py` als deterministischer Validator.

## Dokumentmodi

### `example`

Der öffentliche Repository-Stand enthält ausschließlich den Modus `example`. Er verwendet reservierte `.invalid`-Domains, `approved: false` und `REDACTED` für betriebliche Receipts. Der Validator akzeptiert ihn nur mit `activatable: false`. Derselbe Stand muss im Modus `activation` scheitern.

### `activation`

Ein tatsächlicher Aktivierungskandidat wird außerhalb dieses öffentlichen Repositories geführt. Es darf keine privaten Schlüssel oder Zugangsdaten enthalten, bindet aber reale Betreiber-, DNS-, TLS-, Release- und Belegidentitäten. Beide Betreiber müssen das exakt gleiche Dokument gegen denselben Vertrags-Digest prüfen und gemeinsam freigeben.

## Fail-closed Struktur- und externe Aktivierungsgates

Der statische Validator prüft nur die Struktur der folgenden Gruppen. Eine Aktivierung ist erst gültig, wenn zusätzlich jedes Receipt-Artefakt extern eingelesen, neu gehasht, claimgebunden gegen unabhängige Trust-Anker geprüft und in einem autoritativen Replay-Ledger unverbraucht registriert wurde:

| Gruppe | Pflicht |
|---|---|
| Betreiber | verschiedene Betreiber-IDs, verantwortliche Parteien, Kontakte und Kontrolldomains; der öffentliche Zellhost liegt unter der jeweiligen Kontrolldomain; getrennte Unabhängigkeitsbelege |
| Zellidentität | verschiedene Zell-IDs, HTTPS-Basis-URLs, aktive Key-IDs und Ed25519-Public-Keys; Zell-ID entspricht exakt dem URL-Host |
| Peerbindung | jede Zelle verweist exakt auf Identität, URL, Key-ID und Public Key der anderen Zelle; Ereignis-Whitelist ist symmetrisch und vollständig |
| Egress | exakt eine FQDN-Bindung zum Peer auf TCP 443 als `CiliumNetworkPolicy`; keine Wildcards, `world`-Entity oder CIDR-Freigaben |
| Release | beide Zellen verwenden denselben Git-Commit sowie dieselben API- und Web-Image-Digests; Restore-Belege binden denselben Commit |
| Daten | verschiedene externe Backupziele mit verschiedenen DNS-Autoritäten, konkrete Backup- und Restore-Receipts sowie gemessene RPO-/RTO-Werte |
| Betrieb | getrennte DNS-/TLS-Ownership und Alarmrouten, Delivery-Lag-Alarm vor dem SLO-Grenzwert, aktivierter Availability-Burn-Alarm sowie gestaffelte Upgrade- und Rollbackfenster |
| Verifikation | Identität und Peerbindung werden jeweils durch den anderen Betreiber über einen zugelassenen Out-of-band-Kanal bestätigt |
| Freigabe | `approved: true`, beide Betreiber-IDs in `approved_by`, konkreter Freigabebeleg und exakter SHA-256 des kanonischen Vertrags; dieser bindet zusätzlich den SHA-256 des allgemeinen Zellprofils |

Der Validator führt keine Netzwerkanfragen aus, verändert das Dokument nicht und weist doppelte oder unbekannte JSON-Schlüssel ab. Sein Ergebnis lautet auch im Modus `activation` stets `structurally_valid: true` und `activatable: false`. Hex-Digests sind nur Referenzen; ihre Artefakte, Signaturen, Claims, Failure-Domains und frühere Verwendung werden vom Repository-Validator nicht geprüft.

## Erforderliche Belege

Für jede Zelle werden getrennte SHA-256-Receipts gebunden für:

- erfolgreiche Anwendung eines Ereignisses;
- idempotenten Duplicate-Replay;
- Retry nach transientem Fehler;
- konkurrierende Worker ohne doppelte Wirkung;
- gerenderte exakte Egress-Policy;
- Backup und Restore;
- Upgrade und Rollback.

Jedes Receipt-Feld muss innerhalb desselben Dokuments einen eindeutigen SHA-256 bezeichnen; dokumentübergreifende Wiederverwendung kann nur ein externer autoritativer Replay-Ledger verhindern. Ein einzelnes Artefakt darf nicht mehrere Behauptungen oder Zellen zugleich belegen. Das dokumentierte Restore beider Zellen muss vor `activation.generated_at` liegen. Die Aktivierungszeit muss vor beiden Upgradefenstern liegen, und das Rollbackfenster der zuerst aktualisierten Zelle muss geschlossen sein, bevor das Upgrade der zweiten Zelle beginnt.

Zusätzlich werden beide Transportrichtungen und die gemeinsame Out-of-band-Paarung als gegenseitige Belege erfasst. Fehlende, redigierte oder formal ungültige Receipts blockieren den Modus `activation`.

## Sichere Vorbereitung

1. Beide Betreiber legen getrennte Zellidentitäten, Schlüssel, Domains, TLS-Verantwortung und Backupziele fest.
2. Die öffentlichen Identitäten und Peerbindungen werden über einen getrennten Kanal verglichen.
3. Jede Seite erzeugt ihre lokalen Runtime-, Egress-, Recovery- und Rollbackbelege.
4. Beide Seiten tragen dieselben Release-Digests, Peerwerte und gegenseitigen Belegbindungen in ein gemeinsames Aktivierungsdokument ein.
5. Der Vertrag bindet den exakten SHA-256 von `cell-profile.contract.json`; der exakte SHA-256 von `two-operator-pilot.contract.json` wird im Aktivierungsdokument als `contract_sha256` gebunden.
6. Restore-Zeitpunkte, Dokumenterzeugung, Upgradefenster und Rollbackfristen werden in dieser Reihenfolge festgelegt.
7. Ein vollständig grüner Validierungslauf erlaubt nur die Weitergabe an die externe Receipt-, Trust- und Replay-Prüfung; er erlaubt selbst keine Aktivierung.

Eine fehlgeschlagene oder unklare Prüfung gilt als nicht erfolgt. Ein veralteter Vertrags-Digest, eine asymmetrische Peerdefinition, ein geändertes Image oder ein fehlender Restore-/Rollbackbeleg blockiert die strukturelle Vorprüfung.

## Rücknahme

Die erste technische Rücknahme bleibt `FEDERATION_DELIVERY_ENABLED=false` auf beiden Seiten. Danach werden Peerzustände blockiert, offene Lieferzustände erhalten und die Ursachen anhand der gebundenen Receipts untersucht. Schlüssel, Outbox- und Deliverytabellen werden nicht als Rollbackmaßnahme gelöscht.

Das Aktivierungsdokument bleibt als revisionsgebundener Nachweis erhalten. Eine erneute Aktivierung benötigt einen neuen, extern verifizierten gemeinsamen Freigabebeleg und einen unverbrauchten Ledger-Eintrag und muss bei Vertrags-, Commit-, Image-, Schlüssel-, Endpoint- oder Betriebsänderungen vollständig neu validiert werden.

## Nichtaussagen

Der Vertrag und sein grüner Repository-Test belegen ausdrücklich nicht:

- dass ein realer Zwei-Betreiber-WAN-Pilot bereits gelaufen ist;
- dass `weltgewebe.net` auf Kubernetes umgeschaltet wurde;
- dass physisch getrennte Failure-Domains oder Multi-Region-HA bestehen;
- dass Self-Service, eine GewebeZelle-API, CRD oder ein Operator existieren;
- dass DNS, TLS, Backups oder externe Betreiberbelege ohne realen Readback wahr sind.

Der nächste reale Schritt ist ein zeitlich begrenzter Pilot mit zwei tatsächlich unabhängigen Betreibern und autoritativen Readbacks auf beiden Seiten.
