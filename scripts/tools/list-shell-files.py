#!/usr/bin/env python3
"""List tracked shell files for linting.

Includes conventional .sh/.bash files and extensionless tracked files with a
shell shebang. Output is NUL-delimited for safe xargs use.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SHELL_SUFFIXES = {".sh", ".bash"}
SHELL_SHEBANG_MARKERS = (b"sh", b"bash")


def is_shell_file(path: Path) -> bool:
    if path.suffix in SHELL_SUFFIXES:
        return True
    try:
        first_line = path.open("rb").readline()
    except OSError:
        return False
    return first_line.startswith(b"#!") and any(marker in first_line for marker in SHELL_SHEBANG_MARKERS)


def main() -> int:
    tracked_files = subprocess.check_output(["git", "ls-files"], text=True).splitlines()
    for filename in tracked_files:
        path = Path(filename)
        if path.is_file() and is_shell_file(path):
            sys.stdout.buffer.write(filename.encode("utf-8") + b"\0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
