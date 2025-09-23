# ADR-0003 — Privacy: Unschärferadius & RoN-Platzhalterrolle (v1)
Datum: 2025-09-13  
Status: Accepted

## Kontext
Die Garnrolle ist am Wohnsitz verortet (Residence-Lock). Die Karte und die Fäden sollen ortsbasierte Sichtbarkeit ermöglichen, ohne den exakten Wohnsitz preiszugeben - sofern dies explizit vom Nutzer gewünscht ist. Generell gilt: Transparenz ist Standard – Privacy-Optionen sind ein freiwilliges Zugeständnis für Nutzer, die das wünschen.

## Entscheidung
1) **Unschärferadius r (Meter)**  
   Der Nutzer kann die öffentliche Genauigkeit seiner Garnrolle über einen **Unschärferadius** selbst einstellen. Die **öffentliche Anzeige** nutzt eine **ungenaue Position innerhalb dieses Radius**.  
   Alle öffentlichen Darstellungen und Beziehungen (Fäden/Garn) beziehen sich auf diese angezeigte Position.

2) **RoN-Platzhalterrolle (Toggle)**  
   Optional kann sich ein Nutzer **als „RoN“** (Rolle ohne Namen) zeigen bzw. Beiträge **anonymisieren**. Anonymisierte Fäden verweisen nicht mehr auf die ursprüngliche Garnrolle, sondern auf den **RoN-Platzhalter**. Beim Ausstieg werden Beiträge gemäß RoN-Prozess überführt.

3) **Transparenz als Standard**  
   Standard ist **ohne Unschärfe und ohne RoN**. Die Optionen sind **Opt-in** und dienen der persönlichen Zurückhaltung, nicht der Norm.

## Alternativen
Weitere Modi (z. B. Kachel-Snapping, Stadt-Centroid) werden **nicht** eingeführt.

## Konsequenzen
- **Einfaches UI**: **Slider** (Meter) für den Unschärferadius, **Toggle** für RoN.  
- **Konsistente Darstellung**: Öffentliche Fäden starten an der öffentlich angezeigten Position der Garnrolle.  
- **Eigenverantwortung**: Nutzer wählen ihre gewünschte Sichtbarkeit bewusst.

## Schnittstellen
- **Events**  
  - `VisibilityPreferenceSet { radius_m }`  
  - `RonEnabled` / `RonDisabled`
- **Views**  
  - intern: `roles_view` (exakte Position, nicht öffentlich)  
  - öffentlich: `public_role_view (id, public_pos, ron_flag, radius_m)`  
  - `faden_view` nutzt `public_pos` als Startpunkt

## UI
**Einstellungen → Privatsphäre**: Unschärfe-Slider (Meter) + RoN-Toggle (inkl. Eistellbarkeit der Tage (beginnend mit 0, ab der die RoN-Anonymisierung greifen soll). Vorschau der angezeigten Position.

## Telemetrie & Logging
Keine exakten Wohnsitz-Koordinaten in öffentlichen Daten oder Logs, sofern gewünscht; personenbezogene Daten nur, wo nötig.

## Rollout
- **Web**: Slider + Toggle und Vorschau integrieren.  
- **API**: `/me/visibility {GET/PUT}`, `/me/roles` liefert `public_pos`, `ron_flag`, `radius_m`.  
- **Worker**: Privacy-Auflösung vor Projektionen (`public_role_view` vor `faden_view`).