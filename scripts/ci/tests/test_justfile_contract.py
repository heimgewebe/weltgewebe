import re
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
JUSTFILE = ROOT / "Justfile"
CONTINUATION = chr(92)


def continued(command: str) -> str:
    return f"{command}; {CONTINUATION}"


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
        for line in self.executable_lines():
            normalized = line.lower().rstrip(f"; {CONTINUATION}")
            self.assertNotIn("playwright", normalized)
            self.assertIsNone(
                re.match(r"^pnpm (?:run )?test(?::(?:ci|e2e))?(?: |$)", normalized)
            )

    def test_rust_formatting_stays_check_only(self) -> None:
        lines = self.executable_lines()
        self.assertIn(continued("cargo fmt -- --check"), lines)
        self.assertNotIn(continued("cargo fmt --all"), lines)


if __name__ == "__main__":
    unittest.main()
