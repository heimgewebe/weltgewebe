# Leitfaden · Ethik & Systemdesign (Weltgewebe)

**Stand:** 2025-10-06  
**Quelle:** inhalt.md · zusammenstellung.md · geist und plan.md · fahrplan.md · techstack.md

---

## 1 · Zweck

Dieses Dokument verdichtet Geist, Plan und technische Architektur des Weltgewebes zu einer verbindlichen Orientierung für
Entwicklung, Gestaltung und Governance.  
Es beschreibt:
- **Was** ethisch gilt,  
- **Wie** daraus technische und gestalterische Konsequenzen folgen,  
- **Woran** sich Teams bei Entscheidungen künftig messen lassen.

---

## 2 · Philosophie („Geist“)

| Prinzip | Bedeutung | Operative Konsequenz |
|----------|------------|----------------------|
| **Freiwilligkeit** | Keine Handlung ohne bewusste Zustimmung. | Opt-in-Mechanismen, keine versteckten Datenflüsse. |
| **Transparenz** | Alles Sichtbare ist verhandelbar; nichts Geschlossenes. | Offene APIs, nachvollziehbare Governance-Entscheide. |
| **Vergänglichkeit** | Informationen altern sichtbar; kein endloses Archiv. | Zeitliche Sichtbarkeit („Fade-out“), Lösch- und Verblassungsprozesse. |
| **Commons-Orientierung** | Engagement ≠ Geld; Beiträge = Währung. | Spenden (Goldfäden) optional, sonst Ressourcen-Teilung. |
| **Föderation** | Lokale Autonomie + globale Anschlussfähigkeit. | Ortswebereien mit eigenem Konto + föderalen Hooks. |
| **Privacy by Design** | Sichtbar nur freiwillig Eingetragenes. | Keine Cookies / Tracking; RoN-System für Anonymität. |

---

## 3 · Systemlogik („Plan“)

### 3.1 Domänenmodell
| Entität | Beschreibung |
|----------|--------------|
| **Rolle / Garnrolle** | Verifizierter Nutzer (Account) + Position + Privat/Öffentlich-Bereich. |
| **Knoten** | Informations- oder Ereignis-Bündel (Idee, Ressource, Ort …). |
| **Faden** | Verbindung zwischen Rolle ↔ Knoten (Handlung). |
| **Garn** | Dauerhafte, verzwirnte Verbindung = Bestandsschutz. |

### 3.2 Zeit und Prozesse  
- **7-Sekunden-Rotation** → sichtbares Feedback nach Aktion.  
- **7-Tage-Verblassen** → nicht verzwirnte Fäden/Knoten lösen sich auf.  
- **7 + 7-Tage-Modell** → Anträge: Einspruch → Abstimmung.  
- **Delegation (Liquid Democracy)** → verfällt nach 4 Wochen Inaktivität.  
- **RoN-System** → anonymisierte Beiträge nach gewählter Frist.

---

## 4 · Ethisch-technische Defaults

| Bereich | Schlüssel | Richtwert | Herkunft |
|----------|------------|------------|-----------|
| Sichtbarkeit | `fade_days` | 7 Tage laut zusammenstellung.md | Funktionsbeschreibung, nicht Code. |
| Identität | `ron_alias_valid_days` | 28 Tage (Delegations-Analogon) | Geist & Plan-Ableitung. |
| Anonymisierung | `default_anonymized` | *nicht festgelegt*, nur „Opt-in möglich“ | zusammenstellung.md, III Abschnitt. |
| Ortsdaten | `unschaerferadius_m` | individuell einstellbar | zusammenstellung.md, III Abschnitt. |
| Delegation | `delegation_expire_days` | 28 Tage (4 Wochen) | § IV Delegation. |

> **Hinweis:** Die Werte 7/7/28 Tage sind aus der Beschreibung im Repo abgeleitet – nicht normativ festgelegt.  
> Änderungen erfordern Governance-Beschluss + Changelog-Eintrag.

---

## 5 · Governance-Matrix

| Prozess | Dauer | Sichtbarkeit | Trigger |
|----------|--------|---------------|----------|
| Antrag | 7 Tage + 7 Tage | öffentlich | Timer / Einspruch |
| Delegation | 4 Wochen | transparent (gestrichelte Linien) | Inaktivität |
| Meldung / Freeze | 24 h | eingeklappt | Moderations-Vote |
| RoN-Anonymisierung | variable x Tage | „Rolle ohne Namen“ | User-Opt-in |

---

## 6 · Technische Leitplanken (aus techstack.md)

- **Architektur:** Rust API (Axum) + SvelteKit Frontend + PostgreSQL / NATS JetStream (Event-Sourcing).  
- **Monitoring:** Prometheus + Grafana + Loki + Tempo.  
- **Security:** SBOM + cosign + Key-Rotation + DSGVO-Forget-Pipeline.  
- **HA & Cost Control:** Nomad Cluster · PgBouncer · Opex-KPIs < €1 / Session.  
- **Privacy UI (ADR-0003):** RoN-Toggle + Unschärferadius-Slider (ab Phase C).

---

## 7 · Design-Ethik → UX-Richtlinien

1. **Transparente Zeitlichkeit:** Fade-Animationen zeigen Vergänglichkeit, nicht Löschung.  
2. **Partizipative Interface-Metaphern:** Rollen drehen, Fäden fließen – Verantwortung wird sichtbar.  
3. **Reversible Aktionen:** Alles ist änder- oder verzwirnbar, aber nicht heimlich.  
4. **Privacy Controls Front and Center:** Slider / Toggles direkt im Profil.  
5. **Lokale Sichtbarkeit:** Zoom ≈ Vertraulichkeit; Unschärfe nimmt mit Distanz zu.  
6. **Keine versteckte Gamification:** Engagement wird nicht bewertet, nur sichtbar gemacht.

---

## 8 · Weiterer Fahrplan (Querschnitt aus fahrplan.md)

| Phase | Ziel | Ethik-Bezug |
|-------|------|-------------|
| A | Minimal-Web (SvelteKit + Map) | Transparenz sichtbar machen – Karte hallo sagen |
| B | API + Health + Contracts | Nachvollziehbarkeit von Aktionen |
| C | Privacy UI + 7-Tage-Verblassen | Privacy by Design erlebbar machen |
| D | Persistenz + Outbox-Hook | Integrität von Ereignissen |
| … | Langfristig: Föderation + Delegations-Audits | Verantwortung skaliert halten |

---

## 9 · Governance / Changelog-Pflicht

Alle Änderungen an:
- Datenschutz- oder Ethikparametern  
- Governance-Timern  
- Sichtbarkeits-Mechaniken  

→ müssen in `docs/policies/changelog.md` vermerkt und im Webrat veröffentlicht werden.

---

## 10 · Zusammenfassung

> **Das Weltgewebe** ist ein offenes, vergängliches, fälschungssicheres
> Beziehungs-System.  
> Jede Handlung = Event, jedes Event = Faden, jeder Faden = Verantwortung.
> Ethik, Technik und Design greifen ineinander.

---

## Meta

- **Autor (Extraktion):** ChatGPT aus Repo-Docs 2025-10-06  
- **Status:** Draft v1 · Review im Webrat erforderlich  
- **Pfadvorschlag:** `docs/policies/orientierung.md`
