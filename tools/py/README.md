# Weltgewebe – Python Tools

## Schnellstart

```bash
uv sync --project tools/py --locked
uv run --project tools/py --locked python -c "import yaml; print(yaml.__version__)"
```

Repo-kanonische Aufrufe (Make, Just, CI) lauten immer:

```bash
uv run --project tools/py --locked python -m scripts.agent.validate_agent_tooling_lock
make agent-contract-check   # gleiche Semantik
make validate               # Agent-/Vertrags-/Plattform-Python über denselben Pfad
```

## Abhängigkeiten hinzufügen

```bash
uv add <paket>
```

`PyYAML==6.0.2` ist die erste produktiv genutzte Tooling-Abhängigkeit. Das
Lockfile bindet die zugelassenen Distributionsartefakte an SHA-256-Hashes.
Änderungen werden mit der in `toolchain.versions.yml` gepinnten uv-Version
erzeugt und anschließend mit `uv sync --locked` geprüft.
