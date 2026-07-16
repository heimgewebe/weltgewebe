#!/usr/bin/env python3
"""Refine PR #1445 PAX handling to allow only bounded numeric mtime metadata."""

from pathlib import Path

path = Path(__file__).parents[2] / "scripts/ops/validate_web_deploy_archive.py"
text = path.read_text(encoding="utf-8")
replacements = [
    (
        "import os\nimport sys\nimport tarfile\n",
        "import os\nimport re\nimport sys\nimport tarfile\n",
    ),
    (
        "DEFAULT_MAX_DEPTH = 32\nREQUIRED_REGULAR_FILES",
        "DEFAULT_MAX_DEPTH = 32\nALLOWED_MEMBER_PAX_HEADERS = frozenset({\"mtime\"})\nPAX_TIME_RE = re.compile(r\"^-?[0-9]+(?:\\\\.[0-9]+)?$\")\nREQUIRED_REGULAR_FILES",
    ),
    (
        '''                if member.pax_headers:\n                    raise ArchiveValidationError(\n                        f"archive member has unsupported pax headers: {canonical}"\n                    )\n''',
        '''                unsupported_pax = (\n                    set(member.pax_headers) - ALLOWED_MEMBER_PAX_HEADERS\n                )\n                if unsupported_pax:\n                    raise ArchiveValidationError(\n                        "archive member has unsupported pax headers: "\n                        f"{canonical}: {sorted(unsupported_pax)!r}"\n                    )\n                pax_mtime = member.pax_headers.get("mtime")\n                if pax_mtime is not None and (\n                    len(pax_mtime) > 64 or not PAX_TIME_RE.fullmatch(pax_mtime)\n                ):\n                    raise ArchiveValidationError(\n                        f"archive member has invalid pax mtime: {canonical}"\n                    )\n''',
    ),
]
for old, new in replacements:
    if text.count(old) != 1:
        raise SystemExit(f"expected exactly one PAX refinement anchor: {old[:40]!r}")
    text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
