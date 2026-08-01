---
id: proofs.weltgewebe-os-v1-t032-federation-delivery
title: WELTGEWEBE-OS-V1-T032 — Automatische Föderationsauslieferung
summary: >
  Belegt den dauerhaften, begrenzten und multi-instanzsicheren Auslieferungspfad von der PostgreSQL-Outbox zu ausdrücklich freigegebenen Zielzellen sowie das erste manuelle GewebeZelle-Pilotprofil.
doc_type: report
status: active
owner_task: WELTGEWEBE-OS-V1-T032
review_after: 2026-09-30
relations:
  - type: depends_on
    target: docs/proofs/weltgewebe-os-v1-t005-two-cell-proof.md
  - type: verifies
    target: apps/api/src/federation_delivery.rs
  - type: verifies
    target: apps/api/migrations/20260731000002_federation_delivery_worker.up.sql
  - type: relates_to
    target: docs/runbooks/gewebezelle-manual-pilot.md
  - type: relates_to
    target: platform/cell-profile.contract.json
  - type: verifies
    target: platform/apps/weltgewebe/cell-pilot/federation-delivery-egress.yaml
---

# WELTGEWEBE-OS-V1-T032 — Automatische Föderationsauslieferung

## Ergebnis

Die im Zwei-Zellen-Pilot bislang manuell übertragene `federation_outbox` besitzt nun einen explizit aktivierbaren Produktionsworker. Er wählt ausschließlich vertrauenswürdige Peers mit gültigem HTTPS-Ziel, erlaubter Ereignisklasse und passender globaler oder nachbarschaftlicher Reichweite aus. Auslieferung, Wiederholung, Eigentumslease und Abschlusszustand werden in PostgreSQL dauerhaft geführt.

Der Schnitt aktiviert weder die heutige Weltgewebe-Produktion noch eine fremde Zelle. `FEDERATION_DELIVERY_ENABLED` bleibt in der gemeinsamen Plattformbasis standardmäßig `false`.

## Akzeptanzmatrix

| Kriterium | Umsetzung | Ergebnis |
| --- | --- | --- |
| Neue persistierte Outbox-Ereignisse reservieren erlaubte Ziele atomar und werden automatisch ausgeliefert | `apps/api/src/federation.rs`, `apps/api/src/federation_delivery.rs`, `federation_delivery_attempts` | bestanden |
| Timeouts, Retry, Backoff und dauerhafte Zustände | begrenzter Reqwest-Client, `pending/in_flight/retry/delivered/dead` | bestanden |
| Neustart- und Multi-Instance-Sicherheit | DB-Lease, abgelaufene Claims, `FOR UPDATE SKIP LOCKED` | bestanden |
| Peer-, Scope- und Zielrichtlinien bleiben fail-closed | Auswahl und erneuter Policy-Readback unter geteilter Peer-Sperre | bestanden |
| Idempotente Wiederholung | `Applied` und `Duplicate` schließen ab; derselbe Event-ID-/Digestvertrag bleibt erhalten | bestanden |
| Objektversionen bleiben geordnet | spätere Version wartet je Zielzelle auf alle früheren Versionen desselben Objekts | bestanden |
| Automatischer Zwei-Zellen-Beweis | PostgreSQL-Sender, automatischer Workertransport und unabhängige Empfangszelle | bestanden |
| Manuelles Betreiberprofil | `platform/cell-profile.contract.json`, Runbook und externer Secretpfad | vorhanden |
| Ausgehender Kubernetes-Netzpfad bleibt eng und aktivierbar | nicht eingebundenes Cilium-`toFQDNs`-Template, exakte Host-/Port-Aktivierung, kein `world`-Egress | bestanden |

## Laufzeitvertrag

Der Worker wird nur gestartet, wenn gleichzeitig gelten:

- eine vollständige Zellidentität einschließlich externer Signierschlüsselbereitstellung;
- PostgreSQL als gemeinsame autoritative Zustandsbasis;
- `FEDERATION_DELIVERY_ENABLED=true`;
- mindestens ein Peer mit validierter `https://`-`delivery_base_url`.

HTTP, Redirects, Zugangsdaten in URLs, Queryparameter und Fragmente werden abgewiesen. Erfolgsantworten müssen einen gültigen `ReceiveOutcome` mit exakt derselben Event-ID und Objektversion enthalten. Nur passende `Applied`- und `Duplicate`-Antworten gelten als bestätigt. `429` und `5xx` werden begrenzt wiederholt. Ablehnung, Quarantäne, fremde Bestätigungen, ungültige Erfolgsantworten, andere Protokollfehler und ausgeschöpfte Versuche werden als `dead` sichtbar erhalten. Nachträgliche Policy-Drift macht bestehende Zielzeilen nicht unclaimbar: Sie werden ohne Netzwerkzugriff als Policy-`dead` klassifiziert und nur durch eine spätere passende Policy-Fingerprint-Freigabe wieder auf `pending` gesetzt. Remote-Ablehnungen und erschöpfte Zustellungen bleiben terminal.

Zielreservierungen entstehen atomar mit dem lokalen Outbox-Eintrag. Bei erstmaliger Aktivierung oder Änderung eines Peer-Endpoints oder seines gebundenen Policy-Fingerprints reserviert eine einmalige transaktionale Rückfüllung die nach aktueller Peer-, Ereignis- und Reichweitenrichtlinie zulässige Geschichte. Der Worker pollt danach nur die begrenzte Deliverytabelle und kreuzt nicht bei jedem Lauf die vollständige historische Outbox mit allen Peers. Damit beginnt eine neue Zielzelle nicht bei einer unverifizierbaren Objektversion größer 1.

Für jeden Claim wird die Deliveryzeile exklusiv und die aktuelle Peerbeziehung geteilt gesperrt. Eine Blockierung oder Endpointänderung kann daher vollständig vor oder nach einer einzelnen begrenzten HTTP-Zustellung wirksam werden, nicht unbemerkt mitten in ihr.

## PostgreSQL-Beweis

Ein eigener loopbackgebundener PostgreSQL-16-Wegwerfcontainer wurde ausschließlich für den Test erzeugt. Die realen Migrationen wurden auf eine leere Datenbank angewandt. Der Test hat anschließend belegt:

1. Ein simulierter transienter Netzwerkfehler erzeugt dauerhaft `retry`, Versuchszahl 1 und eine nicht sensible Fehlerklasse.
2. Ein späterer Worker übernimmt denselben Eintrag und erreicht `delivered`, Versuchszahl 2.
3. Zwei konkurrierende Worker verarbeiten denselben Zielzustand genau einmal.
4. Zwei Versionen derselben Objektadresse werden trotz paralleler Worker nicht vertauscht: Version 1 wird zuerst bestätigt, Version 2 bleibt zunächst `pending` und wird erst im folgenden Batch geliefert.
5. Die Zielzelle endet auf Objektversion 2 ohne Quarantäne oder stille Versionslücke.

Terminaler Testreceipt: `09bc06605ee5f278dca2e38f3127a8b47ecad9afa5389712d37e94cc2201f005`.

Der Wegwerfcontainer wurde anschließend entfernt. Cleanup-Receipt: `a8c630996a3e098b12c9d35edda6e23767ff19805e759dc52ecd8740ef431602`.

## Plattform- und Geheimnisgrenze

Das manuelle Pilotprofil ergänzt keine Secretwerte im Repository. Der private Ed25519-Seed ist als optionaler Schlüssel `federation-signing-key-b64` im extern bereitzustellenden Secret `weltgewebe-runtime` gebunden. Nicht geheime Zell- und Peerdaten bleiben versionsgebundene Konfiguration.

Die Kubernetes-Basis bleibt egress-default-deny. Ein nicht eingebundenes Cilium-FQDN-Template erlaubt ausschließlich einen absichtlich ungültigen Beispielhost auf TCP 443. Der Aktivierungsvertrag verlangt, dass das zelleigene Overlay diesen Platzhalter durch die exakten, unabhängig verifizierten Peer-DNS-Namen und Ports ersetzt; Wildcards, `toEntities: world` und pauschale CIDR-Freigaben bleiben verboten. Dadurch ist der Worker weder ohne Netzfreigabe funktionslos noch durch eine allgemeine Internetfreigabe unnötig weit berechtigt.

Das Profil ist ausdrücklich:

- manuell und GitOps-gebunden;
- nicht selbstbedienbar;
- ohne GewebeZelle-CRD, Plattform-API oder Kubernetes-Operator;
- ohne automatische Peer-Discovery oder Vertrauensbildung.

## Beweisgrenzen

Nicht belegt werden:

- ein produktiv aktivierter Dauerverbund zweier realer Betreiber;
- WAN-Verhalten über längere Ausfälle und reale Internetpfade;
- automatische Wiederaufnahme bewusst `dead` gesetzter Zustellungen;
- öffentliche Quarantäneverwaltung;
- Identitätsumzug zwischen Zellen;
- Self-Service-Provisionierung;
- Kubernetes-Produktion oder Multi-Region-HA.

Der nächste reale Erkenntnisschnitt ist ein revisionsgebundener Zwei-Betreiber-Pilot mit getrennten Domains, Schlüsseln, Backups, Upgradefenstern und Verantwortlichkeiten. Erst daraus dürfen stabile Zellprofile und später eine GewebeZelle-API oder ein Operator abgeleitet werden.
