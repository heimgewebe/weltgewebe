---
id: specs.ortsweberei-webgemeindezentrum
title: Ortsweberei und Webgemeindezentrum
summary: Kanonischer Produktvertrag für die lokale Gemeinschaft als Gewebezelle und ihr genau einmal vorhandenes, bewusst verortetes Webgemeindezentrum.
doc_type: specification
status: canonical
canonicality: normative
lifecycle_state: active
role: norm
organ: product-domain
owner: product-domain
last_reviewed: 2026-08-02
review_after: 2026-11-02
depends_on:
  - specs.garnrolle-knoten-faden
  - specs.governance-antraege
relations:
  - type: relates_to
    target: docs/adr/ADR-0011__foederierte-gewebezellen.md
  - type: relates_to
    target: docs/adr/ADR-0015__ortsweberei-gewebezelle-webgemeindezentrum.md
  - type: relates_to
    target: docs/specs/map-experience.md
verifies_with: []
---

# Ortsweberei und Webgemeindezentrum

## Grundsatz

Eine Ortsweberei ist die lokale Gemeinschaft des Weltgewebes. Sie bildet
logisch genau eine Gewebezelle und besitzt genau ein aktives
Webgemeindezentrum. Das Zentrum verbindet die digitale Ortsweberei mit einem
bewusst gewählten Ort auf der Karte, an dem sich die Gemeinschaft treffen kann
oder künftig treffen möchte.

Diese Eins-zu-eins-Regeln sind Fachregeln, keine Behauptung über Serverzahlen:
Ein gemeinsamer Betreiber darf mehrere voneinander getrennte Gewebezellen
hosten. Umgekehrt bleibt die Identität einer Ortsweberei stabil, wenn ihre Zelle
später den Betreiber wechselt.

## Verantwortungen

| Begriff | Verantwortung |
|---|---|
| Ortsweberei | Gemeinschaft, Mitgliedschaft, Regeln, Entscheidungen und gemeinsame Mittel |
| Gewebezelle | Primärwahrheit, Daten- und Governance-Grenze, Föderationsidentität und Betrieb |
| Webgemeindezentrum | Kartenanker, öffentlicher Zugang, Treffort und Einstieg in die lokale Selbstverwaltung |

Webrat, Gewebekonto, örtlicher Gesprächsraum und lokale Vorhaben gehören zur
Ortsweberei. Sie sind über das Zentrum erreichbar, aber nicht automatisch
weitere geographische Mittelpunkte.

## Invarianten

Für den produktiven Datenpfad gelten später serverseitig, nicht nur in der
Benutzeroberfläche:

1. Jede aktive Ortsweberei besitzt genau eine stabile Gewebezellen-ID.
2. Jede aktive Ortsweberei besitzt genau ein aktives Webgemeindezentrum.
3. Ein aktives Zentrum gehört genau einer Ortsweberei und ihrer Gewebezelle.
4. Der aktive Zentrumspunkt liegt an einem bewusst beschlossenen Ort und wird
   nicht aus einem Gebiets- oder Mitglieder-Mittelwert geraten.
5. Ein Standortwechsel erhält Zentrum-ID, Ortsweberei-ID, Gewebezellen-ID,
   URLs und Chronik.
6. Eine Auflösung archiviert Ortsweberei und Zentrum gemeinsam; sie hinterlässt
   keine aktive Ortsweberei ohne Zentrum.
7. Anträge und andere lokale Governance-Objekte nennen ihre zuständige
   Ortsweberei eindeutig.

## Standortzustände

Der aktive Standort besitzt genau einen öffentlich verständlichen Zustand:

- `desired`: gewünschter Treffort; Nutzung noch nicht bestätigt;
- `provisional`: vorläufig nutzbarer Treffort;
- `confirmed`: regelmäßige Nutzung und Zugänglichkeit sind geklärt;
- `unavailable`: Zentrum bleibt Orientierungsanker, ist derzeit aber nicht als
  Treffort nutzbar;
- `relocation_proposed`: ein Ersatzstandort befindet sich im
  Entscheidungsverfahren.

Die Oberfläche übersetzt diese technischen Werte in verständliche deutsche
Bezeichnungen. Sie darf `desired` oder `provisional` nicht als bestätigte
öffentliche Zugänglichkeit ausgeben.

## Standortwahl und Datenschutz

Bevorzugt wird ein real zugänglicher Gemeinschaftsort, etwa eine Bibliothek,
ein Kulturzentrum, ein Gemeinschaftsraum, ein kooperierender Betrieb oder ein
öffentlicher Platz. Ist noch kein Raum gesichert, darf die Ortsweberei einen
gewünschten Treffort markieren und diesen Status offen benennen.

Eine Privatwohnung darf nur veröffentlicht werden, wenn der betroffene
Bewohner ausdrücklich zustimmt und Zugangszeiten sowie Bedingungen öffentlich
angegeben werden. Ohne diese Voraussetzungen wird ein anderer öffentlicher oder
hinreichend ungenauer Ort gewählt. Das System darf eine private Adresse nicht
automatisch aus Account- oder Garnrollendaten übernehmen.

## Kartenvertrag

Das Webgemeindezentrum ist ein eigener typisierter Strukturknoten. Es ist kein
gewöhnliches Angebot, kein persönlicher Accountmarker und kein zeitlich
verblassender Aktivitätsfaden.

Die normale Kartenansicht zeigt mindestens:

- Name der Ortsweberei;
- Standortzustand;
- Einstieg in Übersicht, Zusammenkommen und Webrat;
- dringende lokale Entscheidungen oder den nächsten öffentlichen Termin nur in
  einer kompakten, nicht überladenden Form.

Bei kleinen Zoomstufen dürfen Zentren gebündelt werden. Bei Auswahl bleibt die
Zentrum-ID der Fokus; Detailbereiche werden im Kontextpanel geöffnet. Die
Basiskarte enthält das Zentrum nicht als eingebranntes Kartenmerkmal, sondern es
bleibt eine Weltgewebe-Domänenentität.

## Zentrumoberfläche

Das Fokuspanel gliedert sich schrittweise in:

1. **Übersicht:** Beschreibung, Gebiet, Standortzustand und wichtige lokale
   Aktivitäten;
2. **Zusammenkommen:** Treffzeiten, Zugang, Barrierefreiheit, Weg und Termine;
3. **Webrat:** Anträge, Einspruchsfristen, Abstimmungen, Entscheidungen und
   Delegationen;
4. **Gewebe:** örtliche Knoten, Ressourcen, Vorhaben und Bedarfe;
5. **Gewebekonto:** Bestand, Einnahmen, beschlossene Ausgaben und
   Nachvollziehbarkeit.

Nicht implementierte Bereiche werden nicht als funktionsfähige Schaltflächen
simuliert.

## Governance und Verortung

Die Gründung einer Ortsweberei legt fachlich gemeinsam an:

- Ortsweberei;
- stabile Gewebezellen-Identität;
- vorläufiges oder gewünschtes Webgemeindezentrum;
- lokalen Webrat und Gesprächsraum.

Ein Umzug des Zentrums ist eine nachvollziehbare Governance-Entscheidung. Der
alte und der vorgeschlagene Ort werden im Verfahren klar unterschieden. Erst
die angenommene Entscheidung ändert die aktive Kartenposition; der frühere Ort
bleibt in der Chronik nachvollziehbar.

Ein Weberantrag und spätere Sachanträge sind über den Webrat der zuständigen
Ortsweberei auffindbar. Bezieht sich ein Sachantrag zusätzlich auf einen
konkreten Knoten, darf derselbe Antrag auch von dort aus erreichbar sein. Es
entsteht dabei kein zweiter Antrag.

## Fäden

Antragstellung, Veto, Stimme, Gesprächsbeitrag und Verfahrensphase bleiben
Governance-Datensätze. Sie werden auf der Antragsseite nicht als dekorative
Fadenbündel gezeichnet.

Eine spätere Governance-Linse darf nur ausdrücklich spezifizierte Beziehungen
zeigen, deren typisierte Endpunkte und auslösende Handlung belegt sind. Zähler,
Kategorien und Nullwerte sind keine Fäden. Eine UI-Projektion darf keine
`domain_edges` erzeugen oder eine fehlende Domainbeziehung vortäuschen.

## Ereignisse und Chronik

Die spätere Runtime soll mindestens folgende Ereignisse unterscheiden:

- Ortsweberei angelegt;
- Gewebezellen-Identität zugewiesen;
- Webgemeindezentrum verortet;
- Standort vorgeschlagen;
- Standort bestätigt;
- Zentrum verlegt;
- Treffort vorübergehend nicht verfügbar;
- Ortsweberei und Zentrum archiviert.

Die Ereignisnamen im Code dürfen technisch anders heißen. Ihre fachlichen
Bedeutungen und Übergänge müssen jedoch eindeutig bleiben.

## Einführungsgrenze

Die sofortige UX-Korrektur entfernt das synthetische Antragsgewebe und ersetzt
es durch eine Prozessanzeige. Sie führt noch keine Ortsweberei- oder
Zentrum-Datensätze ein.

Für die produktive Kartenverankerung fehlen derzeit ein kanonischer
Ortsweberei-Datensatz, der beschlossene Standort der ersten Ortsweberei sowie
die serverseitigen Eindeutigkeits- und Migrationspfade. Diese Lücke darf nicht
durch eine im Client erfundene Standard-Ortsweberei oder einen geratenen
Kartenpunkt verdeckt werden.

## Abnahmekriterien für die Runtime

Die spätere Runtime-Einführung ist erst abgeschlossen, wenn:

- Datenbank und API die Eins-zu-eins-Invarianten erzwingen;
- eine Ortsweberei nicht ohne Zentrum aktiviert werden kann;
- Standortstatus und tatsächliche Zugänglichkeit getrennt sichtbar sind;
- keine Privatadresse automatisch veröffentlicht wird;
- Zentrum, Ortsweberei und Gewebezelle stabile Identitäten besitzen;
- Governance-Objekte eindeutig der zuständigen Ortsweberei zugeordnet sind;
- Standortwechsel chronologisch nachvollziehbar sind;
- Karte, Mobilansicht, Tastatur und Bildschirmleser unterstützt werden;
- eine spätere technische Verselbständigung der Gewebezelle keine neuen
  fachlichen IDs verlangt.
