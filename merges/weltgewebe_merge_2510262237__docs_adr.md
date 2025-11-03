### 📄 docs/adr/0042-consume-semantah-contracts.md

**Größe:** 276 B | **md5:** `eebc6c89ed10ea1704ace598b0064f93`

```markdown
# ADR-0042: semantAH-Contracts konsumieren

Status: accepted

Beschluss:

- Weltgewebe liest JSONL-Dumps (Nodes/Edges) als Infoquelle (read-only).
- Kein Schreibpfad zurück. Eventuelle Events: getrennte Domain.

Konsequenzen:

- CI validiert nur Formate; Import-Job später.
```

### 📄 docs/adr/ADR-0001__clean-slate-docs-monorepo.md

**Größe:** 315 B | **md5:** `a9e740a160cba7d00fa8f071255af7b8`

```markdown
# ADR-0001 — Clean-Slate als Docs-Monorepo

Datum: 2025-09-12
Status: Accepted
Entscheidung: Rückbau auf Doku-only. Re-Entry nur über klar definierte Gates.
Alternativen: Sofortiger Code-Reentry ohne ADR; verworfen wegen Drift-Risiko.
Konsequenzen: Vor Code zuerst Ordnungsprinzipien, Budgets, SLOs festhalten.
```

### 📄 docs/adr/ADR-0002__reentry-kriterien.md

**Größe:** 354 B | **md5:** `5a6822d1f593300a94d57cc86d6dea1d`

```markdown
# ADR-0002 — Re-Entry-Kriterien (Gates)

Datum: 2025-09-12
Status: Accepted
Gate A (Web): SvelteKit-Skelett + Budgets (TTI ≤2s, INP ≤200ms, ≤60KB JS).
Gate B (API): Health/Version, Contracts, Migrations-Plan.
Gate C (Infra-light): Compose dev, Caddy/CSP-Basis, keine laufenden Kosten.
Gate D (Security-Basis): Secrets-Plan, Lizenz-/Datenhygiene.
```

### 📄 docs/adr/ADR-0003__privacy-unschaerferadius-ron.md

**Größe:** 3 KB | **md5:** `f864059948a3cbad3cd93757311430b4`

```markdown
# ADR-0003 — Privacy: Unschärferadius & RoN-Platzhalterrolle (v1)

Datum: 2025-09-13  
Status: Accepted

## Kontext

Die Garnrolle ist am Wohnsitz verortet (Residence-Lock). Die Karte und die Fäden sollen ortsbasierte
Sichtbarkeit ermöglichen, ohne den exakten Wohnsitz preiszugeben - sofern dies explizit vom Nutzer gewünscht
ist. Generell gilt: Transparenz ist Standard – Privacy-Optionen sind ein freiwilliges Zugeständnis für
Nutzer, die das wünschen.

## Entscheidung

1) **Unschärferadius r (Meter)**  
   Der Nutzer kann die öffentliche Genauigkeit seiner Garnrolle über einen **Unschärferadius** selbst
   einstellen. Die **öffentliche Anzeige** nutzt eine **ungenaue Position innerhalb dieses Radius**.
   Alle öffentlichen Darstellungen und Beziehungen (Fäden/Garn) beziehen sich auf diese angezeigte Position.

2) **RoN-Platzhalterrolle (Toggle)**  
   Optional kann sich ein Nutzer **als „RoN“** (Rolle ohne Namen) zeigen bzw. Beiträge **anonymisieren**.
   Anonymisierte Fäden verweisen nicht mehr auf die ursprüngliche Garnrolle, sondern auf den
   **RoN-Platzhalter**. Beim Ausstieg werden Beiträge gemäß RoN-Prozess überführt.

3) **Transparenz als Standard**  
   Standard ist **ohne Unschärfe und ohne RoN**. Die Optionen sind **Opt-in** und dienen der persönlichen
   Zurückhaltung, nicht der Norm.

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

**Einstellungen → Privatsphäre**: Unschärfe-Slider (Meter) + RoN-Toggle (inkl. Einstellbarkeit der Tage
(beginnend mit 0, ab der die RoN-Anonymisierung greifen soll). Vorschau der angezeigten Position.

## Telemetrie & Logging

Keine exakten Wohnsitz-Koordinaten in öffentlichen Daten oder Logs, sofern gewünscht; personenbezogene Daten
nur, wo nötig.

## Rollout

- **Web**: Slider + Toggle und Vorschau integrieren.  
- **API**: `/me/visibility {GET/PUT}`, `/me/roles` liefert `public_pos`, `ron_flag`, `radius_m`.  
- **Worker**: Privacy-Auflösung vor Projektionen (`public_role_view` vor `faden_view`).
```

### 📄 docs/adr/ADR-0004__fahrplan-verweis.md

**Größe:** 874 B | **md5:** `e704ae31604d2be399186837a67ca35b`

```markdown
# ADR-0004 — Fahrplan als kanonischer Verweis

Datum: 2025-02-14
Status: Accepted

## Kontext

Der Projektfahrplan wird bereits in `docs/process/fahrplan.md` gepflegt. Dieses ADR dient lediglich als
stabile, versionierte Referenz auf diesen kanonischen Speicherort und vermeidet inhaltliche Duplikate.

## Entscheidung

- Der Fahrplan bleibt **kanonisch** in `docs/process/fahrplan.md`.
- Dieses Dokument enthält **keine Kopie** des Fahrplans, sondern verweist ausschließlich darauf.

## Konsequenzen

- Anpassungen am Fahrplan erfolgen ausschließlich in der Prozessdokumentation.
- Architekturentscheidungen und weitere Dokumente verlinken auf den Fahrplan über dieses ADR.

## Link

- [Fahrplan in docs/process](../process/fahrplan.md)

## Siehe auch

- [ADR-0003 — Privacy: Unschärferadius & RoN-Platzhalterrolle (v1)](ADR-0003__privacy-unschaerferadius-ron.md)
```

