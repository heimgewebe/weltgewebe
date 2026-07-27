import json
from pathlib import Path
import shlex
import unittest


ROOT = Path(__file__).resolve().parents[3]
JUSTFILE = ROOT / "Justfile"
WEB_PACKAGE = ROOT / "apps" / "web" / "package.json"
CONTINUATION = chr(92)


def continued(command: str) -> str:
    return f"{command}; {CONTINUATION}"


def script_uses_playwright(
    script: str,
    scripts: dict[str, str],
    seen: set[str] | None = None,
) -> bool:
    seen = set() if seen is None else seen
    if script in seen:
        return False
    seen.add(script)
    command = scripts.get(script)
    if command is None:
        return False
    try:
        tokens = shlex.split(command)
    except ValueError:
        return True
    if "playwright" in tokens:
        return True
    for index, token in enumerate(tokens):
        if token != "pnpm" or index + 1 >= len(tokens):
            continue
        next_token = tokens[index + 1]
        nested = (
            tokens[index + 2]
            if next_token == "run" and index + 2 < len(tokens)
            else next_token
        )
        if nested in scripts and script_uses_playwright(nested, scripts, seen):
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
        payload = json.loads(WEB_PACKAGE.read_text(encoding="utf-8"))
        scripts = payload.get("scripts")
        self.assertIsInstance(scripts, dict)
        self.assertTrue(
            all(isinstance(k, str) and isinstance(v, str) for k, v in scripts.items())
        )
        return scripts

    def test_local_ci_runs_full_web_unit_suite_only_outside_github_actions(
        self,
    ) -> None:
        lines = self.executable_lines()
        vitest_line = continued("pnpm exec vitest run")
        self.assertEqual(lines.count(vitest_line), 1)
        index = lines.index(vitest_line)
        self.assertEqual(
            lines[index - 1],
            f'if [ "${{GITHUB_ACTIONS:-false}}" != "true" ]; then {CONTINUATION}',
        )
        self.assertEqual(lines[index + 1], continued("fi"))
        self.assertLess(lines.index(continued("pnpm sync")), index)
        self.assertLess(index, lines.index(continued("pnpm build")))
        self.assertNotIn(continued("pnpm test:unit"), lines)

    def test_browser_e2e_commands_remain_outside_local_ci_recipe(self) -> None:
        scripts = self.web_scripts()
        for line in self.executable_lines():
            normalized = line.rstrip(f"; {CONTINUATION}")
            try:
                tokens = shlex.split(normalized)
            except ValueError as error:
                self.fail(f"unparseable CI command {normalized!r}: {error}")
            if "playwright" in tokens[:3]:
                self.fail(f"direct Playwright command in local CI: {normalized}")
            if len(tokens) < 2 or tokens[0] != "pnpm":
                continue
            script = tokens[2] if tokens[1] == "run" and len(tokens) > 2 else tokens[1]
            if script in scripts:
                self.assertFalse(
                    script_uses_playwright(script, scripts),
                    f"pnpm script {script!r} reaches Playwright",
                )

    def test_rust_formatting_stays_check_only(self) -> None:
        lines = self.executable_lines()
        self.assertIn(continued("cargo fmt -- --check"), lines)
        self.assertNotIn(continued("cargo fmt --all"), lines)


if __name__ == "__main__":
    unittest.main()
