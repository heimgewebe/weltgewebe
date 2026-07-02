from __future__ import annotations

import difflib
import sys
from pathlib import Path


def write_or_check(path: str | Path, content: str, *, check: bool = False, label: str | None = None) -> int:
    """Write generated content or compare it with the committed file.

    Check mode is intentionally read-only: it never rewrites the target file.
    """
    target = Path(path)
    display = label or str(target)
    if check:
        try:
            existing = target.read_text(encoding="utf-8")
        except FileNotFoundError:
            print(f"ERROR: {display} missing; regenerate it first.", file=sys.stderr)
            return 1
        except UnicodeError as exc:
            print(f"ERROR: {display} unreadable as UTF-8: {exc}", file=sys.stderr)
            return 1
        if existing == content:
            print(f"{display} is up to date.")
            return 0
        diff = "".join(
            difflib.unified_diff(
                existing.splitlines(keepends=True),
                content.splitlines(keepends=True),
                fromfile=str(target),
                tofile=f"{target} (generated)",
            )
        )
        print(f"ERROR: {display} is stale; regenerate it.", file=sys.stderr)
        if diff:
            print(diff[-12000:], file=sys.stderr)
        return 1

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    print(f"Generated {display}")
    return 0
