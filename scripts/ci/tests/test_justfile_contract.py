from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
JUSTFILE = ROOT / "Justfile"


class JustfileContractTests(unittest.TestCase):
    def ci_recipe(self) -> str:
        text = JUSTFILE.read_text(encoding="utf-8")
        start = text.index("\nci:\n")
        end = text.index("\n# ---------- Rust ----------", start)
        return text[start:end]

    def test_local_ci_runs_web_unit_tests_without_package_pretest_hook(self) -> None:
        recipe = self.ci_recipe()
        self.assertIn("pnpm exec vitest run", recipe)
        self.assertNotIn("pnpm test:unit", recipe)
        self.assertLess(recipe.index("pnpm sync"), recipe.index("pnpm exec vitest run"))
        self.assertLess(
            recipe.index("pnpm exec vitest run"), recipe.index("pnpm build")
        )

    def test_browser_e2e_remains_outside_local_ci_recipe(self) -> None:
        recipe = self.ci_recipe()
        self.assertNotIn("playwright", recipe.lower())
        self.assertNotIn("test:e2e", recipe)

    def test_rust_formatting_stays_check_only(self) -> None:
        recipe = self.ci_recipe()
        self.assertIn("cargo fmt -- --check", recipe)
        self.assertNotIn("cargo fmt --all\n", recipe)


if __name__ == "__main__":
    unittest.main()
