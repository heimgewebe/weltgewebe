import json
from pathlib import Path
import shlex
import unittest


ROOT = Path(__file__).resolve().parents[3]
JUSTFILE = ROOT / "Justfile"
WEB_PACKAGE = ROOT / "apps" / "web" / "package.json"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
WEB_WORKFLOW = ROOT / ".github" / "workflows" / "web.yml"
CONTINUATION = chr(92)
SHELL_OPERATORS = {";", "&&", "||", "|"}


def continued(command: str) -> str:
    return f"{command}; {CONTINUATION}"


def shell_commands(command: str) -> list[list[str]]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
    lexer.whitespace_split = True
    lexer.commenters = ""
    commands: list[list[str]] = [[]]
    for token in lexer:
        if token in SHELL_OPERATORS:
            if commands[-1]:
                commands.append([])
            continue
        commands[-1].append(token)
    return [tokens for tokens in commands if tokens]


def package_script_reference(tokens: list[str], scripts: dict[str, str]) -> str | None:
    if not tokens:
        return None
    executable_index = 0
    while executable_index < len(tokens) and "=" in tokens[executable_index]:
        executable_index += 1
    if executable_index >= len(tokens):
        return None
    tool = tokens[executable_index]
    if tool not in {"pnpm", "npm"}:
        return None
    index = executable_index + 1
    while index < len(tokens) and tokens[index].startswith("-"):
        index += 1
    if index >= len(tokens):
        return None
    if tokens[index] == "run":
        index += 1
    return tokens[index] if index < len(tokens) and tokens[index] in scripts else None


def command_invokes_playwright(tokens: list[str]) -> bool:
    if not tokens:
        return False
    index = 0
    while index < len(tokens) and "=" in tokens[index]:
        index += 1
    if index >= len(tokens):
        return False
    executable = tokens[index]
    if executable == "playwright":
        return True
    if executable not in {"pnpm", "npm", "npx"}:
        return False
    index += 1
    while index < len(tokens) and tokens[index].startswith("-"):
        index += 1
    if index < len(tokens) and tokens[index] in {"exec", "dlx"}:
        index += 1
        while index < len(tokens) and tokens[index].startswith("-"):
            index += 1
    return index < len(tokens) and tokens[index] == "playwright"


def script_uses_playwright(
    script: str,
    scripts: dict[str, str],
    seen: set[str] | None = None,
) -> bool:
    seen = set() if seen is None else seen
    if script in seen:
        return False
    seen.add(script)
    lifecycle = [
        name for name in (f"pre{script}", script, f"post{script}") if name in scripts
    ]
    for name in lifecycle:
        try:
            commands = shell_commands(scripts[name])
        except ValueError:
            return True
        for tokens in commands:
            if command_invokes_playwright(tokens):
                return True
            nested = package_script_reference(tokens, scripts)
            if nested is not None and script_uses_playwright(nested, scripts, seen):
                return True
    return False


class JustfileContractTests(unittest.TestCase):
    def ci_recipe_lines(self) -> list[str]:
        text = JUSTFILE.read_text(encoding="utf-8")
        start = text.index("\nci:\n")
        end = text.index("\n# ---------- Rust ----------", start)
        return text[start:end].splitlines()

    def executable_lines(self) -> list[str]:
        return [
            line.lstrip("\t")
            for line in self.ci_recipe_lines()
            if line.startswith("\t")
            and not line.startswith("\t#")
            and not line.startswith("\t@echo")
        ]

    def web_scripts(self) -> dict[str, str]:
        scripts = json.loads(WEB_PACKAGE.read_text(encoding="utf-8")).get("scripts")
        self.assertIsInstance(scripts, dict)
        self.assertTrue(
            all(isinstance(k, str) and isinstance(v, str) for k, v in scripts.items())
        )
        return scripts

    def test_just_ci_owns_one_exact_full_vitest_execution(self) -> None:
        lines = self.executable_lines()
        expected_pnpm = {
            continued("pnpm install --frozen-lockfile"),
            continued("pnpm sync"),
            continued("pnpm exec vitest run"),
            continued("pnpm build"),
            continued("pnpm run ci"),
        }
        actual_pnpm = {line for line in lines if line.startswith("pnpm ")}
        self.assertEqual(actual_pnpm, expected_pnpm)
        vitest = lines.index(continued("pnpm exec vitest run"))
        self.assertLess(lines.index(continued("pnpm sync")), vitest)
        self.assertLess(vitest, lines.index(continued("pnpm build")))

    def test_hosted_browser_workflows_do_not_repeat_unit_tests(self) -> None:
        for workflow in (CI_WORKFLOW, WEB_WORKFLOW):
            lines = [
                line.strip()
                for line in workflow.read_text(encoding="utf-8").splitlines()
            ]
            self.assertNotIn("run: pnpm test:unit", lines, workflow.name)
            self.assertIn("run: pnpm test:ci", lines, workflow.name)

    def test_local_package_scripts_do_not_reach_playwright(self) -> None:
        scripts = self.web_scripts()
        for script in ("sync", "build", "ci"):
            self.assertFalse(script_uses_playwright(script, scripts), script)

    def test_resolver_handles_flags_hooks_cycles_and_harmless_names(self) -> None:
        scripts = {
            "browser": "playwright test",
            "wrapper": "pnpm --silent run browser",
            "ci": "echo ok",
            "preci": "npm run wrapper",
            "cycle-a": "pnpm cycle-b",
            "cycle-b": "pnpm cycle-a",
            "safe": "echo playwright && test -d playwright",
        }
        self.assertTrue(script_uses_playwright("wrapper", scripts))
        self.assertTrue(script_uses_playwright("ci", scripts))
        self.assertFalse(script_uses_playwright("cycle-a", scripts))
        self.assertFalse(script_uses_playwright("safe", scripts))

    def test_rust_formatting_stays_check_only(self) -> None:
        lines = self.executable_lines()
        self.assertIn(continued("cargo fmt -- --check"), lines)
        self.assertNotIn(continued("cargo fmt --all"), lines)


if __name__ == "__main__":
    unittest.main()
