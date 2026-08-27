#!/usr/bin/env python3
"""Reject new unclassified uses of the retired legacy product identity.

The migration cannot remove every legacy technical identifier at once. This guard
therefore examines only *added lines* relative to an explicit base revision. It
blocks new product-name use and new use of the legacy web host unless the line
is part of the naming-policy documents, a derived documentation artifact, or is
explicitly marked as legacy compatibility.

Derived files under ``docs/_generated/`` are excluded because they are computed
from source documents that are checked separately. Treating their repeated
historical labels as new naming would make a correct source change fail merely
because its indexes were regenerated.

Legacy marker:
    commonthing-naming: legacy

The marker may be on the same line or one of the two immediately preceding lines.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

LEGACY_MARKER = "commonthing-naming: legacy"
POLICY_EXEMPT_PATHS = {
    "docs/deploy/commonthing.naming.md",
    "docs/deploy/weltgewebe.naming.md",
}
DERIVED_EXEMPT_PREFIXES = ("docs/_generated/",)
RETIRED_PRODUCT_PATTERN = re.compile(r"\b" + "Welt" + r"gewebe\b")
LEGACY_WEB_HOST_PATTERN = re.compile(
    r"(?<![@A-Za-z0-9_.-])(?:www\.)?weltgewebe\.net(?=$|[/?:#\s\"'<>`])"
)
FORBIDDEN_PATTERNS = (
    (
        "retired product name",
        RETIRED_PRODUCT_PATTERN,
    ),
    (
        "legacy public web host",
        LEGACY_WEB_HOST_PATTERN,
    ),
)
HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


@dataclass(frozen=True)
class AddedLine:
    path: str
    line_number: int
    text: str


@dataclass(frozen=True)
class Violation:
    path: str
    line_number: int
    reason: str
    text: str


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "git command failed")
    return completed.stdout


def _revision_exists(repo: Path, revision: str) -> bool:
    completed = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", f"{revision}^{{commit}}"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return completed.returncode == 0


def _require_revision(repo: Path, revision: str, source: str) -> str:
    if not revision or set(revision) == {"0"}:
        raise RuntimeError(f"{source} comparison base is empty or invalid")
    if not _revision_exists(repo, revision):
        raise RuntimeError(f"{source} comparison base is unavailable: {revision}")
    return revision


def resolve_base(repo: Path, explicit: str | None) -> str:
    if explicit is not None:
        return _require_revision(repo, explicit.strip(), "explicit")

    env_base = os.environ.get("COMMONTHING_NAMING_BASE", "").strip()
    if env_base:
        return _require_revision(repo, env_base, "environment")

    github_base_ref = os.environ.get("GITHUB_BASE_REF", "").strip()
    if github_base_ref:
        candidate = f"origin/{github_base_ref}"
        if _revision_exists(repo, candidate):
            return candidate
        raise RuntimeError(f"GitHub base ref is unavailable: {candidate}")

    if _revision_exists(repo, "HEAD^"):
        return "HEAD^"

    raise RuntimeError(
        "no comparison base is available; provide --base or COMMONTHING_NAMING_BASE"
    )


def parse_added_lines(diff_text: str) -> list[AddedLine]:
    path: str | None = None
    new_line: int | None = None
    added: list[AddedLine] = []

    for raw in diff_text.splitlines():
        if raw.startswith("+++ "):
            target = raw[4:]
            if target == "/dev/null":
                path = None
            elif target.startswith("b/"):
                path = target[2:]
            else:
                path = target
            new_line = None
            continue

        match = HUNK_RE.match(raw)
        if match:
            new_line = int(match.group(1))
            continue

        if path is None or new_line is None:
            continue

        if raw.startswith("+") and not raw.startswith("+++"):
            added.append(AddedLine(path=path, line_number=new_line, text=raw[1:]))
            new_line += 1
        elif raw.startswith("-") and not raw.startswith("---"):
            continue
        else:
            new_line += 1

    return added


def _marked_legacy(path: str, line_number: int, text: str, loader: Callable[[str], str]) -> bool:
    if LEGACY_MARKER in text.casefold():
        return True

    try:
        lines = loader(path).splitlines()
    except (OSError, UnicodeError):
        return False

    index = max(0, line_number - 1)
    start = max(0, index - 2)
    for candidate in lines[start : index + 1]:
        if LEGACY_MARKER in candidate.casefold():
            return True
    return False


def _is_exempt_path(path: str) -> bool:
    return path in POLICY_EXEMPT_PATHS or path.startswith(DERIVED_EXEMPT_PREFIXES)


def find_violations(
    diff_text: str,
    loader: Callable[[str], str],
) -> list[Violation]:
    violations: list[Violation] = []
    for line in parse_added_lines(diff_text):
        if _is_exempt_path(line.path):
            continue

        for reason, pattern in FORBIDDEN_PATTERNS:
            if not pattern.search(line.text):
                continue
            if _marked_legacy(line.path, line.line_number, line.text, loader):
                continue
            violations.append(
                Violation(
                    path=line.path,
                    line_number=line.line_number,
                    reason=reason,
                    text=line.text.strip(),
                )
            )
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Guard the commonThing naming contract")
    parser.add_argument("--base", help="Git revision used as the comparison base")
    parser.add_argument("--repo", default=".", help="Repository root")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    try:
        base = resolve_base(repo, args.base)
        diff_text = _git(
            repo,
            "diff",
            "--no-ext-diff",
            "--unified=0",
            f"{base}...HEAD",
            "--",
        )
    except RuntimeError as error:
        print(f"commonThing naming guard: {error}", file=sys.stderr)
        return 2

    def loader(path: str) -> str:
        return (repo / path).read_text(encoding="utf-8")

    violations = find_violations(diff_text, loader)
    if violations:
        print("commonThing naming guard failed:", file=sys.stderr)
        for item in violations:
            print(
                f"- {item.path}:{item.line_number}: {item.reason}: {item.text}",
                file=sys.stderr,
            )
        print(
            "Use commonThing for current naming. If this is necessary compatibility, "
            f"annotate it with '{LEGACY_MARKER}'.",
            file=sys.stderr,
        )
        return 1

    print(f"commonThing naming guard passed against {base}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
