---
id: specs.governance-antraege
title: Anträge, Konsent, Veto und Abstimmung
summary: Kanonischer Produkt- und Ausführungsvertrag für die allgemeine Antragsmechanik und die Aufnahme von Gästen als Weber.
doc_type: specification
status: canonical
canonicality: normative
lifecycle_state: active
role: norm
organ: governance
owner: governance
last_reviewed: 2026-07-20
review_after: 2026-10-12
depends_on:
  - specs.garnrolle-knoten-faden
relations:
  - type: relates_to
    target: docs/domain/vocabulary.md
verifies_with:
  - apps/api/tests/api_governance_guards.rs
  - apps/api/tests/db_governance.rs
  - apps/web/src/lib/api/governance.test.ts
  - apps/web/tests/governance.spec.ts
---

# Anträge, Konsent, Veto und Abstimmung

## Grundsatz

Alles, was im Weltgewebe gemeinschaftlich verändert werden kann, soll über
einen transparenten Antragsmechanismus disponibel sein. Jeder Antrag besitzt
eine Informationsseite, einen öffentlichen Gesprächsraum, eindeutige Fristen
und eine dauerhaft nachvollziehbare Zustandsfolge.

Der erste produktive Antragstyp ist der **Weberantrag**. Er überführt einen
mitwirkenden Gast nach gemeinschaftlicher Prüfung in den Weberstatus. Die
Garnrolle besteht bereits vorher; die Annahme verleiht zusätzliche Pflege- und
Entscheidungsrechte.

## Gast und Weber

Ein neu registrierter Account beginnt als `gast` und besitzt genau eine
Garnrolle.

Ein Gast darf:

- das gesamte öffentliche Weltgewebe ansehen, suchen und filtern;
- die eigene Garnrolle beschreiben und freiwillig verankern;
- Knoten knüpfen und eigene Knoten pflegen;
- zulässige, serverseitig abgeleitete Fäden auslösen;
- in offenen Knoten- und Antragsgesprächen mitreden;
- den eigenen Weberstatus beantragen;
- den eigenen Gastaccount auflösen.

Ein Gast darf keine fremden oder historisch eigentümerlosen Knoten bearbeiten.
Formale Vetos und Abstimmungen sind Webern und Administratoren vorbehalten.
Über den eigenen Weberantrag darf der Antragsteller auch nach einem möglichen
Rollenwechsel nicht selbst entscheiden; diese Selbstentscheidungsgrenze gilt
rollenunabhängig.

Die Zahl eigener Gastknoten ist pro Account begrenzt. Der Betriebsstandard liegt
bei 1.000 Knoten und kann über `MAX_GUEST_OWNED_NODES` als positive Ganzzahl
enger oder weiter gefasst werden. Die Grenze wird serverseitig und bei
PostgreSQL unter dem Account-Lock geprüft; ein idempotenter Retry derselben
`operation_id` bleibt auch am Limit zulässig. Weber und Administratoren sind
von dieser Gastgrenze nicht betroffen.

Ein Weber darf zusätzlich fremde und gemeinschaftliche Knoten pflegen sowie bei
fremden Weberanträgen ein begründetes Veto einlegen und abstimmen.

Administratoren besitzen darüber hinaus moderative Rechte.

## Weberantrag

Der Gast löst **Weberstatus beantragen** aus. Pro Gast darf höchstens ein
offener Weberantrag bestehen. Der Antrag enthält:

- Antragsteller und Anzeigename;
- optionale Vorstellung oder Begründung;
- Status und vollständige Fristen;
- öffentliche Vetos;
- Stimmenzählung;
- Gesprächsraum;
- Ergebnis und Ausführungsstatus.

Der Antragsteller darf im eigenen Verfahren mitreden, aber weder ein formales
Veto gegen den eigenen Antrag einlegen noch über die eigene Aufnahme abstimmen.

## Erste Phase: sieben Tage Konsent

Nach dem Stellen befindet sich der Antrag exakt sieben Tage im Status
`consent`.

Jeder Weber oder Administrator außer dem Antragsteller selbst kann in dieser
Zeit ein begründetes Veto einlegen. Das Veto muss einen nichtleeren Einwand
enthalten.

Nach Ablauf gilt:

- **kein Veto:** Antrag wird angenommen;
- **mindestens ein Veto:** Antrag wechselt in die Abstimmungsphase.

Ein Veto lehnt den Antrag nicht ab. Es erzwingt Beratung und eine ausdrückliche
Abstimmung.

## Zweite Phase: sieben Tage Gespräch und Abstimmung

Die zweite Phase schließt unmittelbar an die erste an und dauert exakt weitere
sieben Tage. Die maximale reguläre Verfahrensdauer beträgt vierzehn Tage.

Jeder Weber oder Administrator außer dem Antragsteller selbst besitzt pro Antrag
genau eine aktuelle Stimme. Sie kann bis zum Fristende geändert werden:

- `ja`;
- `nein`;
- `enthaltung`.

Es gibt kein Quorum und keine Mindestbeteiligung. Die Entscheidungsregel ist:

```text
Ja-Stimmen > Nein-Stimmen
```

Daraus folgt:

- mehr Ja als Nein: angenommen;
- Gleichstand: abgelehnt;
- 0:0: abgelehnt;
- Enthaltungen verändern den Vergleich nicht.

## Ausführung eines angenommenen Weberantrags

Annahme und Rollenwechsel sind ein einziger PostgreSQL-Vorgang. Innerhalb
derselben Transaktion:

1. wechselt der Account von `gast` zu `weber`;
2. wechselt der Antrag auf `accepted`;
3. wird der Abschlusszeitpunkt gespeichert.

Nicht verändert werden:

- Account- und Garnrollen-ID;
- Anzeigename, Beschreibung und Tags;
- `map_state`, Position oder Radius;
- Urheberschaft bereits geknüpfter Knoten;
- bestehende Fäden und Gesprächsbeiträge.

Wiederholte Fristenauswertung ist idempotent. Es darf weder ein angenommener
Antrag ohne Weberrolle noch eine zweite Garnrolle entstehen.

## Fristenauswertung

Fristen werden serverseitig ausgewertet. Ein Browser ist weder Uhr noch
Ausführungsinstanz.

Die API wertet fällige Anträge bei relevanten Zugriffen aus. Zusätzlich läuft
im API-Prozess ein regelmäßiger Sweeper. Beide Wege benutzen dieselben
gesperrten und idempotenten Datenbankübergänge.

Governance ist nur aktiv, wenn Account-Lesen und Account-Schreiben kanonisch
aus PostgreSQL erfolgen. Fehlt diese Voraussetzung, antworten die Endpunkte
fail-closed statt auf eine zweite Wahrheit auszuweichen.

## Gesprächsraum

Jeder Antrag besitzt einen öffentlichen, lesbaren Gesprächsraum.

- Nicht angemeldete Besucher dürfen lesen.
- Angemeldete Gäste, Weber und Administratoren dürfen während einer offenen
  Phase Beiträge verfassen.
- Nach Abschluss bleibt der Gesprächsraum als Verfahrensnachweis lesbar, aber
  geschlossen.
- Beim Löschen eines Gastaccounts bleiben Beiträge als Verfahrensspur erhalten;
  die aktive Accountbindung des Beitrags wird entfernt.

Mitreden ist ein Webungsrecht jedes angemeldeten Accounts. Formale Vetos und
Stimmen setzen Weber- oder Administratorstatus voraus. Die Selbstentscheidung
des Antragstellers bleibt zusätzlich ausgeschlossen.

## Gast-Austritt

Ein Gast kann den eigenen Account vollständig auflösen. Details zur Erhaltung
und Anonymisierung gemeinschaftlicher Spuren stehen in
`docs/specs/garnrolle-knoten-faden.md`.

Der Austritt entfernt eigene Weberanträge, Passkeys, Sitzungen und die
Garnrolle. Gemeinschaftlich sichtbare Knoten und Beiträge werden nicht
stillschweigend vernichtet. Der Pfad ist für Weber und Administratoren gesperrt,
weil deren Austritt bereits übernommene gemeinschaftliche Verantwortung berührt
und einen eigenen späteren Governance- und Datenschutzprozess benötigt.

## Anträge-Oberfläche

Der Wurzelknopf **Gemeinsam** befindet sich im Kartenkopf oben mittig. Er zeigt
reale Governance-Sichten: alle Anträge, offene Konsentverfahren, Vetos,
Gesprächsphasen und laufende Abstimmungen. Das Stellen eines Antrags erscheint
als eigene Webungsaktion im unteren Werkzeugfächer.

Die Oberfläche bietet:

- Liste und Informationsseite aller Anträge;
- Status und verbleibende Zeit;
- Vetos und Stimmenzahlen;
- ein aus belegten Aktionen abgeleitetes, nicht editierbares Antragsgewebe;
- den öffentlichen Gesprächsraum;
- für angemeldete Accounts das Beitragsfeld;
- für Weber und Administratoren bei fremden Anträgen die kontextabhängigen
  Veto- und Abstimmungsaktionen;
- für Gäste Weberantrag und Gast-Austritt.

Die Oberfläche darf keine Rechte simulieren. Jeder Schutz wird zusätzlich auf
dem Server durchgesetzt.

## Erweiterung auf weitere Antragstypen

Das Zustandsmodell und die Fristen sind allgemein angelegt. Der aktuelle
Datenbankvertrag lässt zunächst ausschließlich `weberantrag` zu, damit nicht
spezifizierte Antragstypen nicht versehentlich produktiv werden.

## Nicht-Ziele dieses Schnitts

- kein Quorum;
- keine Mindestbeteiligung;
- keine gewichteten Stimmen;
- keine automatische Beförderung nach Zeit oder Aktivität;
- keine direkte Vergabe des Weberstatus durch einzelne Administratoren;
- keine zweite Governance-Wahrheit außerhalb PostgreSQL;
- noch kein allgemeiner Austrittsprozess für Weber.
