# Heimserver Naming Policy

## These / Antithese / Synthese

**These:**
Deine Policy ist eindeutig: zwei getrennte Organismen, zwei getrennte Namensräume (*.heimgewebe.home.arpa vs *.weltgewebe.home.arpa).
Alles, was leitstand.heimgewebe… in einem „weltgewebe“-Stack auftauchen lässt, ist Drift und erzeugt genau den TLS/DNS-Splitbrain, den du beschreibst.

**Antithese:**
Man kann argumentieren: „Ist doch egal, Hauptsache es läuft auf dem Heimserver.“
Das stimmt nur kurzfristig; langfristig wird „egal“ zur Fehlerklasse („falsches Cert“, „falscher Host“, „falsches Repo“).

**Synthese:**
Wir machen Bereinigung als Contract:

1. Heimgewebe-Domains nur für Heimgewebe-Services.
2. Weltgewebe-Domains nur für Weltgewebe-Services.
3. Caddy bindet strikt pro FQDN.
4. DNS hat genau eine Quelle.
5. Optionale Übergangsphase nur als expliziter Redirect/Alias — nie still.

---

## Klarstellung zur Altlast

Mit „Altlast“ meinte ich: Der Pfad /opt/weltgewebe und Container-Namen wie weltgewebe-api können historisch/zufällig sein, ohne dass sie semantisch zu Heimgewebe gehören.
Das ist eine typische Drift-Falle: Labels (Ordner/Service-Namen) erzeugen eine falsche Wirklichkeit im Kopf.
Deine Policy zwingt jetzt die Korrektur: Semantik bestimmt Routing, nicht der Ordnername.

---

## Entscheidung

Wir ziehen das hart auseinander:

* **Heimgewebe:** `leitstand.heimgewebe.home.arpa`, `api.heimgewebe.home.arpa`, optional `heimgewebe.home.arpa`
* **Weltgewebe:** analog `weltgewebe.home.arpa` als optionales Root, plus `api.weltgewebe.home.arpa` etc. (nur wenn Weltgewebe überhaupt eine API hat)

Keine Kreuzung, kein „shared“ Host.

---

## Doku-Korrektur: .home vs .home.arpa

* „Kein .home als TLD“ (weil nicht reserviert)
* „.home.arpa ist kanonisch“ (RFC 8375)
