# Heimserver Naming Policy

## 1. Zweck

Vermeidung von Split-Brain-Situationen zwischen DNS, TLS und Container-Routing.
Dieses Dokument definiert den normativen Contract für die Benennung von Diensten auf dem Heimserver.

## 2. Begriffe

* **Heimgewebe:** Organismus aus Repositories (lokale Dienste, keine Zwecke).
* **Weltgewebe:** Kartenbasiertes Common-Interface (kein eigener Organismus).

## 3. Normative Regeln

1. **Heimgewebe-Domains** verweisen ausschließlich auf Heimgewebe-Services.
2. **Weltgewebe-Domains** verweisen ausschließlich auf Weltgewebe-Services.
3. **Caddy** bindet strikt pro FQDN (keine Wildcards, keine impliziten Defaults).
4. **DNS** hat genau eine autoritative Quelle.
5. **Optionale Übergangsphasen** erfolgen nur als expliziter Redirect/Alias — niemals stillschweigend.
6. **.home vs .home.arpa:** `.home` ist als TLD nicht zulässig (da nicht reserviert). `.home.arpa` ist kanonisch (RFC 8375).

---

## 4. Kanonische Domains

Die Zuordnung erfolgt strikt nach Semantik:

### Heimgewebe

* `leitstand.heimgewebe.home.arpa` (sofern provisioniert)
* `api.heimgewebe.home.arpa`
* `heimgewebe.home.arpa` (optional)

### Weltgewebe

* `weltgewebe.home.arpa` (optional)
* `api.weltgewebe.home.arpa` (optional, nur sofern existent)

Keine Kreuzung der Namensräume. Kein „shared“ Host.

---

## 5. Drift-Falle: Label ≠ Semantik

Historische Pfade (z.B. `/opt/weltgewebe`) oder Container-Namen (z.B. `weltgewebe-api`) können irreführend sein und müssen
nicht der semantischen Zugehörigkeit entsprechen.
Die Policy erzwingt eine Korrektur: Die Semantik bestimmt das Routing, nicht der Ordner- oder Service-Name.
Labels erzeugen oft eine falsche Wirklichkeit; dieser Contract gilt vorrangig.
Wenn Label und Semantik kollidieren, sind Labels zu bereinigen (rename/alias), nicht Semantik umzudeuten.
