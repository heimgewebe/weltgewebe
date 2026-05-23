#!/usr/bin/env python3
"""Parse a version.json file and write canonical fields to stdout.

Usage:
    python3 parse-version-json.py <file>

Exit codes:
    0  valid JSON, 'version' present and non-blank
    2  valid JSON but 'version' missing, blank, or wrong type
    3  not valid JSON
    1  unexpected runtime error

Stdout on exit 0 (one field per line, empty string when field absent):
    line 1  version
    line 2  build_id
    line 3  commit
"""
import sys
import json


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: parse-version-json.py <file>", file=sys.stderr)
        sys.exit(1)

    try:
        with open(sys.argv[1]) as fh:
            data = json.load(fh)
    except json.JSONDecodeError:
        sys.exit(3)
    except Exception:
        sys.exit(1)

    try:
        v = data.get("version")
        if not isinstance(v, str) or not v.strip():
            sys.exit(2)
        print(v.strip())
        print(data.get("build_id", ""))
        print(data.get("commit", ""))
    except Exception:
        sys.exit(1)


main()
