"""Tests for the write-free safety of the `check` recipe in Justfile."""

from __future__ import annotations

import re
import unittest
from dataclasses import dataclass
from pathlib import Path

from scripts.docmeta.docmeta import REPO_ROOT


JUST_RECIPE = re.compile(
    r"^([a-z][a-z0-9_-]*):(?:\s+([^#]*?))?(?:\s+#.*)?$"
)
JUST_CALL = re.compile(r"^@?just\s+([a-z][a-z0-9_-]*)(?:\s|$)")
SOFT_FAILURE = re.compile(
    r"(?:\|\|\s*(?:true\b|:\s*(?:$|;)|echo\b|exit\s+0\b))"
    r"|(?:;\s*(?:true\b|:\s*(?:$|;)|exit\s+0\b))"
)
RECIPE_NAME = re.compile(r"^[a-z][a-z0-9_-]*$")


@dataclass(frozen=True)
class Recipe:
    dependencies: list[str]
    commands: list[str]


def parse_recipes(content: str) -> dict[str, Recipe]:
    dependencies: dict[str, list[str]] = {}
    commands: dict[str, list[str]] = {}
    current: str | None = None

    for raw_line in content.splitlines():
        if raw_line and not raw_line[0].isspace():
            match = JUST_RECIPE.fullmatch(raw_line)
            current = match.group(1) if match else None
            if current is not None:
                header = (match.group(2) or "").strip()
                dependencies[current] = [
                    token
                    for token in header.split()
                    if RECIPE_NAME.fullmatch(token)
                ]
                commands[current] = []
            continue
        if current is not None and raw_line.startswith(("\t", " ")):
            commands[current].append(raw_line.strip())

    return {
        name: Recipe(dependencies=dependencies[name], commands=commands[name])
        for name in commands
    }


def strip_unquoted_comment(raw_line: str) -> str:
    """Remove a shell comment without treating quoted or escaped # as comments."""
    quote: str | None = None
    escaped = False
    output: list[str] = []

    for char in raw_line:
        if escaped:
            output.append(char)
            escaped = False
            continue
        if char == "\\" and quote != "'":
            output.append(char)
            escaped = True
            continue
        if quote is not None:
            output.append(char)
            if char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            output.append(char)
            quote = char
            continue
        if char == "#" and (
            not output or output[-1].isspace() or output[-1] in ";|&()<>"
        ):
            break
        output.append(char)

    return "".join(output).strip()


def logical_commands(lines: list[str]) -> list[str]:
    commands: list[str] = []
    pending = ""
    for raw_line in lines:
        line = strip_unquoted_comment(raw_line)
        if not line:
            continue
        if pending:
            line = f"{pending} {line}"
        if line.endswith("\\"):
            pending = line[:-1].rstrip()
            continue
        commands.append(line)
        pending = ""
    if pending:
        commands.append(pending)
    return commands


def reachable_recipes(recipes: dict[str, Recipe], root: str) -> list[str]:
    pending = [root]
    visited: list[str] = []

    while pending:
        name = pending.pop(0)
        if name in visited:
            continue
        if name not in recipes:
            raise AssertionError(f"Referenced Just recipe is missing: {name}")
        visited.append(name)
        recipe = recipes[name]
        for dependency in recipe.dependencies:
            if dependency not in visited:
                pending.append(dependency)
        for command in logical_commands(recipe.commands):
            match = JUST_CALL.match(command)
            if match and match.group(1) not in visited:
                pending.append(match.group(1))

    return visited


class TestJustCheckSafety(unittest.TestCase):
    def test_dependency_recipes_are_reachable(self):
        recipes = parse_recipes(
            "check: indirect\n\tjust direct\nindirect:\n\tcargo fmt -- --check\n"
            "direct:\n\tpython3 -m unittest\n"
        )
        self.assertEqual(reachable_recipes(recipes, "check"), ["check", "indirect", "direct"])

    def test_logical_commands_join_continuations(self):
        self.assertEqual(
            logical_commands(["command || \\", "exit 0"]),
            ["command || exit 0"],
        )

    def test_shell_hashes_inside_quotes_or_escapes_are_preserved(self):
        self.assertEqual(
            logical_commands(
                [
                    'echo "Fix #123" # trailing comment',
                    "curl 'https://example.invalid/#anchor' # trailing comment",
                    r"echo value\#fragment # trailing comment",
                    "echo issue#123 # trailing comment",
                    "echo ${name#prefix} # trailing comment",
                    "echo done;# trailing comment",
                ]
            ),
            [
                'echo "Fix #123"',
                "curl 'https://example.invalid/#anchor'",
                r"echo value\#fragment",
                "echo issue#123",
                "echo ${name#prefix}",
                "echo done;",
            ],
        )

    def test_soft_failure_patterns_are_detected(self):
        for command in (
            "check || true",
            "check || echo skipped",
            "check || exit 0",
            "check; true",
            "check; exit 0",
        ):
            with self.subTest(command=command):
                self.assertIsNotNone(SOFT_FAILURE.search(command))

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
            for line in logical_commands(recipes[recipe_name].commands):
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
