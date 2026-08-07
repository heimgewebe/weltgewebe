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
last_reviewed: 2026-08-06
review_after: 2026-11-06
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
   Die Anzahl der aktuell am Ziel anknüpfenden aktiven Gesprächsfäden steuert
   sichtbar den Ringdurchmesser: wenige Gespräche ergeben einen kleinen, engen
   Ring, mehr Gespräche einen größeren Ring. Durchmesser und Banddicke wachsen
   gesättigt (`log1p` oder gleichwertig) innerhalb fester Grenzen, sodass der
   Gesprächsring nicht in den äußeren Antragsring hineinwächst. Bei null
   Gesprächen ist der Ring unsichtbar. Rein zeitliche Alterungsopazität
   aktualisiert CSS/Style am bestehenden DOM.
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
  Stildefinition (`EDGE_VISUAL_STYLE` / `EDGE_THREAD_VARIANTS`) und dieselbe
  Kurvengeometrie. Es gibt genau vier Fadenarten: `knotting` ist der
  stabilste, dickste und geradeste Faden; `conversation` der dünnste, weichste
  und am stärksten ausschwingende; `proposal` der deutlichste Handlungsfaden;
  `vote` bleibt mit `proposal` verwandt, ist aber schlanker, straffer und über
  eine eigene Flechtrhythmik unterscheidbar. Untypisierte ausgehende Fäden
  nutzen genau eine interne `out`-Darstellung; `out` ist keine fünfte
  Fadenart. Keine Straßenmarkierungs- und keine Perlenoptik.
- **Kurvengeometrie:** Kanonische Fadenlinien sind deterministische, begrenzt
  abgetastete kubische Bézier-Pfade (oder gleichwertig), keine geraden
  technischen Linien und keine Kapselketten. Quelle und Ziel bleiben im
  GeoJSON exakt die gelieferten Koordinaten. Chord, Normalen, Bulge,
  Sampling **und Bogenlänge** werden in einer sphärischen Web-Mercator-Ebene
  (EPSG:3857-Radius, interne Breitenklemme nur für die Projektion) berechnet —
  nicht in rohen Lon/Lat-Graden und nicht in MapLibre-CSS-Pixeln, solange kein
  echter `map.project`-Pixelpfad angebunden ist. Kumulative Längen und
  Progress nutzen Web-Mercator-Meter entlang der projizierten Samples; ein
  Gradraum-`hypot(Δlng, Δlat)` ist vertragswidrig. Austritt und Einzug liegen
  für private Fäden nahezu am Sehnenverlauf; die Mitte trägt einen weiten
  natürlichen Bogen. Kurze Wege bleiben fast gerade; die laterale Auslenkung
  ist nach projizierter Chordlänge begrenzt (`EDGE_CURVE_FULL_LENGTH_M`,
  `EDGE_CURVE_MAX_BULGE_M`). Biegungsseite und Mikrovariation entstehen stabil
  aus Fadenidentität (`threadId` / `faden_subject_id`), nicht aus Zufall oder
  Physiksimulation. Die Abtastpunktzahl ist fest auf höchstens 96 Punkte
  begrenzt und mit einer maximalen sichtbaren Richtungsabweichung von 3 Grad
  krümmungs-/flachheitsadaptiv: Für jede
  zu prüfende Spanne werden mehrere innere Stützstellen ausgewertet (nicht nur
  die zwei Span-Enden), und die stärkste Tangentenrotation **zwischen einem
  beliebigen Paar** dieser Stützstellen entscheidet über eine weitere
  Unterteilung (`threadCurveAdaptiveBreakpoints` / `spanCurvatureMetrics`).
  Ein reiner Zwei-Punkt-Vergleich an den Span-Enden würde eine innere
  S-Kurve oder einen Spitzenknick übersehen, deren Endtangenten zufällig
  ähnlich sind; der Mehrpunktvergleich deckt diesen Fall zusätzlich ab, ohne
  die bestehende Empfindlichkeit für glatte, monoton rotierende Krümmung zu
  schwächen. So bleiben auch stark gekrümmte oder lange Fäden innerhalb der
  harten Obergrenze eine glatt wirkende Kurve statt einer sichtbar eckigen
  Polygonfolge. Der Sichtbarkeits-Schwellwert `EDGE_CURVE_MIN_VISIBLE_SEGMENT_M`
  vergleicht dabei sowohl die Fünf-Punkt-Subbogen-Schätzung als auch eine
  konservative Sub-Kontrollpolygon-Längenschranke (`spanControlPolygonLength`).
  Eine Spanne unterhalb dieser Schranke wird nur dann übersprungen, wenn sie
  nicht an ein sichtbares Segment mit einer unverfeinerten Tangenten-
  oder Knickabweichung angrenzt — so werden lokalisierte Rückläufe oder Cusps
  auch bei direkter Verwendung mit extremen Kontrollpunkten nicht wegen eines
  kurzen Endsegments übergangen. Unterhalb dieser Schwellwerte ohne angrenzenden
  Knick wird nicht weiter verfeinert, da eine Richtungsänderung auf dieser Skala
  auf keinem Kartenzoom sichtbar wäre. Es gibt keine Physiksimulation und keine
  Kollisionserkennung. Längenunterschiede am Antimeridian nutzen die kürzeste
  unwrapped Längendifferenz; Zwischenpunkte bleiben endlich (kein
  NaN/Infinity). Ungültige Unprojektion darf nicht als `[0, 0]` (Nullinsel)
  maskiert werden: explizites `null`/Fehler und sichere lineare unwrapped
  Interpolation. Ein vollständiger MapLibre-LineString-Split für
  World-Wrapping ist in dieser Stufe **nicht** Teil des Vertrags — der Pfad ist
  intern short-path-sicher, die Kartenrenderer-Grenze bleibt ehrlich offen.
  Ebenso ist ein statischer Pfadcache über den minütlichen Karten-Refresh
  hinaus **nicht** Teil dieser Stufe (nur einmal pro Feature-/Motion-Aufbau).
- **Kanonischer Pfadzustand:** Static und Motion teilen dieselbe reine
  Path-Builder-Logik und dieselbe Identität. Der unveränderliche Zustand
  enthält GeoJSON-Sample-Polyline, **einmalig vorbereitete projizierte
  Samples**, kumulative Bogenlängen in Web-Mercator-Metern, Gesamtlänge und
  stabile Segmentmetadaten (Farbsäume). Er wird einmal beim Aufbau eines
  statischen Features bzw. eines `ActiveMotion` erzeugt; pro Animationsframe
  dürfen nur der sichtbare Fortschrittsausschnitt und die GeoJSON-Feature-Hülle
  entstehen — keine erneute Kontrollpunkt-, Sampling-, Projektions- oder
  Seam-Berechnung im RAF. `pointAtArcProgress`, Clipping, Mehrfarben-Segmente
  und Motion-Tipp lesen denselben vorbereiteten Zustand. Concurrent Motion
  bleibt durch `EDGE_MOTION_MAX_ACTIVE` (8) begrenzt.
- **Spannungs- und Materialprofile** pro Fadenart (`THREAD_CURVE_PROFILES`):
  Knüpffaden straff, gering gekrümmt und kräftig; Gespräch weich, weiter,
  leicht asymmetrisch und dünner; Antrag ruhig, mittlere Spannung und breiter;
  Stimme schmal, antragsbezogen und ohne unabhängige Großkurve. Belegte
  `faden_subject_id` bindet Antrag, antragsbezogenes Gespräch und Stimme in
  ein **gemeinsames deterministisches Ordnungsfeld**: gleiche Biegungsseite
  und ein bevorzugter deterministischer Anflugvektor aus Subject-ID plus
  Zielidentität/-lage (`threadTargetLocalCorridorAxis`) — unabhängig von der
  jeweiligen Quell-Sehne berechnet. Dieser bevorzugte Vektor gilt jedoch
  **nicht ungeprüft für jede Quelle**: Er wird pro Quelle in einen sicheren
  Ziel-Einlaufkegel um die jeweils eigene natürliche Anflugrichtung (die
  umgekehrte Quell-Ziel-Sehne) geklemmt (`EDGE_CURVE_TARGET_APPROACH_CONE_DEG`,
  60°). Liegt die natürliche Richtung einer Quelle bereits innerhalb dieses
  Kegels, erhält sie den exakt gemeinsamen Vektor — der sichtbare
  Korridor-Zusammenschluss bleibt für den Normalfall erhalten. Liegt sie
  außerhalb (z. B. eine Quelle aus entgegengesetzter Richtung), wird der
  Vektor auf den Kegelrand geklemmt: derselbe Subject bedeutet dieselbe
  Biegungsseite und eine eng benachbarte Korridorfamilie, **nicht** mehr eine
  für jede Quellrichtung identische Endtangente — eine identische Tangente
  wäre mit rückfaltungsfreiem Einlauf aus beliebigen Richtungen geometrisch
  nicht vereinbar. Zusätzlich zu diesem Kegel erzwingt eine harte, von der
  Kegellogik unabhängige Invariante (`enforceMonotoneChordProjection`) eine
  nicht fallende Projektion der Kontrollpunkte `p0, p1, p2, p3` auf die
  Quelle→Ziel-Sehnenachse (`0 <= proj(p1) <= proj(p2) <= Länge`); daraus folgt
  mathematisch, dass die Bézier-Ableitung entlang dieser Achse nie negativ
  wird — keine Schleifen, kein Überschwingen, keine Umkehr, unabhängig davon,
  aus welcher Richtung eine Quelle kommt. Handle-Längen bleiben zusätzlich
  relativ (`EDGE_CURVE_MAX_HANDLE_FRACTION`) und absolut
  (`EDGE_CURVE_MAX_HANDLE_M`) begrenzt. Mittlere Bögen und Typenspannungen
  dürfen differieren. Ohne belegte Subject-ID gilt der bestehende
  fadenbezogene private Fallback ohne erfundene Beziehung (sehnenrelativer
  Ansatz), ebenfalls durch dieselbe Monotonie-Invariante abgesichert.
- **Schatten und Garnkörper** sind bei Knüpfen, Gespräch und Antrag weitgehend
  kontinuierlich; der Flecht-/Faserrhythmus lebt primär im schmalen Highlight.
  Stimme darf am Körper stichartiger bleiben, behält aber einen feinen
  kontinuierlichen Schatten-Zusammenhang.
- **Mehrfarbige Segmente** und Erzeugungs-/Auflösungsanimation segmentieren
  nach projizierter Kurvenlänge (Bogenfortschritt in Metern) und nutzen exakt
  dieselbe Pfadgeometrie wie der statische Faden. Farbsäume bleiben in diesem
  Fortschrittsraum fest. Benachbarte Mehrfarben-Segmente überlappen im
  Arc-Progress (einseitiger Seam-Pullback als Bruchteil der lokalen
  Segmentlänge). Der Motion-Tipp endet exakt bei
  `pointAtArcProgress(path, progress)` auf dem vorbereiteten Zustand; kein
  Segment zeichnet darüber hinaus. Wandernde Farbsäume und unbewiesene
  Gradient-Experimente sind unzulässig.

## Zentraler Linienanschluss

Kartenkoordinate, MapLibre-Markeranker und sichtbares X- bzw. Garnrollen-Zentrum
stimmen exakt überein (`anchor: center`). Fadenlinien laufen als geglättete
Kurven geometrisch bis zur tatsächlichen Mitte jedes Knotens bzw. jeder runden
Garnrolle (exakte Endpunkte) und werden nicht am Markerumfang abgeschnitten. Sie
liegen unter dem DOM-Marker (WebGL-Ebenen vor Symbol- und Marker-DOM), sodass
sie optisch in die Mitte eingezogen werden. `faden_endpoint_id` bleibt der
strikt gültige Alias für Webgemeindezentren.

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
