# Kurzfassung: Übertragbare Praktiken aus HausKI, semantAH und WGX-Profil
*(X-Repo Learnings → sofort anwendbare Leitplanken für Konsistenz & Qualität)*

- **Semantische Artefakte versionieren:** Ein leichtgewichtiges Graph-Schema (z. B. `nodes.jsonl`/`edges.jsonl`) und eingebettete Cluster-Artefakte direkt im Repo halten, um Beziehungen, Themen und Backlinks portabel zu machen.
- **Terminologie & Synonyme pflegen:** Eine gepflegte Taxonomie (z. B. `synonyms.yml`, `entities.yml`) unterstützt Suche, Filter und konsistente Begriffsnutzung.
- **Governance-Logik messbar machen:** Domänenregeln (**7-Tage** Verblassen, **84-Tage** RoN-Anonymisierung, Delegationsabläufe) über konkrete Metriken, Dashboards und Alerts operationalisieren. → vgl. `docs/zusammenstellung.md`
- **WGX-Profil als Task-SSoT:** Ein zentrales Profil `.wgx/profile.yml` definiert Env-Prioritäten & Standard-Tasks (`up/lint/test/build/smoke`) und vermeidet Drift zwischen lokal & CI.
- **Health/Readiness mit Policies koppeln:** Die bestehenden `/health/live` und `/health/ready` um Policy-Signale (Rate-Limits, Retention, Governance-Timer) ergänzen und in Runbooks verankern.
- **UI/Produkt-Definition testbar machen:** UI-Spezifika (Map-UI, Drawer, Zeitleiste, Knotentypen) als Playwright-/Vitest-Szenarien automatisieren, um Regressionen früh zu erkennen.
- **Föderierung & Archiv-Strategie festigen:** Hybrid-Indexierung durch wiederkehrende Archiv-Validierung, URL-Kanonisierungstests und CI-Jobs absichern.
- **Delegation/Abstimmung operationalisieren:** Policy-Engines und Telemetrie-Events (z. B. `delegation_expired`, `proposal_auto_passed`) etablieren, um Governance-Wirkung zu messen.
- **Kosten-Szenarien als Code umsetzen:** Kostenmodelle (S1–S4) in Versionierung halten und regelmäßige `cost-report.md`-Artefakte in CI erzeugen.
- **Security als Release-Gate durchsetzen:** SBOM, Signaturen, Key-Rotation und CVE-Schwellen als harte CI-Gates etablieren, um Releases zu schützen.

## Nächste Schritte (knapp & machbar)
- [x] `docs/README.md`: Abschnitt **„X-Repo Learnings“** mit Link auf dieses Dokument ergänzen.
- [ ] `.wgx/profile.yml`: Standard-Tasks `up|lint|test|build|smoke` definieren (Repo-SSoT).
- [ ] `/health/ready`: Policy-Signal-Platzhalter ausgeben (z. B. `governance_timer_ok=true`).
- [ ] `ci/`: Playwright-Smoke für Map-UI (1–2 kritische Szenarien) hinzufügen.
- [ ] `ci/`: `cost-report.md` (S1–S4) als regelmäßiges Artefakt erzeugen.
- [ ] `ci/`: SBOM+Signatur+Audit als Gate in Release-Workflow aktivieren.
