# Garnrolle (Konzept)

Die **Garnrolle** repräsentiert das Konto (Account) eines Akteurs im Weltgewebe. Sie ist der Ursprung aller Fäden (Kanten), die der Akteur spinnt.

## Definition

> **Garnrolle** = Konto + private Einstellungen + öffentliche Profil-/Ressourceninfos + Verortung am Wohnsitz.

Semantisch ist sie die "Spule, auf der der Faden sitzt".

## Privatsphäre & Verortung

Da die Garnrolle fest am Wohnsitz verankert ist (**Residence-Lock**), gibt es strenge Mechanismen zum Schutz der Privatsphäre.

### Default: Exakt
Standardmäßig wird die Position **exakt** angezeigt.

### Opt-in: Unschärfe (Radius)
Der Nutzer kann einen **Unschärferadius** (in Metern) definieren.
*   **Radius = 0m**: Exakte Anzeige (Standard).
*   **Radius > 0m**: Die öffentliche Anzeige (`public_pos`) ist ein zufälliger, aber stabiler Punkt innerhalb dieses Radius.

### RoN (Rolle ohne Namen)
Optional kann die **RoN-Flag** gesetzt werden, um die Identität zu verschleiern (Anonymisierung).

## Technische Umsetzung

### Views
Es wird strikt zwischen interner und öffentlicher Sicht getrennt:
*   **Internal View (`roles_view`)**: Kennt die exakte `location` (Wohnsitz). Nur für den Nutzer selbst sichtbar.
*   **Public View (`public_role_view`)**: Enthält **nie** die exakte `location`, sondern nur die `public_pos`.
    *   `public_pos` wird aus `location` + `radius_m` berechnet (Jitter).
    *   Alle öffentlichen Fäden starten optisch an der `public_pos`.

### Normative Quelle
Siehe [ADR-0003: Privacy: Unschärferadius & RoN](../adr/ADR-0003__privacy-unschaerferadius-ron.md).
