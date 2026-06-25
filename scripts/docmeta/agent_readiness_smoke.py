from __future__ import annotations

from subprocess import CompletedProcess

SMOKE_MARKER = "handoff-readiness-smoke:valid"


def smoke_succeeded(run: CompletedProcess[str]) -> bool:
    return run.returncode == 0 and run.stdout.strip() == SMOKE_MARKER
