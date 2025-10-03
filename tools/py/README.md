# Weltgewebe – Python Tools

## Schnellstart

```bash
cd tools/py
uv sync        # erstellt venv, installiert deps (aktuell leer)
uv run python -V
```

## Abhängigkeiten hinzufügen

```bash
uv add ruff black
```

Das erzeugt/aktualisiert `uv.lock` – damit sind Builds in CI reproduzierbar.
