---
id: specs.garnrolle-knoten-faden
title: Garnrolle, Knoten und Faden
summary: Kanonischer Produktvertrag für Gastidentität, Garnrolle, Knoten, Webungsaktionen und daraus abgeleitete Fäden.
doc_type: specification
status: canonical
canonicality: normative
lifecycle_state: active
role: norm
organ: product-domain
owner: product-domain
last_reviewed: 2026-07-20
review_after: 2026-10-12
depends_on: []
relations:
  - type: relates_to
    target: docs/specs/governance-antraege.md
  - type: supersedes
    target: docs/konzepte/garnrolle-und-verortung.md
  - type: supersedes
    target: docs/specs/privacy-ui.md
  - type: relates_to
    target: docs/adr/ADR-0009__garnrolle-verortung-sichtbarkeit.md
  - type: relates_to
    target: docs/domain/vocabulary.md
verifies_with:
  - contracts/domain/account.schema.json
  - contracts/domain/node.schema.json
  - contracts/domain/edge.schema.json
  - apps/api/tests/api_governance_guards.rs
  - apps/api/tests/api_accounts.rs
  - apps/web/tests/garnrolle-self-service.spec.ts
  - apps/web/tests/komposition.spec.ts
---
# Garnrolle, Knoten und Faden

## Grundsatz

Jeder registrierte Account besitzt genau eine Garnrolle. Die Garnrolle ist der
persönliche Ausgangspunkt im Weltgewebe; die Berechtigungsrolle `gast`, `weber`
oder `admin` beschreibt dagegen, welche Verantwortung der Account übernehmen
darf. Sichtbarkeit und Kartenposition werden ausschließlich durch `map_state`
gesteuert.

Ein Account beginnt als `gast`. Gäste dürfen bereits weben: die eigene
Garnrolle beschreiben und verankern, Knoten knüpfen, zulässige Fäden auslösen
und in offenen Gesprächen mitreden. Der Weberstatus ist keine technische
Freischaltung der ersten Garnrolle, sondern die gemeinschaftlich bestätigte
Befugnis, auch fremde beziehungsweise gemeinschaftliche Inhalte zu pflegen.
Formale Veto- und Stimmrechte stehen ausschließlich Webern und Administratoren
bei fremden Weberanträgen zu; über den eigenen Antrag darf niemand selbst entscheiden.

## Rollen und Fähigkeiten

| Fähigkeit | Gast | Weber | Admin |
|---|---:|---:|---:|
| Eigene Garnrolle beschreiben und verankern | ja | ja | ja |
| Knoten knüpfen | ja | ja | ja |
| Eigenen Knoten bearbeiten oder entfernen | ja | ja | ja |
| Fremden oder eigentümerlosen Knoten pflegen | nein | ja | ja |
| In offenen Knoten- und Antragsgesprächen schreiben | ja | ja | ja |
| Eigenen Gesprächsbeitrag bearbeiten | ja | ja | ja |
| Veto und Stimme zu fremden Weberanträgen | nein | ja | ja |
| Moderativ fremde Beiträge entfernen | nein | nein | ja |

Nicht angemeldete Besucher dürfen öffentliche Inhalte lesen, aber keine
Webungsaktion ausführen.

## Garnrolle

Die Garnrolle ist der Account selbst. Es gibt weder einen zweiten
Garnrollen-Datensatz nach der Aufnahme als Weber noch einen getrennten
Gastmodus der Identität.

Jede neue Garnrolle beginnt datenschutzsicher mit:

```text
map_state = not_on_map
```

Der Account kann anschließend bewusst wählen:

- `not_on_map`: keine öffentliche Position;
- `exact`: ausdrücklich bestätigte genaue Position;
- `radius`: stabile, abgeleitete ungefähre Position innerhalb des gewählten
  Radius.

Nur der angemeldete Account darf sein Garnrollenprofil verändern. Interne
Positionen und private Projektionsbindungen erscheinen nie in öffentlichen
Antworten.

## Knoten

Knoten beschreiben Orte, Kollektivgüter, Ressourcen, Vorhaben, Bedürfnisse oder
Angebote. Jeder neu erzeugte Knoten erhält serverseitig eine unveränderliche
Urheberbindung:

```text
created_by_account_id = Account-ID der authentifizierten Sitzung
```

Der Client darf diese Bindung weder vorgeben noch ändern. Beim Ersetzen oder
Bearbeiten eines Knotens bleibt sie erhalten.

Für bestehende Knoten, deren Urheber historisch nicht belegt ist, wird keine
Urheberschaft erfunden. Sie besitzen keine `created_by_account_id`. Daraus folgt:

- Gäste dürfen solche Knoten nicht bearbeiten oder entfernen;
- Weber dürfen sie gemeinschaftlich pflegen;
- Administratoren behalten den moderativen Pfad.

Ein Gast darf einen vorhandenen Knoten nur verändern, wenn dessen gespeicherte
Urheberbindung exakt der Account-ID seiner aktuellen Sitzung entspricht. Diese
Prüfung erfolgt auf dem Server und gilt unabhängig von der sichtbaren
Oberfläche. Versionsvorbedingungen (`If-Match`) schützen zusätzlich gegen
überschriebene Paralleländerungen.

## Fäden

Fäden sind Beziehungen zwischen Garnrollen und Knoten. Der produktive
Webungsweg erzeugt sie serverseitig als Folge einer fachlichen Handlung, etwa
wenn ein angemeldeter Account einen Knoten knüpft. Ein Client darf dabei keine
fremde Garnrolle als handelnden Ausgangspunkt vortäuschen.

Dieser Schnitt eröffnet bewusst keinen allgemeinen manuellen
`POST /edges`-Editor. Ein solcher Editor benötigt einen eigenen Vertrag für
Fadenarten, Eigentum, Änderung, Entfernung und Missbrauchsschutz. Bis dahin
bleiben Fäden aus den belegten Webungsaktionen abgeleitete, öffentlich lesbare
Projektionen.

Freie interne Fadennotizen gehören nicht zur öffentlichen Projektion.

Fäden sind keine frei editierbaren Fachobjekte. Für abgeleitete Fadenprojektionen
gelten weiterhin diese harten Regeln:

1. Es gibt keinen allgemeinen öffentlichen `POST`, `PUT`, `PATCH` oder `DELETE`-Pfad,
   mit dem Clients beliebige Fäden als eigene Wahrheit erzeugen oder verändern.
2. Die Benutzeroberfläche bietet keinen unabhängigen Fadeneditor.
3. Der Server erzeugt oder repariert eine vorgesehene Projektion mit stabiler
   Operations-ID, damit Wiederholungen keine Doppelprojektionen erzeugen.
4. Aus der Projektion muss auf die belegte fachliche Webungsaktion zurückgeführt
   werden können.

Beim Knotenknüpfen erzeugt der Server nach der dauerhaften Knotenanlage den
zugehörigen Garnrolle-Knoten-Faden. Der Account-Lifecycle wird dabei vom Beginn
der Knotenpersistenz bis zum erfolgreichen Faden oder zur Kompensation
serialisiert. Schlägt die Projektion dauerhaft fehl, darf kein verwaister neuer
Knoten als erfolgreicher Gesamtvorgang zurückbleiben.

Anträge, Vetos, Abstimmungen und Gesprächsbeiträge bleiben eigene dauerhafte
Governance-Datensätze. Das Antragsgewebe auf der Informationsseite wird daraus
als reine Leseprojektion berechnet; es erzeugt keinen zweiten `domain_edges`-
Bestand. Da Anträge keinen geografischen Ort besitzen, erscheint diese Projektion
nicht auf der Karte. Exakte Aktionszahlen bleiben als Text erhalten; nur die Zahl
gleichzeitig gezeichneter paralleler Linien darf zur Renderbegrenzung gedeckelt
werden.

### Auflösung unverzwirnter Fäden

Jeder neu abgeleitete, unverzwirnte Faden besitzt ab seiner Entstehung eine
eigene Lebensdauer von exakt **168 Stunden**. Der Server setzt `expires_at`
ausschließlich aus dem servereigenen `created_at`; ein Client darf weder Beginn
noch Ende vorgeben.

1. Die sichtbare Stärke nimmt zwischen `created_at` und `expires_at` kontinuierlich
   und linear von vollständig sichtbar auf unsichtbar ab. Die Karte projiziert
   den Wert minütlich neu; die exakte Ablaufgrenze wird unabhängig davon terminiert.
2. Bei `now == expires_at` gehört der Faden nicht mehr zur aktiven Projektion.
   Listen, Einzelabrufe und Karte geben ihn dann nicht mehr aus.
3. Eine spätere Webungsaktion verlängert keinen bestehenden Faden. Sie erzeugt,
   sofern fachlich vorgesehen, eine neue Projektion mit eigener Uhr.
4. Die zugrunde liegende Webungsaktion und ihre Chronik bleiben dauerhaft
   erhalten. Aufgelöst wird nur die abgeleitete Fadenprojektion.
5. Bestehende Datensätze ohne `expires_at` bleiben aus Kompatibilitätsgründen
   sichtbar. Sie dürfen nicht durch eine rückwirkend geratene Ablaufzeit gelöscht
   werden.
6. Ein vorhandener, aber ungültiger oder nicht exakt 168 Stunden langer
   Ablaufvertrag wird in aktiven Projektionen fail-closed ausgeblendet.

Ein verzwirnter, dauerhafter Zusammenhang heißt **Garn** und ist vom Fadenverfall
ausgenommen. Die Verzwirnungsaktion und ihre technische Garnrepräsentation sind
nicht Bestandteil dieses Vertragsstands. Bis zu einer eigenen kanonischen
Spezifikation darf dafür weder ein öffentliches CRUD noch ein geratenes Edge-Feld
eingeführt werden. `expires_at = null` ist deshalb kein regulärer Erzeugungswert
für neue Fäden, sondern ausschließlich ein Legacy- und späterer expliziter
Garn-Kompatibilitätspfad.

## Gespräche

Jeder PostgreSQL-Knoten besitzt genau einen öffentlichen Gesprächsraum.
Angemeldete Gäste, Weber und Administratoren dürfen während des offenen
Lebenszyklus Beiträge verfassen. Ein Beitrag besitzt einen Autoren-Snapshot und
eine aktive Accountbindung:

- nur der Autor darf den eigenen Beitrag bearbeiten;
- Autor oder Administrator dürfen ihn entfernen;
- beim Löschen eines Accounts wird die aktive Accountbindung entfernt, der
  historische Anzeigename und der Beitrag bleiben erhalten.

## Aufnahme als Weber

Die Aufnahme folgt `docs/specs/governance-antraege.md`. Ein angenommener
Weberantrag ändert die Berechtigungsrolle von `gast` auf `weber`. Er erzeugt
keine neue Garnrolle und verändert weder Profil noch Kartenstatus, Position,
Urheberschaft eigener Knoten oder bisherige Gesprächsbeiträge.

Der zusätzliche Weberstatus verleiht die gemeinschaftliche Pflege fremder oder
historisch eigentümerloser Knoten sowie formale Veto- und Stimmrechte bei
fremden Weberanträgen.

## Gast-Austritt

Ein Gast darf den eigenen Account löschen. Der Austritt ist ein atomarer
PostgreSQL-Vorgang:

- eigene Weberanträge und deren abhängige Verfahrensdaten werden entfernt;
- Passkeys und Sitzungen werden entfernt;
- die Garnrolle wird entfernt;
- eigene, inzwischen gemeinschaftlich sichtbare Knoten bleiben bestehen und
  verlieren ihre aktive Urheberbindung;
- Fäden mit der gelöschten Garnrolle als Account-Endpunkt werden entfernt;
- Beiträge in fremden Anträgen und Knotengesprächen bleiben mit ihrem
  Anzeigenamen erhalten, verlieren aber die Account-ID;
- Vetos und Stimmen in fremden Weberverfahren bleiben als Verfahrensspur und
  für die Zählung erhalten, verlieren aber ebenfalls ihre aktive Account-ID.

Der Austritt ist nur verfügbar, wenn Accounts, Knoten und Fäden kanonisch in
PostgreSQL gelesen und geschrieben werden. Ein Mischbetrieb wird fail-closed
abgewiesen, damit keine Spuren in einer zweiten Datenquelle zurückbleiben.

## Typischer Ablauf

1. Registrierung erzeugt eine Gast-Garnrolle im Zustand `not_on_map`.
2. Der Gast beschreibt und verankert die eigene Garnrolle freiwillig.
3. Der Gast knüpft einen Knoten; der Server bindet dessen Urheberschaft an den
   Account und erzeugt die zulässigen abgeleiteten Fäden.
4. Der Gast kommuniziert in Knoten- und Antragsgesprächen.
5. Der Gast kann den Weberstatus beantragen.
6. Bei Annahme bleibt die gesamte bisherige Identität unverändert; nur die
   gemeinschaftlichen Pflege- und Entscheidungsrechte kommen hinzu.

## Nicht-Ziele dieses Schnitts

- kein allgemeiner manueller Fadeneditor;
- keine freie Übertragung von Knoten-Eigentum;
- keine automatische Beförderung nach Aktivität oder Zeit;
- keine Bearbeitung fremder Gesprächsbeiträge außer administrativer Entfernung;
- keine erfundene Urheberschaft für Altbestand.
