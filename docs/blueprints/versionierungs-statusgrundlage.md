---
id: versionierungs-statusgrundlage
title: "Weltgewebe – Versionierungs-Statusgrundlage"
doc_type: blueprint
status: active
canonicality: normative
summary: "Belastbare Arbeitsgrundlage und Ist-Stand-Dokumentation für alle Folgeschritte zur Weltgewebe-Versionierung."
---

# Weltgewebe – Versionierungs-Statusgrundlage

## 1. Ziel und Zweck

Dieses Dokument dient als belastbare, repo-belegte Ist-Stand-Analyse der Weltgewebe-Deploy-Versionierung. Es beendet den Zyklus aus isolierten Patches und unkoordinierten Reparaturen, indem es eine präzise Bestandsaufnahme liefert. Es ist die kanonische Arbeitsgrundlage für den nächsten, fokussierten PR zur sauberen Durchsetzung der Versionierungsverträge (Cache-Guards, Caddy-Header, Testsemantik).

## 2. Repo-belegter Ist-Stand

### 2.1 Build / version.json

- **Erzeugung:** `apps/web/scripts/generate-version.js` erzeugt die Datei `build/_app/version.json`.
- **Schema:** Das Skript schreibt ein JSON mit den Feldern `version` (Short SHA oder Commit, Fallback "unknown"), `build_id` (Short SHA + Timestamp, Fallback "unknown-Timestamp"), `built_at` (ISO Timestamp) und optional `commit`.
- **Kanonisches Feld:** Im Skript wird `version` explizit als "Canonical artifact ID (deterministic)" deklariert.

### 2.2 Caddy / Cache

- **Caddyfile:** `infra/caddy/Caddyfile.heim` trennt zwischen `/_app/immutable/*` (Header `public, max-age=31536000, immutable`) und dem Rest via try_files (Header `no-cache, must-revalidate`).
- **Fehlende Regel:** Es existiert aktuell **kein** separater Block für `/_app/version.json`. Die Datei wird daher implizit mit `no-cache, must-revalidate` ausgeliefert, anstatt mit dem laut Blueprint (`versionierungs-blaupause.md`) geforderten `no-store`.

### 2.3 weltgewebe-up / Guards

- **Frontend Guard:** `scripts/weltgewebe-up` prüft harte Cache-Regeln für HTML (`no-cache, must-revalidate`) und Immutable Assets (`max-age=31536000, immutable`).
- **version.json Guard:** Die Überprüfung von `/_app/version.json` in `weltgewebe-up` (Phase B) ist aktuell **warn-only** ("This is a diagnostic guard (warn-only), curl failures should not abort the deploy."). Fehler bei der JSON-Validierung oder Erreichbarkeit führen nicht zum Abbruch (Exit 1).
- **REQUIRE_FRONTEND:** Wird im Skript abgefragt (`if [[ -n "$REQUIRE_FRONTEND" ]] ...`), aber die strikte Validierung auf exakt `0` oder `1` (wie in der Blaupause gefordert) ist rudimentär, fehlerhafte Werte crashen das Skript aktuell nicht immer zwingend hart mit Fehlerabbruch vor der Guard-Ausführung. In Test 22 wird es als Override zur Erzwingung der Tests verwendet.

### 2.4 UI-Diagnose

- **Implementierung:** `apps/web/src/lib/components/VersionDiagnostics.svelte` und zugehörige Tests (`apps/web/tests/version-diagnostics.spec.ts`) sind **bereits vollständig umgesetzt**.
- **Begriffsverwendung:** Die UI sucht primär nach `version` (oder Fallback `commit`/`build`) als kanonische Identität ("Version abc1234"). `build_id` wird als sekundärer Kontext ("Build abc1234-174...") angezeigt.
- **Cache:** Das UI fetched die Datei explizit mit `{ cache: 'no-store' }`.

### 2.5 Tests

- **Test-Skript:** `scripts/tests/test_verify_deployment.sh` enthält Test 22 für "Cache Guards Logic".
- **Vorhandene Tests:**
  - `22a` (Missing HTML Cache Header) -> Negativtest.
  - `22b` (Missing Asset Cache Header) -> Negativtest.
  - `22c` (Valid Cache Headers) -> Positivtest (Prüft den positiven Pfad inkl. mock für `version.json`).
- **Fehlende Tests:** Die in der Blaupause (`versionierungs-blaupause.md`) erwähnten Negativtests `22d` (`version.json` ohne `no-store`) und `22e` (`version.json` erreichbar, aber ohne brauchbare Build-ID) fehlen komplett.

## 3. Kanonische Begriffe

- **version:** Die kanonische, deterministische Artefakt-ID (i.d.R. der Git-Commit oder Short-SHA). Identifiziert *was* gebaut wurde.
- **build_id:** Ein volatiler Bezeichner für den spezifischen CI-/Build-Lauf (z.B. `<sha>-<timestamp>`). Identifiziert *wann/wie* es gebaut wurde. **Achtung:** `version.json` enthält beides.
- **built_at:** ISO-Timestamp des Build-Zeitpunkts.
- **version.json:** Die maschinenlesbare JSON-Diagnosequelle (`/_app/version.json`), die diese Metadaten zur Laufzeit verfügbar macht.
- **Cache-Control:** HTTP-Header zur Steuerung des Caching-Verhaltens.
- **REQUIRE_FRONTEND:** Eine Umgebungsvariable, die explizit steuert, ob Frontend-Guards durchgesetzt werden. Gültige Werte sind ausschließlich `0` (deaktiviert) oder `1` (erzwungen). Aktuell wird diese Striktheit in `weltgewebe-up` noch nicht durchgängig durchgesetzt.

## 4. Vertragsmatrix

| Artefakt / Feld | Produzent | Konsument | Erwartete Semantik | Aktueller Status | Drift-Risiko |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `version.json.version` | `generate-version.js` | UI, `weltgewebe-up` | Kanonische ID | Implementiert & konsistent | Niedrig |
| `version.json.build_id` | `generate-version.js` | UI, `weltgewebe-up` | Volatile CI Run ID | Implementiert & konsistent | Niedrig |
| Caddy Cache-Control für `/_app/version.json` | `Caddyfile.heim` | Browser, `weltgewebe-up` | `no-store` | **Fehlt** (fällt auf `no-cache, must-revalidate` zurück) | **Hoch** (Browser könnte veraltete JSON-Daten nutzen) |
| `weltgewebe-up` Frontend Guard für `version.json` | `weltgewebe-up` | CI/CD | Harter Fehler bei Fehlen oder invalidem JSON | **Warn-only** | **Hoch** (Fehlerhafte Deployments gehen durch) |
| UI-Diagnoseanzeige | `VersionDiagnostics.svelte` | Benutzer | Zeigt `version` primär, `build_id` sekundär | Fertig (fetched mit `no-store`) | Niedrig |
| Deploy-Tests (22a, 22b, 22c) | `test_verify_deployment.sh` | CI/CD | Absicherung der Cache-Header | Implementiert | Mittel |
| Deploy-Tests (22d, 22e) | `test_verify_deployment.sh` | CI/CD | Absicherung von `version.json` Constraints | **Fehlen** | **Hoch** (Keine Testabdeckung für die harte Guard-Logik) |

## 5. Testklassifikation

- **22a: Missing HTML Cache Header**
  - *Typ:* Negativtest (Erwarteter Exit != 0)
  - *Verhalten:* Simuliert fehlende `no-cache, must-revalidate` Header für `/map`. Schlägt korrekt fehl.
- **22b: Missing Asset Cache Header**
  - *Typ:* Negativtest (Erwarteter Exit != 0)
  - *Verhalten:* Simuliert fehlende `immutable` Header für Assets. Schlägt korrekt fehl.
- **22c: Valid Cache Headers (Positive Path)**
  - *Typ:* Positivtest (Erwarteter Exit 0)
  - *Verhalten:* Simuliert korrekte Header für HTML und Assets sowie eine gültige `version.json`-Antwort. Geht erfolgreich durch.
- **22d: version.json ohne no-store**
  - *Typ:* Geplanter Negativtest
  - *Status:* **Fehlt** in `test_verify_deployment.sh`.
- **22e: version.json ohne brauchbare Build-ID**
  - *Typ:* Geplanter Negativtest
  - *Status:* **Fehlt** in `test_verify_deployment.sh`.

## 6. Offene Widersprüche / epistemische Leerstellen

- **Widerspruch Caddy vs. Blueprint:** Laut `versionierungs-blaupause.md` muss `/_app/version.json` zwingend den Header `Cache-Control: no-store` erhalten. Dies ist in `Caddyfile.heim` nicht umgesetzt.
- **Widerspruch weltgewebe-up vs. Blueprint:** Die Blaupause fordert einen "harten Fehler" bei fehlerhaftem `version.json` ("weltgewebe-up darf Frontend-Erfolg nicht mehr nur implizit an HTML/Assets festmachen"). Der aktuelle Code in `weltgewebe-up` deklariert die Überprüfung jedoch explizit als "warn-only".
- **Widerspruch Test-Semantik vs. Blueprint:** Die in der Blaupause geforderten Tests `22d` und `22e` zur Absicherung der harten `version.json` Guards fehlen im Testskript, obwohl die Blaupause sie als Bedingung für das Stop-Kriterium von Phase D nennt.
- **Unklarheit REQUIRE_FRONTEND:** Die Blaupause definiert, dass bei Setzen von `REQUIRE_FRONTEND` nur `0` oder `1` erlaubt sind und alles andere zum "fail fast" führen muss. Der Code in `weltgewebe-up` prüft dies nicht ausreichend strikt.

### Beantwortung der Kernfragen

1. **Ist version aktuell kanonisch oder build_id?**
   `version` ist kanonisch. `generate-version.js` und `VersionDiagnostics.svelte` behandeln `version` konsistent als die primäre, deterministische Artefakt-ID.
2. **Ist das aktuelle Schema wirklich konsistent zwischen den Dateien?**
   Ja, das Schema (Fokus auf `version`, sekundär `build_id`/`built_at`) ist zwischen Generator, UI und Blaupause konsistent. Lediglich der Infrastruktur-Code (`Caddyfile.heim`, `weltgewebe-up`) setzt die daraus resultierenden *Verträge* (`no-store`, hartes Failen) noch nicht durch.
3. **Ist REQUIRE_FRONTEND heute eine saubere Override-Schnittstelle oder nur pragmatischer Testhebel?**
   Aktuell eher ein pragmatischer Hebel. Die "fail fast"-Validierung auf exakt `0` oder `1` (wie dokumentiert) fehlt.
4. **Welche Tests rund um 22c/22d/22e sind logisch korrekt benannt und welche nicht?**
   `22c` ist korrekt als Positivtest. `22d` und `22e` fehlen aktuell komplett und können daher nicht bewertet werden.
5. **Ist die UI-Diagnose inhaltlich schon „fertig genug“, sodass PR 2 im Wesentlichen als erledigt gelten kann?**
   Ja, die UI-Komponente ist vollständig implementiert, abgetestet und erfüllt die Anforderungen von Phase E der Blaupause.

## 7. Empfohlener nächster Schritt

### Fokus-PR: Härtung des version.json Vertrags in Infrastruktur und Tests

Der nächste PR sollte exakt und ausschließlich diese drei zusammenhängenden Punkte lösen:

1. `infra/caddy/Caddyfile.heim`: Ergänzen einer spezifischen Regel für `/_app/version.json` mit `Cache-Control "no-store"`.
2. `scripts/weltgewebe-up`: Umwandeln der aktuellen `warn-only` Phase B (version.json Verify) in harte Checks (Exit 1 bei Fehler/Fehlen), inkl. Prüfung auf den neuen `no-store` Header.
3. `scripts/tests/test_verify_deployment.sh`: Hinzufügen der fehlenden Negativtests `22d` (fehlender no-store Header) und `22e` (invalides JSON/fehlende Version).

**Begründung:** Die UI und das Generator-Skript sind bereits konsistent und fertig. Die Lücke klafft rein auf Infrastruktur- und Test-Ebene. Dieser Schritt schließt die Lücke minimal-invasiv, ohne neue Features anzufassen, und etabliert die harte Garantie, die für alle weiteren Schritte (wie Browser-Self-Update) zwingend nötig ist.
