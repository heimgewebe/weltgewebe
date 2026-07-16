#!/usr/bin/env python3
"""Update the contract test anchor before the final PR #1445 patch run."""

from pathlib import Path

path = Path(__file__).parents[2] / "scripts/ci/tests/test_production_reconciler_contract.py"
text = path.read_text(encoding="utf-8")
old = "        public_readback = script.index('api_body=\"$(curl', deploy)\n"
new = "        public_readback = script.index('api_body_file=\"$(mktemp', deploy)\n"
if text.count(old) != 1:
    raise SystemExit("expected exactly one legacy public readback anchor")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
