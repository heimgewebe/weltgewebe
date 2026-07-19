# Weltgewebe – Python Tools

## Schnellstart

```bash
cd tools/py
uv sync --locked
uv run --locked python -c "import yaml; print(yaml.__version__)"
```

## Abhängigkeiten hinzufügen

```bash
uv add <paket>
```

`PyYAML==6.0.2` ist die erste produktiv genutzte Tooling-Abhängigkeit. Das
Lockfile bindet die zugelassenen Distributionsartefakte an SHA-256-Hashes.
Änderungen werden mit der in `toolchain.versions.yml` gepinnten uv-Version
erzeugt und anschließend mit `uv sync --locked` geprüft.
