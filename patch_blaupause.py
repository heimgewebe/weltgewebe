import re

path = "docs/blueprints/map-blaupause.md"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

new_strategy = """
## 8. Update- und Publish-Strategie

OSM Updatezyklus:

- **Rhythmus:** Ereignis- oder zeitgetrieben (z. B. monatlich oder bei signifikanten OSM-Diffs/Regionsupdates).
- **Prozess:** Ein Build-Job (z. B. `build-hamburg-pmtiles.sh`) lädt den definierten OSM-Snapshot (gepinnt via SHA256) herunter und erzeugt das PMTiles-Artefakt.

Publish- und Rollback-Strategie (Contract-First):

- **Atomic Switch:** Neue PMTiles-Artefakte (z. B. `basemap-hamburg-v2.pmtiles`) werden zuerst vollständig neben dem aktiven Artefakt in das Zielverzeichnis transferiert.
- **Verifikation (Der Sentinel Contract):** Die Einsatzbereitschaft wird über eine exakt korrespondierende `.meta.json` (z. B. `basemap-hamburg-v2.meta.json`) definiert. Diese Datei darf erst geschrieben werden, nachdem das PMTiles-Artefakt erfolgreich transferiert und geprüft wurde.
  - Das Schema der `.meta.json` **muss** folgende Felder enthalten, um als Contract zu gelten:
    - `version`: Version des Builds
    - `artifact_name`: z. B. "basemap-hamburg-v2.pmtiles"
    - `sha256`: Hash der generierten `.pmtiles` Datei
    - `size_bytes`: Dateigröße
    - `status`: `"ready"` oder `"invalid"`
- **Aktivierung:** Der Symlink-Switch (`ln -sfn basemap-hamburg-v2.pmtiles basemap-current.pmtiles`) darf **ausschließlich** erfolgen, wenn:
  1. Die `.meta.json` existiert und `status == "ready"` ist.
  2. Der `sha256` Hash der echten `.pmtiles` Datei lokal mit der Angabe in der `.meta.json` übereinstimmt (Integrity Check, z. B. durch `weltgewebe-up` oder CI-Job).
  3. Die Datei vollständig ist (`size_bytes` match).
- **Rollback:** Bei Laufzeit-Anomalien wird der Symlink sofort auf die vorherige, intakte Version (z. B. `basemap-hamburg-v1.pmtiles`) zurückgesetzt. Konkrete Rollback-Trigger können sein:
  - Erhöhte HTTP-Fehlerquote (z. B. 404/500 auf der Edge-Route)
  - Fehlgeschlagene Range-Responses (PMTiles Client fordert Bytes an, Server liefert unvollständig)
  - MapLibre Client-Init-Fehler (Sichtbarkeit/Ladezeit überschreitet Timeout)
  Alte Artefakte verbleiben für eine Karenzzeit von mindestens 14 Tagen im Storage.
"""

# Replace the existing section 8
text = re.sub(
    r"## 8\. Update- und Publish-Strategie.*?(?=## 9\. Performance)",
    new_strategy.strip() + "\n\n",
    text,
    flags=re.DOTALL
)

with open(path, "w", encoding="utf-8") as f:
    f.write(text)

print("Patched map-blaupause.md")
