---
id: specs.knoten-gewebe-visualisierung
title: Knoten-Gewebevisualisierung
summary: Kanonischer Produkt- und Renderingvertrag für gewachsene Knoten, Beteiligungszonen und antragsgebundene Stimmen auf der Karte.
doc_type: specification
status: canonical
canonicality: normative
lifecycle_state: active
role: norm
organ: product-map
owner: product-map
last_reviewed: 2026-08-05
review_after: 2026-11-05
depends_on:
  - specs.garnrolle-knoten-faden
  - specs.map-experience
relations:
  - type: relates_to
    target: docs/specs/governance-antraege.md
  - type: relates_to
    target: docs/specs/ortsweberei-webgemeindezentrum.md
verifies_with:
  - apps/web/src/lib/map/weaveTheme.ts
  - apps/web/src/lib/map/weaveModel.ts
  - apps/web/src/lib/map/weaveModel.test.ts
  - apps/web/src/lib/map/overlay/weaveRuntime.ts
  - apps/web/src/lib/map/overlay/nodes.ts
  - apps/web/src/lib/map/overlay/nodes.test.ts
  - apps/web/src/lib/map/overlay/edges.ts
  - apps/web/src/lib/map/overlay/edges.test.ts
  - apps/web/tests/woven-node-visualization.spec.ts
  - apps/web/tests/garnrolle-marker-rendering.spec.ts
---

# Knoten-Gewebevisualisierung

Status: Produkt- und Renderingvertrag für die erste umsetzbare Stufe.

## Bedeutung

Ein Knoten ist kein austauschbarer Kartenmarker. Er ist ein gewachsener
Gewebekörper, dessen sichtbare Schichten aus Beteiligung entstehen.

Die Darstellung trennt vier Fragen:

- **Farbe:** Thema des Knotens beziehungsweise des aktuell verfügbaren
  Themenbezugs.
- **Bindung und Lage:** Art des Webungsakts.
- **Spannung und Sättigung:** Aktivität und verbleibende Lebensdauer.
- **Bogenbindung:** fachliches Ziel, insbesondere die Zuordnung einer Stimme zu
  genau einem Antrag.

Farbe darf niemals allein die Fadenart tragen. Menschen mit eingeschränkter
Farbwahrnehmung müssen Knüpfen, Gespräch, Antrag und Stimme weiterhin anhand von
Lage, Breite, Bindung und Rhythmus unterscheiden können.

## Kanonische Zonen

1. **Knüpfkern (diagonales X)** — Knotenanlage und echte Bearbeitung. Der Kern
   ist ein diagonales gewebtes X aus zwei über/unter gekreuzten textilen
   Strängen mit vier stabilen Armen (`northwest`, `northeast`, `southeast`,
   `southwest`). Kein Plus und kein Zielscheiben-Primärmotiv. Themen färben die
   Arme deterministisch: ein Thema einfarbig, zwei Themen je einen Strang
   (NW–SE bzw. NE–SW), drei oder vier Themen stabil auf die Arme verteilt, mehr
   als vier Themen bleiben vollständig im Modell und verdichten die Sicht auf
   maximal vier Primärfarben. Belegte Armauflagerungen sind vorbereitet, bleiben
   aber leer, solange die öffentliche Kartenprojektion keine dem Knoten
   hinzugefügten Inhalte liefert (Wahrheitsgrenze).
2. **Gesprächsring** — aktive Gesprächsfäden liegen unmittelbar um die Kreuzung.
   Die Ringdicke wächst gesättigt (`log1p` oder gleichwertig) bis zu einer festen
   Maximaldicke; bei null Gesprächen ist der Ring unsichtbar. Rein zeitliche
   Alterungsopazität aktualisiert CSS/Style am bestehenden DOM.
3. **Antragsring** — jeder aktive Antrag erhält einen getrennten äußeren
   Antragsbogen. Bis zu sieben aktuelle Bögen bleiben einzeln sichtbar; eine
   achte Darstellung bündelt zusätzlichen Überlauf wahrheitsgetreu und nennt
   dessen Anzahl.
4. **Stimmkränze** — es gibt keinen losgelösten globalen Stimmring. Stimmstiche
   liegen ausschließlich am Bogen des Antrags, dessen `faden_subject_id` sie
   teilen; als DOM-Geschwister der Antragsbögen, nicht verschachtelt.

Gesprächsfäden mit derselben `faden_subject_id` wie ein sichtbarer Antrag werden
zusätzlich als antragsbezogenes Gespräch am betreffenden Bogen gezählt. Der
Gesprächsring zeigt dennoch die gesamte aktive Gesprächsbeteiligung.

## Faden und Webungsschlag

Die bestehende Domänenwahrheit hält pro Konto, Fadenart und semantischem Ziel
eine stabile Fadenrelation. Wiederholte Beteiligung reaktiviert diese Relation,
statt parallele Kartenlinien zu erzeugen.

Ein **Webungsschlag** bezeichnet dagegen eine einzelne echte Handlung, etwa
einen neuen Beitrag oder eine echte Bearbeitung. Die aktuelle Datenprojektion
enthält noch kein dauerhaftes, öffentliches Webungsschlag-Ledger. Deshalb zeigt
diese Stufe ausschließlich belegte aktive Fadenrelationen. Sie behauptet nicht,
jede historische Einzelhandlung als eigene Faser rekonstruieren zu können.
Exakte Wiederholungen und semantische Nulländerungen erzeugen weder eine neue
Relation noch einen erfundenen Webungsschlag.

## Themenwahrheit

Die Themenfarben stammen derzeit aus den verfügbaren Knotenschlagwörtern und der
Knotenart. Für Webgemeindezentren werden Gemeinschaft und Mitentscheidung als
vorhandener Produktkontext verwendet. Fadenlinien erben die Themenpalette ihres
Zielkörpers: ein Thema einfarbig, mehrere Themen als kontrollierte, entlang der
Linie wiederholte Teilstränge (keine Regenbogenblendung). Die Fadenart bleibt
davon unabhängig über Breite, Dash/Flechtmuster, Halo und Dichte unterscheidbar.

Eine zukünftige Themenbindung pro Antrag muss explizit im Domänenvertrag stehen;
sie darf nicht aus Antragstexten geraten werden.

## Wahrheitsgrenze Armauflagerungen

Die öffentliche Knoten-/Kartenprojektion liefert in dieser Stufe noch keine
begrenzte Liste dem Knoten hinzugefügter Inhalte. Das Modell und der Renderer
halten deshalb eine leere, fest gedeckelte Armauflagerungsprojektion bereit und
zeigen keine erfundenen Zahlen.

## Mehrere Anträge

Anträge werden nach jüngster belegter Fadenaktivität stabil angeordnet. Bei bis
zu sieben Anträgen bleibt jeder Bogen einzeln sichtbar. Ab dem achten Antrag
bleiben die sieben jüngsten einzeln; der achte Darstellungsplatz bündelt den
Rest und nennt dessen Anzahl. Das ist eine Darstellungsbündelung, keine
fachliche Zusammenlegung.

Die Statusformen `Entwurf`, `Beratung`, `Abstimmung`, `angenommen`, `abgelehnt`,
`zurückgezogen` und `umgesetzt` können erst verbindlich gezeichnet werden, wenn
der Kartenvertrag den Antragsstatus revisionsgebunden liefert. Bis dahin zeigt
der Bogen ausschließlich belegte Aktivität.

## Sichtbarkeit: bewusste Asymmetrie zwischen Körper und Linie

Diese Asymmetrie ist normativ und kein Nebeneffekt der Umsetzung.

- Ein **sichtbarer Zielkörper** trägt seine belegte Gewebestruktur auch dann,
  wenn der Quellmarker ausgefiltert ist. Die Beteiligung am Ziel bleibt wahr,
  unabhängig davon, ob die beteiligte Garnrolle gerade angezeigt wird.
- Eine **Kartenlinie** darf ausschließlich existieren, wenn Quelle _und_ Ziel
  als sichtbare Endpunkte aufgelöst sind. Eine Linie zu einem unsichtbaren
  Endpunkt behauptete eine Lage, die auf der Karte nicht belegt ist.
- Beide Darstellungen nutzen deshalb bewusst **verschiedene, klar benannte
  Fadenmengen**: die Gewebemenge (`deriveWeaveEdges`, zielseitig aufgelöst) und
  die Linienmenge (`deriveLineEdges`, beidseitig aufgelöst). Die Linienmenge ist
  stets eine Teilmenge der Gewebemenge.
- Die **Ablaufprojektion gilt trotzdem gemeinsam und exakt**: Beide Mengen
  werden aus demselben Projektionszeitpunkt abgeleitet. Dieser Zeitpunkt wird
  bei Fadenänderung, im Minutenintervall, zum exakten Ablaufzeitpunkt und bei
  der Rückkehr eines zuvor verborgenen Tabs neu gelesen. Ein Faden, der während
  aktiver Filterung oder im Hintergrund abläuft, darf beim Wiedereinblenden
  nicht zurückkehren.

## Themenidentität

Die Identität eines Themas entsteht exakt aus
`value.normalize('NFKC').replace(/\s+/g, ' ').trim()`. Es folgt **keine**
zusätzliche Kleinschreibung und keine generische Präfixentfernung. Vor
Deduplizierung, Hashing, Segment-Identität und Farbzuordnung findet **keine**
Kürzung statt. Zwei lange Themen mit gleichem Präfix — etwa
`Nachbarschaftliche Lebensmittelversorgung Hamburg` und
`Nachbarschaftliche Lebensmittelversorgung Hannover` — bleiben verschiedene
Segmente mit eigener Farbe. Auch case-verschiedene normalisierte Themen
(`Kunst` / `kunst`) bleiben getrennte Identitäten. Eine rein technische
Ignorier-/Vergleichslogik darf case-insensitiv arbeiten, ohne die Identität zu
falten.

Bedeutungstragende Doppelpunkte (z. B. `Kunst: Öffentlicher Raum` oder
`kunst:öffentlicher raum`) bleiben in Identität, Anzeige und Farbe vollständig
erhalten. Nur ein explizit allowlisteter technischer Namensraum (aktuell
`thema:`) darf höchstens in der **finalen Anzeige** entfallen; Identität, Hash
und Farbe behalten den vollständigen normalisierten Text. Alle eindeutig
normalisierten Themen bleiben im Modell; die visuelle Palette/X-Geometrie bleibt
auf höchstens vier Primärfarben begrenzt.

## Materialsprache Knoten und Fäden

Knoten und Fäden teilen dieselbe textile Materialsprache.

- **Knotenarme** sind diagonal gewebte Garnarme: leicht zum Zentrum zulaufend,
  mit feiner Flecht-/Faserstruktur, dunklem Rand und schmaler Lichtkante. Kein
  Plus, kein Bullseye, kein schwarzes Loch, keine Pill-/Kapseloptik und kein
  quadratischer Hintergrund. Mehrthemenfarben bleiben pro Arm sichtbar; die
  Über-/Unter-Kreuzung der beiden Diagonalen ist klar lesbar.
- **Fäden** nutzen eine performante Garnillusion aus begrenzten MapLibre-Layern
  pro Fadenart: subtiler Schatten/Unterzug, farbiger Garnkörper, feiner
  Licht-/Faserakzent. Static- und Motion-Pfad teilen exakt dieselbe
  Stildefinition (`EDGE_VISUAL_STYLE` / `EDGE_THREAD_VARIANTS`). Typen
  `knotting`, `conversation`, `proposal`, `vote` und `legacy` bleiben über
  Breite und sinnvolle Flecht-/Dash-Rhythmen unterscheidbar — keine
  Straßenmarkierungs- und keine Perlenoptik.
- **Mehrfarbige Segmente** halten feste Farbsäume entlang der Geometrie. An
  belegten WebGL-Nahtstellen (runde Line-Caps) gilt eine stabile, minimale
  geometrische Überdeckung der Segmentenden. Wandernde Farbsäume und
  unbewiesene Gradient-Experimente sind unzulässig.

## Zentraler Linienanschluss

Kartenkoordinate, MapLibre-Markeranker und sichtbares X- bzw. Garnrollen-Zentrum
stimmen exakt überein (`anchor: center`). Fadenlinien laufen geometrisch bis zur
tatsächlichen Mitte jedes Knotens bzw. jeder runden Garnrolle und werden nicht
am Markerumfang abgeschnitten. Sie liegen unter dem DOM-Marker (WebGL-Ebenen
vor Symbol- und Marker-DOM), sodass sie optisch in die Mitte eingezogen werden.
`faden_endpoint_id` bleibt der strikt gültige Alias für Webgemeindezentren.

## Schichten und Interaktion

Schichten innen nach außen: Kreuzung, Gesprächsring, X-Arme/Auflagerungen,
Proposal-Segmente, Stimmen, externer Fokus/Such/Auswahlhalo. Kein quadratischer
Hintergrund, keine Box um Marker oder Namen, kein Clipping des Gewebekörpers,
geografischer Center-Anker stabil, Touchziel mindestens 44×44.

## Maßstab und Leistung

- **Ferne:** ein kompakter textiler Körper mit Kern, Gesprächsring und klaren
  äußeren Antragsabschnitten.
- **Nähe:** getrennte Antragsbögen und antragsgebundene Stimmstiche.
- **Auswahl:** Der textile Kartenmarker bleibt die maßgebliche Darstellung und
  wird hervorgehoben. Zonenordnung und Relationszahlen stehen zusätzlich in der
  zugänglichen Markerbeschriftung; das Fachpanel zeichnet keine zweite
  Gewebedarstellung.

Unter Zoomstufe 13,5 bleibt der Körper kompakt: Antragsabschnitte bleiben
sichtbar, während Stimmstiche und rein dekorative Bogenfasern ausgeblendet
werden. Ab Zoomstufe 13,5 erscheint die antragsgebundene Detaildarstellung.
Diese Umschaltung verändert keine Relationszahlen und keine Domänenwahrheit.

Die Marker bleiben stabile DOM-Objekte. Bei Fadenaktivität wird nur ihr innerer
Gewebekörper neu aufgebaut; MapLibre-Positionierung, Fokus und Auswahl werden
nicht neu erzeugt. Die bestehende gemeinsame Minutenprojektion und der exakte
Ablauftimer steuern Linien und Knotenkörper gemeinsam. Dauerhafte physikalische
Simulationen aller Fasern sind nicht Teil dieses Vertrags.

Ein Neuaufbau des Gewebekörpers ist ausschließlich an **strukturelle** Änderungen
gebunden: Themenidentitäten, Segmentgeometrie, Antragszuordnung, Fadenzahlen und
Überlauf. Die zeitliche Deckkraft alternder Gesprächs- und Antragsfäden ist keine
Strukturänderung; sie wird auf die bereits vorhandenen Elemente geschrieben. Eine
rein zeitliche Alterung darf den Gewebe-DOM nicht ersetzen.

Die vollständige Bereitschaft des Kartenstils gilt erst dann als erreicht, wenn
die Fadenquelle und **sämtliche** kanonischen Halo- und Linienebenen der
typisierten Fadenarten vorhanden sind. Eine unvollständig wiederhergestellte
Stilmenge darf nicht als bereit behandelt werden.

Scheitert die Karteninitialisierung — etwa weil ein früher dynamischer Import
nicht geladen werden kann —, endet der Ladezustand. Es erscheint ein sichtbarer,
zugänglicher Fehlerzustand mit Wiederholungsmöglichkeit. Ein unendlicher
Ladezustand ist vertragswidrig.

## Nichtbehauptungen dieser Stufe

- keine vollständige historische Einzelaktionsdarstellung ohne
  Webungsschlag-Ledger;
- keine genaue Antrags-Themenfarbe ohne explizite Themenbindung;
- keine Statusform eines Antrags ohne Statusprojektion auf die Karte;
- keine Offenlegung individueller Stimmentscheidung. Sichtbar ist nur die
  belegte, antragsgebundene Beteiligungsrelation.
