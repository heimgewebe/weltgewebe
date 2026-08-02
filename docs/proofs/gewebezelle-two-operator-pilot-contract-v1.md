---
id: proof.gewebezelle-two-operator-pilot-contract-v1
title: Beweisgrenze Zwei-Betreiber-GewebeZelle-Pilotvertrag v1
doc_type: proof
status: active
summary: >
  Dokumentiert die statisch und testseitig belegte Vertragsgrenze für einen späteren Zwei-Betreiber-Piloten und trennt sie von noch fehlender WAN- und Produktionswahrheit.
relations:
  - type: depends_on
    target: platform/cell-pilot/two-operator-pilot.contract.json
  - type: depends_on
    target: platform/cell-pilot/two-operator-pilot.example.invalid.json
  - type: depends_on
    target: scripts/platform/validate_two_operator_pilot.py
  - type: depends_on
    target: scripts/ci/tests/test_two_operator_cell_pilot.py
  - type: relates_to
    target: docs/runbooks/gewebezelle-two-operator-pilot-v1.md
  - type: relates_to
    target: docs/proofs/weltgewebe-os-v1-t032-federation-delivery.md
  - type: relates_to
    target: docs/tasks/board.md
---

# Beweisgrenze Zwei-Betreiber-GewebeZelle-Pilotvertrag v1

## Belegter Stand

Der Repository-Stand enthält einen kanonischen, versionierten Zwei-Betreiber-Strukturvertrag, ein absichtlich nicht aktivierbares Beispiel und einen deterministischen Validator ohne Netzwerkzugriffe. Auch ein vollständiges `activation`-Dokument bleibt statisch `activatable: false`. Die Plattformprüfung bindet diese Artefakte an den allgemeinen GewebeZelle-Vertrag.

Statisch belegt sind:

- exakt zwei Zellen und zwei voneinander verschiedene Betreiberidentitäten;
- unterschiedliche Zell-IDs, HTTPS-Endpoints, aktive Key-IDs, Ed25519-Public-Keys und Backupziele mit verschiedenen DNS-Autoritäten;
- wechselseitig exakte Peer-, Key- und Ereignisbindung;
- Parität zwischen Peer-Endpoint und Cilium-FQDN-Egress auf TCP 443;
- Ausschluss von IP-Literalen, URL-Zugangsdaten, Querys, Fragmenten, Pfaden, Wildcards, `world` und CIDR-Egress;
- gemeinsamer Git-Commit und gemeinsame API-/Web-Image-Digests;
- konkrete DNS-, TLS-, Backup-, Restore-, SLO-, Alarm-, Upgrade- und Rollbackverantwortung mit getrennten Alarmrouten, Alarm vor der Delivery-Lag-SLO-Verletzung und Availability-Burn-Alarm;
- gegenseitige Out-of-band-Verifikation durch den jeweils anderen Betreiber;
- exakte Bindung des Aktivierungsdokuments an den SHA-256 des kanonischen Vertrags und mittelbar an den SHA-256 des allgemeinen Zellprofils;
- vollständige, nicht redigierte Receipt-Digests als Voraussetzung der strukturellen Prüfung des Modus `activation`;
- dauerhafte Nichtaktivierbarkeit der öffentlichen `.invalid`-Vorlage;
- Ablehnung doppelter oder nicht endlicher JSON-Werte, wiederverwendeter Receipts an beliebiger Stelle, gemeinsamer Backup-Autoritäten sowie einer Zeitachse, in der Restore oder Aktivierung zu spät liegen;

## Negativbeweise

Die Tests verändern jeweils eine kritische Invariante und verlangen ein fail-closed Ergebnis. Abgedeckt sind mindestens:

- identische Zell-, Betreiber-, Kontroll-, Key-, Backup- oder Alarmidentitäten sowie Zellhosts außerhalb der gebundenen Kontrolldomain;
- asymmetrische Peer-ID, Endpoint-, Key-ID- oder Public-Key-Bindung;
- reduzierte Ereignis-Whitelist;
- Endpoint-/Egress-Abweichung sowie breite Egressfreigaben;
- HTTP, IP-Literal, Zugangsdaten, Query, Fragment, Pfad oder abweichender Port;
- reservierte Beispieldomains im Aktivierungsmodus;
- Commit- und Image-Digest-Drift;
- veralteter Vertrags-Digest, fehlende Zustimmung oder unvollständige gemeinsame Freigabe;
- fehlender Restore-/Rollbackbeleg, falscher Restore-Commit, innerhalb desselben Dokuments wiederverwendete Receipts, Restore nach Dokumenterzeugung, Aktivierung nach Beginn eines Upgradefensters oder ungültige beziehungsweise überlappende Rollbackfenster;
- Selbstverifikation oder ein nicht zugelassener Verifikationskanal;
- geheime oder private Schlüsselfelder an beliebiger Stelle;
- doppelte JSON-Schlüssel, nicht endliche JSON-Zahlen, Vertrags-/Profil-Digestdrift, identische Alarmrouten, verspätete Alarme oder deaktivierter Burn-Rate-Alarm;
- konkrete Receipts im öffentlichen Beispiel sowie Aktivierungsversuche mit dem Beispiel.

## CI- und Plattformbindung

`make cell-pilot-check` validiert die öffentliche Vorlage und führt die gezielten Tests aus. `make platform-check` hängt von diesem Ziel ab. Zusätzlich ruft `scripts/platform/validate_platform.py` den Validator auf und verlangt ausdrücklich `activatable: false` für die Repository-Vorlage. Der Kubernetes-PR-Workflow kompiliert Validator und Plattformwerkzeuge und führt die neue Testsuite zusammen mit den bestehenden Plattform- und HA-Verträgen aus.

## Nicht belegter Stand

Diese Evidenz ist ein **Vertragsbeweis**, kein Laufzeit- oder WAN-Beweis. Sie belegt nicht:

- einen tatsächlich ausgeführten Austausch zwischen zwei extern betriebenen Zellen;
- reale DNS-, TLS-, Backup-, Restore- oder Alarm-Readbacks;
- physisch getrennte Betreiber- und Failure-Domains;
- eine produktionsnahe Last-, Störungs- oder Recovery-Messung über das Internet;
- den Kubernetes-Staging- oder Produktionscutover aus `WELTGEWEBE-OS-V1-T044`;
- einen Operator, eine CRD, eine Provisionierungs-API oder Self-Service.

Ein späterer Aktivierungskandidat darf erst nach der statischen Vorprüfung als Aktivierungsbeleg gelten, wenn die referenzierten Receipt-Artefakte außerhalb der Dokumentbehauptung autoritativ gelesen, neu gehasht, claimgebunden gegen unabhängige Trust-Anker geprüft, den realen Betreiber- und Failure-Domains zugeordnet und in einem autoritativen Replay-Ledger als unverbraucht registriert wurden.

## Nächster Beweisschritt

Der nächste Schritt ist ein begrenzter Zwei-Betreiber-WAN-Pilot mit getrennten Domains, TLS-Zertifikaten, Datenbanken, Schlüsseln, Backupzielen und Betriebsverantwortungen. Dabei müssen beide Richtungen, Retry, Duplicate, Concurrency, Egress, Restore und Rollback auf denselben Commit- und Image-Digests gemessen und anschließend in einen strukturell validierten und extern verifizierten Aktivierungskandidaten gebunden werden. Erst danach kann aus realen Betriebsdaten ein standardisiertes Zellprofil oder später eine Operator-API abgeleitet werden.
