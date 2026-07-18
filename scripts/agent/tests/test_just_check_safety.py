"""Tests for the write-free safety of the `check` recipe in Justfile."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from scripts.docmeta.docmeta import REPO_ROOT


JUST_RECIPE = re.compile(r"^([a-z][a-z0-9_-]*):(?:\s+[^#]+)?(?:\s+#.*)?$")
JUST_CALL = re.compile(r"^just\s+([a-z][a-z0-9_-]*)(?:\s|$)")
SOFT_FAILURE = re.compile(r"\|\|\s*(?:true\b|:\s*(?:$|;)|echo\b)")


def parse_recipes(content: str) -> dict[str, list[str]]:
    recipes: dict[str, list[str]] = {}
    current: str | None = None

    for raw_line in content.splitlines():
        if raw_line and not raw_line[0].isspace():
            match = JUST_RECIPE.fullmatch(raw_line)
            current = match.group(1) if match else None
            if current is not None:
                recipes[current] = []
            continue
        if current is not None and raw_line.startswith(("\t", " ")):
            recipes[current].append(raw_line.strip())

    return recipes


def reachable_recipes(recipes: dict[str, list[str]], root: str) -> list[str]:
    pending = [root]
    visited: list[str] = []

    while pending:
        name = pending.pop(0)
        if name in visited:
            continue
        if name not in recipes:
            raise AssertionError(f"Referenced Just recipe is missing: {name}")
        visited.append(name)
        for line in recipes[name]:
            command = line.split("#", 1)[0].strip()
            match = JUST_CALL.match(command)
            if match and match.group(1) not in visited:
                pending.append(match.group(1))

    return visited


class TestJustCheckSafety(unittest.TestCase):
    def test_just_check_is_write_free_and_fail_closed(self):
        justfile_path = Path(REPO_ROOT) / "Justfile"
        self.assertTrue(justfile_path.is_file(), "Justfile is missing")

        recipes = parse_recipes(justfile_path.read_text(encoding="utf-8"))
        reachable = reachable_recipes(recipes, "check")
        self.assertIn("check-demo-data", reachable)
        self.assertIn("contracts-domain-check", reachable)
        self.assertIn("agent-contract-check", reachable)

        has_cargo_fmt_check = False
        for recipe_name in reachable:
            for raw_line in recipes[recipe_name]:
                line = raw_line.split("#", 1)[0].strip()
                if not line:
                    continue

                self.assertIsNone(
                    SOFT_FAILURE.search(line),
                    f"{recipe_name} hides a mandatory check failure: {line}",
                )
                self.assertNotIn(
                    "set +e", line, f"{recipe_name} disables fail-closed execution"
                )
                self.assertNotIn(
                    "just fmt", line, "just fmt found in check path (mutates sources)"
                )

                if "cargo fmt" in line:
                    self.assertIn(
                        "--check", line, "cargo fmt without --check found in check path"
                    )
                    if "cargo fmt --all -- --check" in line:
                        has_cargo_fmt_check = True

                self.assertNotIn(
                    "make generate", line, "make generate found in check path (mutates)"
                )
                self.assertNotIn(
                    "just generate", line, "just generate found in check path (mutates)"
                )

                if "generate" in line or "generator" in line:
                    if "python" in line or "bash" in line or "./" in line:
                        self.assertTrue(
                            "--check" in line or "--dry-run" in line,
                            f"generator called in write mode from {recipe_name}: {line}",
                        )

                if "verify-demo-data.ts" in line:
                    self.assertIn(
                        "--dry-run",
                        line,
                        "demo-data verification must be explicitly write-free",
                    )
                if "contracts-domain-check.sh" in line:
                    self.assertIn(
                        "--check",
                        line,
                        "domain contract validation must use check mode",
                    )

        self.assertTrue(
            has_cargo_fmt_check,
            "cargo fmt --all -- --check must be present in the check recipe",
        )


if __name__ == "__main__":
    unittest.main()
