---
id: security
title: Security Architecture
summary: Aktuelle Vertrauensgrenzen, Schutzmechanismen und offene Sicherheitsannahmen.
role: norm
organ: governance
status: canonical
last_reviewed: 2026-07-11
depends_on: []
relations:
  - type: relates_to
    target: docs/specs/auth-api.md
  - type: relates_to
    target: docs/deploy/vps.md
  - type: relates_to
    target: runtime/README.md
verifies_with: []
---

# Security Architecture

## Schutzobjekte

- Sitzungen und Login-Tokens
- Passkey-Credentials und WebAuthn-Identitäten
- reale Accountpositionen und private Accountfelder
- SMTP-, Datenbank- und Signatursecrets
- administrative Mutationen an Accounts, Knoten und Fäden
- Herkunft der Client-IP für Ratelimits und Auditierung
- Integrität von Migrationen und Deploymentkonfiguration

## Vertrauensgrenzen

### Browser

Der Browser erhält eine HTTP-only-Sitzung über Cookies. Der Authzustand wird beim
Laden über `/api/auth/me` wiederhergestellt. Bearer-Tokens werden nicht im
Webspeicher abgelegt.

Sitzungscookies verwenden einen gemeinsamen Scope und werden bei Logout
profilweit gelöscht. Mutierende Cookie-Requests unterliegen dem CSRF-Vertrag der
API. Notwendige Sitzungscookies sind erlaubt; Tracking- oder Werbecookies sind
nicht Teil des Systems.

### Caddy und API

Im öffentlichen beziehungsweise proxied Betrieb ist Caddy die vertrauenswürdige
Proxygrenze:

- eingehende fremde `Forwarded`-Header werden entfernt,
- `X-Forwarded-For` wird aus der tatsächlichen Remote-Adresse neu gesetzt,
- die API akzeptiert Proxyheader nur aus ausdrücklich konfigurierten Netzen,
- aktive IP-Ratelimits erfordern eine explizite Proxyentscheidung,
- direkter Betrieb wird mit `AUTH_TRUSTED_PROXIES=none` erklärt.

Ein alternativer Proxy muss denselben Überschreibungs- und
Headerbereinigungsvertrag erfüllen.

### API und Persistenz

PostgreSQL-Schreibpfade dürfen nicht mit einer JSONL-Lesequelle kombiniert
werden. Die Konfiguration verweigert den Start, wenn persistierte Änderungen
nach einem Neustart unsichtbar würden. Es gibt keinen stillen Fallback von
PostgreSQL zu JSONL.

Öffentliche Accountprojektionen dürfen private Standortkoordinaten nicht direkt
ausgeben. Die Trennung zwischen `public_payload`, `private_payload` und
Standortfeldern ist eine Sicherheitsgrenze, keine bloße Darstellungsfrage.

### Secrets

Secrets gehören weder in Git, PR-Kommentare, Chat noch rohe Diagnoseausgaben.
Betriebsprüfungen dürfen nur Vorhandensein, Quelle, Berechtigung und redigierte
Fingerprints belegen. Rotation und Injection sind privilegierte, separat
auditierte Vorgänge.

## Authentifizierungsflächen

| Fläche | aktueller Schutz |
|---|---|
| Magic Link | kurzlebiger Token, neuester Loginversuch maßgeblich, keine Tokenlogs im Produktionsvertrag |
| Passkey | WebAuthn-Origin/RP-Vertrag, Credential-Duplikatschutz, opt-in Persistenzpfad |
| Session | Serverzustand, Ablaufzeit, Device-ID, persistenter Cookie mit Sicherheitsabstand |
| Step-up | eigener kurzlebiger Nachweis für sensible Accountänderungen |
| Logout | Sessionentfernung und Cookie-Löschung mit identischem Scope |
| Ratelimit | IP-basiert und nur mit geklärter Proxyvertrauensgrenze startfähig |

## Deployment- und Lieferkettengrenzen

- Images, Actions und Werkzeuge sollen versions- oder digestgebunden sein.
- Datenbankmigrationen sind kein Nebeneffekt eines beliebigen Smokes.
- `WELTGEWEBE_API_STARTUP_MIGRATIONS` legt fest, ob angewendet, nur verifiziert
  oder bewusst übersprungen wird.
- Der kanonische Deploypfad ist `scripts/weltgewebe-up`; zielbezogene Shims
  delegieren dorthin.
- Mergefähigkeit erfordert grünes CI, aktuelle Headbindung und ein
  risikogewichtetes Selbstreview. Externe Modellreviews sind kein Pflichtbeleg.

## Offene Risiken

- Legacy-RoN-Daten werden privacy-sicher zu `not_on_map` normalisiert. Vor der
  späteren Entfernung der nullable Rollbackspalte `mode` ist ein Produktions-
  und Rückrollbeleg nötig.
- Der vollständige PostgreSQL-Cutover ist nicht abgeschlossen.
- Branch-/Ruleset-Schutz muss nach Stabilisierung der Pflichtcheckliste aktiv
  und minimal gehalten werden.
- Vorschauplattformen können extern scheitern; ihre Rolle muss von der
  Produktionsroutingwahrheit getrennt bleiben.

## Keine Sicherheitsbehauptung ohne Beleg

Dieses Dokument beschreibt den Vertrag im Repository. Es behauptet nicht, dass
eine konkrete Runtime aktuell gesund, ein Secret rotiert oder ein Provider
korrekt konfiguriert ist. Dafür sind frische Runtime-, CI- und Betriebsbelege
nötig.
