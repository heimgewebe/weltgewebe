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

1. **Knüpfkern** — Knotenanlage und echte Bearbeitung. Jeder Knoten beginnt als
   gewebtes Kreuz in der Farbe seines ersten verfügbaren Themas. Weitere Themen
   bilden faserige radiale Segmente, keine glatten Diagrammflächen.
2. **Gesprächsring** — aktive Gesprächsfäden liegen unmittelbar um den Kern. Sie
   sind lockerer gebunden und verflüchtigen sich mit ihrer Fadenlebensdauer.
3. **Antragsring** — jeder aktive Antrag erhält einen getrennten äußeren
   Antragsbogen. Bis zu sieben aktuelle Bögen bleiben einzeln sichtbar; eine
   achte Darstellung bündelt zusätzlichen Überlauf wahrheitsgetreu und nennt
   dessen Anzahl.
4. **Stimmkränze** — es gibt keinen losgelösten globalen Stimmring. Stimmstiche
   liegen ausschließlich am Bogen des Antrags, dessen `faden_subject_id` sie
   teilen.

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
vorhandener Produktkontext verwendet. Antrags- und Stimmfäden erben in dieser
Stufe die Primärfarbe ihres Zielkörpers, weil die öffentliche Fadenprojektion
noch keinen eigenen Themenbezug pro Antrag oder Webungsakt enthält.

Eine zukünftige Themenbindung muss explizit im Domänenvertrag stehen; sie darf
nicht aus Antragstexten geraten werden.

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

## Maßstab und Leistung

- **Ferne:** ein kompakter textiler Körper mit Kern, Gesprächsring und klaren
  äußeren Antragsabschnitten.
- **Nähe:** getrennte Antragsbögen und antragsgebundene Stimmstiche.
- **Auswahl:** Der textile Kartenmarker bleibt die maßgebliche Darstellung und
  wird hervorgehoben. Zonenordnung und Relationszahlen stehen zusätzlich in der
  zugänglichen Markerbeschriftung; das Fachpanel zeichnet keine zweite
  Gewebedarstellung.

Die Marker bleiben stabile DOM-Objekte. Bei Fadenaktivität wird nur ihr innerer
Gewebekörper neu aufgebaut; MapLibre-Positionierung, Fokus und Auswahl werden
nicht neu erzeugt. Die bestehende gemeinsame Minutenprojektion und der exakte
Ablauftimer steuern Linien und Knotenkörper gemeinsam. Dauerhafte physikalische
Simulationen aller Fasern sind nicht Teil dieses Vertrags.

## Nichtbehauptungen dieser Stufe

- keine vollständige historische Einzelaktionsdarstellung ohne
  Webungsschlag-Ledger;
- keine genaue Antrags-Themenfarbe ohne explizite Themenbindung;
- keine Statusform eines Antrags ohne Statusprojektion auf die Karte;
- keine Offenlegung individueller Stimmentscheidung. Sichtbar ist nur die
  belegte, antragsgebundene Beteiligungsrelation.
