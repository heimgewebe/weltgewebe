---
id: deploy.domain-mail-migration-ionos-inwx-mailbox-brevo
title: "Architektur & Historie: Domain-/Mail-Migration IONOS zu INWX"
doc_type: reference
status: active
summary: >
  Aktuelle Providerarchitektur sowie historische Referenz des abgeschlossenen
  IONOS-zu-INWX-Cutovers für weltgewebe.net.
relations:
  - type: relates_to
    target: docs/deploy/README.md
  - type: relates_to
    target: docs/deploy/DRIFT_POLICY.md
  - type: relates_to
    target: docs/deployment.md
  - type: relates_to
    target: docs/deployment_governance.md
  - type: relates_to
    target: docs/runbooks/domain-mail-cutover.md
  - type: relates_to
    target: docs/runbooks/ops.runbook.weltgewebe-selfhost-deploy.md
  - type: relates_to
    target: docs/adr/ADR-0008__domain-mail-provider-boundaries.md
---

# Domain- und Providerarchitektur

## 1. Erreichter Zustand

Der Registrar-/DNS-Cutover für `weltgewebe.net` ist abgeschlossen. INWX ist Registrar aller drei Domains und autoritativer DNS-Provider für `weltgewebe.net`. Die IONOS-Verträge sind gekündigt. Bis zum noch offenen DNS-Cutover verweisen `weltweb.net` und `weltweberei.org` weiterhin auf alte UI-DNS-/IONOS-Nameserver.

Die IONOS-Kündigung wurde nach menschlicher Freigabe durchgeführt. Ein reproduzierbarer 48-Stunden-Nachweis ist nicht Bestandteil dieses Repository-Artefakts.

## 2. Domainrollen

### weltgewebe.net

- **Registrar:** INWX
- **Autoritative DNS-Verwaltung:** INWX
- **Web/API:** Die öffentlichen A-Records für Apex, `www` und `api` werden dynamisch durch den Heimberry-DDNS-Dienst gepflegt. Keine statische WAN-IP ist kanonische Repository-Wahrheit.

### weltweb.net

- **Registrar:** INWX
- **Autoritative DNS-Verwaltung:** Die Domain ist weiterhin an alte UI-DNS-/IONOS-Nameserver delegiert. INWX ist für diese Domain noch nicht autoritativ. Es existiert noch kein belegter öffentlicher Zielzustand.
- **Ziel:** INWX-Delegation; permanente Weiterleitung auf `https://weltgewebe.net` (Pfad und Query nach Möglichkeit erhalten); defensive No-Mail-Records; HTTPS-Nachweis.

### weltweberei.org

- **Registrar:** INWX
- **Autoritative DNS-Verwaltung:** Die Domain ist weiterhin an alte UI-DNS-/IONOS-Nameserver delegiert. INWX ist für diese Domain noch nicht autoritativ. Es existiert noch kein belegter öffentlicher Zielzustand.
- **Ziel:** INWX-Delegation; eigenständige Informationsseite; defensive No-Mail-Records; HTTPS-Nachweis. Die frühere WordPress-/IONOS-Fläche ist kein zu erhaltender Zielzustand.

## 3. Mailrollen

- **mailbox.org:** `kontakt@weltgewebe.net` (menschliche Inbound/Outbound-Mail). Betriebsfähig und belegt.
- **Brevo:** `noreply@login.weltgewebe.net` (technische Magic-Link-Mail). Betriebsfähig und belegt.

## 4. DNS- und DDNS-Prinzip

Die Produktions-Runtime erfordert keine statische WAN-IP. Das Routing erfolgt primär über DDNS für `weltgewebe.net`. Die öffentliche URL der Anwendung wird zusätzlich in `docs/deploy/public-app-base-url.md` vertraglich geregelt.

### Implementierungsbesitz

Dieses Repository besitzt den öffentlichen Vertrag, nicht die Heimberry-Implementierung. Der Implementierungsbesitzer ist das Repository `heimgewebe/heimserver`. Dort liegen die kanonischen Pfade:

- `scripts/heimberry/weltgewebe_ddns.py` – fail-closed Reconciliation-Client,
- `scripts/heimberry/install_weltgewebe_ddns.sh` – Installation, read-only Driftprüfung und explizite Aktivierung,
- `ops/systemd/weltgewebe-ddns.service` und `ops/systemd/weltgewebe-ddns.timer` – Laufzeitsteuerung,
- `runbooks/weltgewebe-dyndns.md` – Betrieb, Diagnose und Rollback.

Die öffentliche Host-Allowlist ist exakt:

- `weltgewebe.net`,
- `www.weltgewebe.net`,
- `api.weltgewebe.net`.

Weitere öffentliche DynDNS-Hosts, Wildcards oder eine statische WAN-IP benötigen eine neue Architekturentscheidung. Credentials und installierter Runtime-Zustand gehören nicht in dieses Repository.

### Beweisgrenze

Ein grüner Repository-Test im Implementierungsrepo beweist Quellcode, Installervertrag und deterministische Gegenwelten. Er beweist weder, dass Heimberry bereits aktualisiert wurde, noch dass DNS, Edge und Anwendung live den Zielzustand erfüllen.

Ein vollständiger Runtime-Nachweis erfordert separat:

1. installierte Programm- und Unit-Dateien stimmen mit einem exakten gemergten `heimserver`-Commit überein,
2. Service und Timer besitzen den erwarteten Zustand,
3. alle drei autoritativen INWX-Nameserver liefern für alle drei erlaubten Hosts den erwarteten einzelnen A-Record,
4. öffentliches HTTPS antwortet für Apex, `www` und `api`,
5. der kanonische API-Health-Pfad antwortet erfolgreich,
6. Heimberry besitzt keinen eingehenden öffentlichen DDNS-Dienst und App-, Admin- oder Datenbankports sind nicht direkt exponiert.

Live-Aktivierung erfolgt erst nach Review und Merge des Implementierungscommits. Ein PR, ein Merge-Dump oder ein erfolgreicher Health-Bericht ersetzt diesen Runtime-Nachweis nicht.

## 5. Wiederherstellungsgrenze

Ein IONOS-Rollback ist nicht mehr verfügbar.
Wiederherstellung erfolgt durch Korrektur der INWX-Zone, der DDNS-Konfiguration oder der aktuellen Runtime.

## 6. Offener Restbestand

Die Nebendomains `weltweb.net` und `weltweberei.org` besitzen aktuell keinen belegten DNS-/Web-/No-Mail-Endzustand. Ihre endgültige Delegation an INWX sowie die Einrichtung der Weiterleitungs- bzw. Informationsdienste ist Teil des ausstehenden Task-Restbestands.

## 7. Historische Einordnung

Die frühere IONOS→INWX-Migration ist abgeschlossen. Detaillierte damalige Phasen, Aktivierungsfenster und Rollbackannahmen sind nicht mehr operativ und bleiben ausschließlich über die Git-Historie nachvollziehbar.
