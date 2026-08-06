from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.docmeta import generate_implicit_dependencies as generator


class GenerateImplicitDependenciesTests(unittest.TestCase):
    def test_strips_only_recipe_environment_prefixes(self) -> None:
        cases = {
            "python3 -m module": "python3 -m module",
            "FOO=bar python3 -m module": "python3 -m module",
            "env FOO=bar python3 -m module": "python3 -m module",
            "$(CI_TEST_GIT_ENV) python3 -m module": "python3 -m module",
            "$(UV_RUN) python -m module": "python -m module",
            "echo python3 -m not-a-command": "echo python3 -m not-a-command",
        }

        for command, expected in cases.items():
            with self.subTest(command=command):
                self.assertEqual(
                    generator._strip_recipe_environment_prefix(command),
                    expected,
                )

    def test_collects_current_python_and_bash_dependency_shapes(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            (root / "Makefile").write_text(
                "validate-tests:\n"
                "\t$(CI_TEST_GIT_ENV) $(UV_RUN) python -m unittest discover tests/\n"
                "\t$(UV_RUN) python scripts/check.py\n"
                "\tbash scripts/check.sh\n",
                encoding="utf-8",
            )

            with mock.patch.object(generator, "REPO_ROOT", raw_root):
                dependencies = generator.collect_deps()

        self.assertEqual(
            [(item["kind"], item["dependency"]) for item in dependencies],
            [
                ("python-module", "unittest"),
                ("python-script", "scripts/check.py"),
                ("bash-script", "scripts/check.sh"),
            ],
        )
        self.assertEqual([item["line"] for item in dependencies], [2, 3, 4])

    def test_current_unresolved_dependency_fails_closed(self) -> None:
        dependency = {
            "source": "Makefile",
            "target": "validate",
            "dependency": "scripts/missing.py",
            "evidence": "python scripts/missing.py",
            "kind": "python-script",
            "line": 2,
        }
        with tempfile.TemporaryDirectory() as raw_root:
            with mock.patch.object(generator, "REPO_ROOT", raw_root):
                with self.assertRaises(generator.DependencyDecisionError):
                    generator._classify_dependency(dependency, historical=False)
                historical = generator._classify_dependency(
                    dependency,
                    historical=True,
                )

        self.assertEqual(historical["decision"], "remove")

    def test_historical_audit_is_digest_bound_and_complete(self) -> None:
        audit = generator.load_historical_audit()
        self.assertEqual(audit["source_commit"], generator.HISTORICAL_SOURCE_COMMIT)
        self.assertEqual(audit["source_sha256"], generator.HISTORICAL_SOURCE_SHA256)
        self.assertEqual(audit["finding_count"], 51)
        self.assertEqual(len(audit["findings"]), 51)
        finding_ids = [generator._finding_id(item) for item in audit["findings"]]
        self.assertEqual(len(set(finding_ids)), 51)

    def test_historical_audit_rejects_source_byte_drift(self) -> None:
        source = generator._historical_audit_path().read_bytes()
        with tempfile.TemporaryDirectory() as raw_root:
            target = (
                Path(raw_root)
                / "scripts"
                / "docmeta"
                / "data"
                / "implicit-dependencies-b043a86.md"
            )
            target.parent.mkdir(parents=True)
            target.write_bytes(source + b"\n")
            with mock.patch.object(generator, "REPO_ROOT", raw_root):
                with self.assertRaises(generator.DependencyDecisionError):
                    generator.load_historical_audit()

    def test_render_decides_every_historical_and_current_edge(self) -> None:
        rendered = generator.render()
        current_count = len(generator.collect_deps())

        self.assertIn("Findings decided: **51 / 51**", rendered)
        self.assertIn(
            f"Current execution edges decided: **{current_count} / {current_count}**",
            rendered,
        )
        self.assertNotIn("*unclear*", rendered)
        self.assertIn("not an overall architecture pass", rendered)
        self.assertIn("fail closed", rendered)


if __name__ == "__main__":
    unittest.main()
