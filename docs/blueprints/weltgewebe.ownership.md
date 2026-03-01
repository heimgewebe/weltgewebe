# Blueprint: Docmeta System Evolution

## B1) Doc Ownership / Governance

- Frontmatter-Feld `organ`: einführen (Architektur-Semantik, z. B. governance, runtime, deploy).
- *Hinweis:* Personale Ownership und `CODEOWNERS` werden im Solo-Setup nicht genutzt und
  explizit ausgesetzt. Die Steuerung erfolgt ausschließlich über Architektur-Semantik (`organ`).

## B2) Graph-Intelligenz / Review-Impact

- `depends_on` als Graph auswerten.
- "Review impact" ausgeben: Bei Änderung von Doc A → markiere abhängige Docs als
  `needs_review` (oder generiere einen Report).

## B3) Review-Workflow Komfort

- Skript `scripts/docmeta/touch_last_reviewed.py` (manuell aufrufbar) zum Setzen oder
  Aktualisieren des Feldes `last_reviewed`.

## B4) Link-Checker

- Interne Markdown-Links in canonical Docs prüfen (existierende Ziele, Anker optional).

## B5) Schema/Contract (hart, aber sauber)

- `contracts/docmeta.schema.json` definieren.
- Validation per JSON-Schema einführen (ggf. separiert, wenn Abhängigkeiten wie PyYAML
  oder jsonschema eingeführt werden).
  *Achtung:* Python Tooling für das Repository muss nach Möglichkeit dependency-free
  bleiben (gemäß bestehender Speicher-Richtlinien).

## B6) DX / Tooling

- `make docs-guard` (oder äquivalent) als Single-Source-of-Truth für CI/lokale Checks hinzufügen.
- WGX-Hook: `wgx guard docs` bzw. Forwarder-Integration (Heimgewebe-Style).

## B7) SYSTEM_MAP Erweiterungen

- `verifies_with` in der `SYSTEM_MAP.md` ausgeben.
- "Freshness"-Ampel nach Policy (warn/fail, basierend auf den Tagen seit dem letzten Review).
- "Missing scripts"-Ampel (Checks, die in `verifies_with` referenziert sind, aber im
  Dateisystem fehlen).

---

## C) Optionaler Extra-PR (Integrationstests & Strictness)

*Hinweis: Nur implementieren, wenn Integrationstests zwingend erforderlich sind.*

- Env-Overrides: `REPO_INDEX_PATH`, `REVIEW_POLICY_PATH` bereitstellen, um echte
  Integrationstests hermetisch zu ermöglichen.
- Strict-Manifest: Unbekannte Keys im Manifest/Frontmatter führen zum Abbruch (fail-closed).
- End-to-end Test: `mode=fail` + fehlendes `last_reviewed` → Exit 1.
- `manifest/review-policy.yaml`: Die Strictness-Policy (`strict_manifest`) dokumentieren.
- `generate_system_map`: Spaltenbreiten/Width-Calc kosmetisch anpassen: Link-Texte strippen
  und Diff-Noise minimieren (kein dynamisches Padding in Markdown-Tabellen).
