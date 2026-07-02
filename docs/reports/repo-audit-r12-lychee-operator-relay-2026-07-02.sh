#!/usr/bin/env bash
set -euo pipefail

git rm .lychee.toml
python3 - <<'PY'
from pathlib import Path
p = Path('.github/workflows/ci.yml')
s = p.read_text(encoding='utf-8')
s = s.replace("${{ runner.os }}-lychee-${{ hashFiles('**/*.md', '.lychee.toml') }}", "${{ runner.os }}-lychee-${{ hashFiles('**/*.md') }}")
p.write_text(s, encoding='utf-8')
PY
