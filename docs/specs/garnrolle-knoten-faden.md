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
last_reviewed: 2026-07-14
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

## Grundmodell

Eine registrierte E-Mail-Adresse erzeugt zunächst eine **Gastidentität**, nicht bereits eine Garnrolle. Der Gast kann das Weltgewebe vollständig wahrnehmen, aber noch nicht daran weben.

Erst ein angenommener Weberantrag aktiviert dieselbe Accountidentität als genau eine Garnrolle. Die Garnrolle ist damit kein Synonym für jeden technischen Account, sondern der sichtbare und handlungsfähige Ausgangspunkt eines Webers.

| Produktbegriff | technischer Begriff | Bedeutung |
|---|---|---|
| Gastidentität | Account mit Rolle `gast` | Zugang ohne sichtbare Spur und ohne Webungsrechte |
| Garnrolle | Account mit Rolle `weber` oder `admin` | sichtbarer und handlungsfähiger Ausgangspunkt |
| Knoten | Node | Ort, Commons, Ressource, Vorhaben, Bedarf oder Angebot |
| Webungsaktion | Domain action | gemeinschaftlich relevante Handlung eines Webers |
| Faden | Edge/Projektion | automatisch abgeleitete Visualisierung einer Webungsaktion |
| Gesprächsraum | Conversation | eigener Diskussions- oder Entscheidungsraum |
| Beitrag | Message | Inhalt eines Gesprächsraums und selbst eine Webungsaktion |

`thread` ist als technischer Sammelbegriff verboten. Eine Graphprojektion ist ein `edge`, ein Gesprächsraum eine `conversation`.

## Gastidentität

Ein Gast darf:

- das gesamte öffentliche Weltgewebe ansehen;
- suchen und filtern;
- Garnrollen, Knoten, Fäden, Anträge und Gesprächsräume lesen;
- den eigenen Weberstatus beantragen;
- den eigenen Gaststatus vollständig auflösen.

Ein Gast besitzt keine Garnrolle, erscheint nicht in öffentlichen Garnrollenlisten und kann nicht auf der Karte verortet werden. Er darf keine Webungsaktion ausführen und hinterlässt keine reguläre Spur.

Die beiden zustandsändernden Gastvorgänge sind Sonderpfade:

1. Weberstatus beantragen;
2. Gastidentität auflösen und das Weltgewebe verlassen.

Die Aufnahme als Weber folgt `docs/specs/governance-antraege.md`.

## Garnrolle

Eine angenommene Aufnahme aktiviert genau eine Garnrolle. Sie kann enthalten:

- Anzeigename und Kurzbeschreibung;
- Fähigkeiten, Güter, Interessen und Tags;
- optional eine interne reale Position;
- optional eine öffentliche Kartenprojektion;
- geknüpfte Knoten;
- aus Webungsaktionen abgeleitete Fäden.

Die Rollen `weber` und `admin` regeln technische Rechte. Die Garnrolle bleibt die fachliche Darstellung des webenden Accounts.

## Verortung und Sichtbarkeit

Die Nutzerhandlung lautet:

> Garnrolle auf die Karte setzen

Die öffentliche Darstellung kennt genau drei Zustände:

| Nutzertext | API-Wert | Wirkung |
|---|---|---|
| Noch nicht auf der Karte | `not_on_map` | keine öffentliche Position |
| Exakt sichtbar | `exact` | öffentliche Position entspricht der gewählten Position |
| Im Umkreis sichtbar | `radius` | öffentliche Position wird angenähert dargestellt |

Regeln:

1. Eine Garnrolle beginnt nach der Aufnahme im Zustand `not_on_map`.
2. Eine Garnrolle kann ohne öffentliche Position bestehen.
3. Exakte Sichtbarkeit ist ein regulärer, positiv formulierter Fall.
4. Nur `radius` verlangt ein Radiusfeld.
5. `not_on_map` darf auch bei intern vorhandener Position keine öffentliche Koordinate ausgeben.
6. Alte RoN- und `mode`-Felder sind nur Migrationskontext und keine Produktsprache.

## Knoten

Ein Knoten ist ein fachlich fassbares Bündel. Er kann verortet oder ortsunabhängig sein. Beispiele:

- Commons-Ort;
- Projekt oder Initiative;
- Werkzeug oder Ressource;
- Angebot oder Bedarf;
- Veranstaltung;
- Idee, Frage oder Beschlussgegenstand.

Knoten werden durch die Webungsaktion **Knoten knüpfen** aus einer angemeldeten Garnrolle heraus angelegt. Seed- oder Demo-Inhalte dürfen den organischen Produktpfad nicht ersetzen.

## Webungsaktionen

Webungsaktionen verändern oder erweitern das gemeinsame Gewebe. Dazu gehören unter anderem:

- Knoten knüpfen;
- kommunizieren;
- Anträge stellen;
- ein begründetes Veto einlegen;
- abstimmen;
- später weitere ausdrücklich spezifizierte Gemeinschaftshandlungen.

Die jeweilige fachliche Aktion ist die Quelle der Wahrheit. Sie wird vollständig validiert, autorisiert und dauerhaft gespeichert. Eine sichtbare Fadenprojektion darf niemals die eigentliche Handlung ersetzen.

## Fäden

Ein Faden ist **kein direkt bearbeitbares Fachobjekt**. Nutzer können Fäden weder erstellen noch ändern noch löschen.

Ein Faden entsteht ausschließlich als automatisch abgeleitete Visualisierung einer erfolgreichen Webungsaktion. Daraus folgen vier harte Regeln:

1. Es gibt keinen öffentlichen `POST`, `PUT`, `PATCH` oder `DELETE`-Pfad für Fäden.
2. Die Benutzeroberfläche bietet keinen Fadeneditor und keine Aktion „Faden ohne zugrunde liegende Handlung erzeugen“.
3. Der Server erzeugt oder repariert die Projektion mit einer stabilen Operations-ID, damit Wiederholungen keine doppelten Fäden anlegen.
4. Aus der Projektion muss auf die belegte Webungsaktion zurückgeführt werden können; Fäden besitzen keine von ihr unabhängige Wahrheit.

Beim Knotenknüpfen erzeugt der Server nach der dauerhaften Knotenanlage den zugehörigen Garnrolle-Knoten-Faden. Schlägt die Projektion nach der Knotenanlage fehl, meldet der Server den Gesamtvorgang als noch nicht erfolgreich. Eine Wiederholung derselben Operations-ID repariert die fehlende Projektion; der Browser darf weder selbst einen Faden schreiben noch „ohne Faden fortfahren“.

Anträge, Vetos, Abstimmungen und Gesprächsbeiträge sind bereits als eigene dauerhafte Governance-Datensätze belegt. Ihre räumliche oder graphische Fadenprojektion wird aus diesen Datensätzen abgeleitet, sobald der jeweilige Darstellungskontext spezifiziert ist. Es entsteht dafür kein manueller Fadenschreibweg.

## Erster organischer Produktfluss

1. E-Mail-Adresse anmelden oder registrieren.
2. Als Gast das Weltgewebe erkunden.
3. Weberstatus beantragen.
4. Nach Annahme genau eine Garnrolle erhalten.
5. Garnrolle beschreiben und optional auf die Karte setzen.
6. Ersten Knoten knüpfen.
7. Der Server leitet den passenden Faden aus derselben Webungsaktion ab.
8. Garnrolle, Knoten und abgeleitete Projektion nach Neuladen wiederfinden.

Dieser vertikale Schnitt muss ohne Demo-Fallback und mit eindeutigem Persistenzpfad funktionieren.

## Produktsprache

Nutzertexte verwenden Gast, Weber, Garnrolle, Knoten, Faden, knüpfen, weben, Sichtbarkeit, Antrag und Gesprächsraum. Interne Begriffe wie Account, Node, Edge, Credential, Token oder WebAuthn erscheinen nicht in der Hauptführung.

## Nicht-Ziele

- kein Trust-Score;
- keine automatische Weberbeförderung nach Zeit oder Aktivität;
- keine Garnrolle für Gäste;
- kein direkter Fadeneditor;
- kein anonymer Alternativaccount neben der Gastidentität;
- kein Privacy-Modus als Accountart;
- keine künstliche Währung;
- kein Demo-Datensatz als Ersatz für echte Webungsaktionen.
