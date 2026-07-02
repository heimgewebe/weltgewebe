#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from scripts.docmeta.docmeta import REPO_ROOT
from scripts.docmeta.generated_check import write_or_check

OUT_FILE = os.path.join(REPO_ROOT, "docs", "_generated", "change-resonance.md")


def render() -> str:
    return """---
id: docs.generated.change-resonance
title: Change Resonance
doc_type: generated
status: active
summary: Wenn sich X ändert, prüfe oder aktualisiere Y.
---

## Weltgewebe Change Resonance

Generated automatically. Do not edit.

> (Heuristic placeholder)

- **Infra / Compose:** -> Deploy-Doku / Runbooks
- **Workflows:** -> AGENTS.md / Policy-Doku
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare output without rewriting it")
    args = parser.parse_args(argv)
    return write_or_check(OUT_FILE, render(), check=args.check, label=os.path.relpath(OUT_FILE, REPO_ROOT))


if __name__ == "__main__":
    sys.exit(main())
