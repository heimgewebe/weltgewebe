## contracts-mirror

Dieser Ordner ist ein **validierungsfreundlicher Spiegel** der kanonischen Contracts.
Die Wahrheit liegt im Metarepo (z. B. `metarepo/contracts/...`). Der Mirror hier
stellt nur eine Arbeitskopie für Tests und lokale Validierungen dar.

### Drift-Schutz

Nutze `scripts/contracts-mirror-guard.sh`, um sicherzustellen, dass der Mirror
byte-identisch mit dem Kanon ist:

```bash
CANONICAL_CONTRACTS_DIR=/pfad/zum/metarepo/contracts \
MIRROR_DIR=contracts-mirror/json \
bash ./scripts/contracts-mirror-guard.sh
```

Der Guard bricht mit Exit-Code 1 ab, sobald Dateien fehlen oder voneinander abweichen.
So bleibt sichtbar, wenn der Mirror von der Quelle abdriftet.

> Regel: Änderungen gehören zuerst in den Kanon. Aktualisiere anschließend den Mirror
> (per Sync/Copy) und lass den Guard laufen. PRs, die nur den Mirror verändern,
> ohne den Kanon zu aktualisieren, gelten als drift-gefährdet.
