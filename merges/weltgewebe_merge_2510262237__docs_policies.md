### 📄 docs/policies/orientierung.md

**Größe:** 5 KB | **md5:** `1f169aa5b19f0c555c669faaff7bf2d1`

```markdown
# Leitfaden · Ethik & Systemdesign (Weltgewebe)

**Stand:** 2025-10-06
**Quelle:**

- [inhalt.md](../overview/inhalt.md)
- [zusammenstellung.md](../overview/zusammenstellung.md)
- [geist-und-plan.md](../geist-und-plan.md)
- [fahrplan.md](../process/fahrplan.md)
- [techstack.md](../techstack.md)

---

## 1 · Zweck

Dieses Dokument verdichtet Geist, Plan und technische Architektur des Weltgewebes zu einer
verbindlichen Orientierung für
Entwicklung, Gestaltung und Governance.
Es beschreibt:

- **Was** ethisch gilt.
- **Wie** daraus technische und gestalterische Konsequenzen folgen.
- **Woran** sich Teams bei Entscheidungen künftig messen lassen.

---

## 2 · Philosophie („Geist“)

- **Freiwilligkeit**
  - Bedeutung: Keine Handlung ohne bewusste Zustimmung.
  - Operative Konsequenz: Opt-in-Mechanismen, keine versteckten Datenflüsse.
- **Transparenz**
  - Bedeutung: Alles Sichtbare ist verhandelbar; nichts Geschlossenes.
  - Operative Konsequenz: Offene APIs, nachvollziehbare Governance-Entscheide.
- **Vergänglichkeit**
  - Bedeutung: Informationen altern sichtbar; kein endloses Archiv.
  - Operative Konsequenz: Zeitliche Sichtbarkeit („Fade-out“), Lösch- und Verblassungsprozesse.
- **Commons-Orientierung**
  - Bedeutung: Engagement ≠ Geld; Beiträge = Währung.
  - Operative Konsequenz: Spenden (Goldfäden) optional, sonst Ressourcen-Teilung.
- **Föderation**
  - Bedeutung: Lokale Autonomie + globale Anschlussfähigkeit.
  - Operative Konsequenz: Ortswebereien mit eigenem Konto + föderalen Hooks.
- **Privacy by Design**
  - Bedeutung: Sichtbar nur freiwillig Eingetragenes.
  - Operative Konsequenz: Keine Cookies/Tracking; RoN-System für Anonymität.

---

## 3 · Systemlogik („Plan“)

### 3.1 Domänenmodell

- **Rolle / Garnrolle**
  - Beschreibung: Verifizierter Nutzer (Account) + Position + Privat-/Öffentlich-Bereich.
- **Knoten**
  - Beschreibung: Informations- oder Ereignis-Bündel (Idee, Ressource, Ort …).
- **Faden**
  - Beschreibung: Verbindung zwischen Rolle und Knoten (Handlung).
- **Garn**
  - Beschreibung: Dauerhafte, verzwirnte Verbindung = Bestandsschutz.

### 3.2 Zeit und Prozesse

- **7-Sekunden-Rotation** → sichtbares Feedback nach Aktion.
- **7-Tage-Verblassen** → nicht verzwirnte Fäden/Knoten lösen sich auf.
- **7 + 7-Tage-Modell** → Anträge: Einspruch → Abstimmung.
- **Delegation (Liquid Democracy)** → verfällt nach 4 Wochen Inaktivität.
- **RoN-System** → anonymisierte Beiträge nach gewählter Frist.

---

## 4 · Ethisch-technische Defaults

- Sichtbarkeit (`fade_days`)
  - Richtwert: 7 Tage laut zusammenstellung.md.
  - Herkunft: Funktionsbeschreibung, nicht Code.
- Identität (`ron_alias_valid_days`)
  - Richtwert: 28 Tage (Delegations-Analogon).
  - Herkunft: Geist & Plan-Ableitung.
- Anonymisierung (`default_anonymized`)
  - Richtwert: *nicht festgelegt*, nur „Opt-in möglich“.
  - Herkunft: zusammenstellung.md, Abschnitt III.
- Ortsdaten (`unschaerferadius_m`)
  - Richtwert: individuell einstellbar.
  - Herkunft: zusammenstellung.md, Abschnitt III.
- Delegation (`delegation_expire_days`)
  - Richtwert: 28 Tage (4 Wochen).
  - Herkunft: § IV Delegation.

> **Hinweis:** Die Werte 7/7/28 Tage sind aus der Beschreibung im Repo abgeleitet – nicht normativ festgelegt.
> Änderungen erfordern Governance-Beschluss + Changelog-Eintrag.

---

## 5 · Governance-Matrix

- Antrag
  - Dauer: 7 Tage + 7 Tage.
  - Sichtbarkeit: öffentlich.
  - Trigger: Timer oder Einspruch.
- Delegation
  - Dauer: 4 Wochen.
  - Sichtbarkeit: transparent (gestrichelte Linien).
  - Trigger: Inaktivität.
- Meldung / Freeze
  - Dauer: 24 h.
  - Sichtbarkeit: eingeklappt.
  - Trigger: Moderations-Vote.
- RoN-Anonymisierung
  - Dauer: variable x Tage.
  - Sichtbarkeit: „Rolle ohne Namen“.
  - Trigger: User-Opt-in.

---

## 6 · Technische Leitplanken (aus techstack.md)

- **Architektur:** Rust API (Axum) + SvelteKit Frontend + PostgreSQL / NATS JetStream
  (Event-Sourcing).
- **Monitoring:** Prometheus + Grafana + Loki + Tempo.
- **Security:** SBOM + cosign + Key-Rotation + DSGVO-Forget-Pipeline.
- **HA & Cost Control:** Nomad Cluster · PgBouncer · Opex-KPIs < €1 / Session.
- **Privacy UI (ADR-0003):** RoN-Toggle + Unschärferadius-Slider (ab Phase C).

---

## 7 · Design-Ethik → UX-Richtlinien

1. **Transparente Zeitlichkeit:** Fade-Animationen zeigen Vergänglichkeit, nicht Löschung.
2. **Partizipative Interface-Metaphern:** Rollen drehen, Fäden fließen – Verantwortung wird
   sichtbar.
3. **Reversible Aktionen:** Alles ist änder- oder verzwirnbar, aber nicht heimlich.
4. **Privacy Controls Front and Center:** Slider / Toggles direkt im Profil.
5. **Lokale Sichtbarkeit:** Zoom ≈ Vertraulichkeit; Unschärfe nimmt mit Distanz zu.
6. **Keine versteckte Gamification:** Engagement wird nicht bewertet, nur sichtbar gemacht.

---

## 8 · Weiterer Fahrplan (Querschnitt aus fahrplan.md)

- Phase A
  - Ziel: Minimal-Web (SvelteKit + Map).
  - Ethik-Bezug: Transparenz sichtbar machen – Karte hallo sagen.
- Phase B
  - Ziel: API + Health + Contracts.
  - Ethik-Bezug: Nachvollziehbarkeit von Aktionen.
- Phase C
  - Ziel: Privacy UI + 7-Tage-Verblassen.
  - Ethik-Bezug: Privacy by Design erlebbar machen.
- Phase D
  - Ziel: Persistenz + Outbox-Hook.
  - Ethik-Bezug: Integrität von Ereignissen.
- Phase …
  - Ziel: Langfristig Föderation + Delegations-Audits.
  - Ethik-Bezug: Verantwortung skaliert halten.


## 9 · Governance / Changelog-Pflicht

Alle Änderungen an:

- Datenschutz- oder Ethikparametern.
- Governance-Timern.
- Sichtbarkeits-Mechaniken.
```

