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
            "echo python3 -m not-a-command": "echo python3 -m not-a-command",
        }

        for command, expected in cases.items():
            with self.subTest(command=command):
                self.assertEqual(
                    generator._strip_recipe_environment_prefix(command),
                    expected,
                )

    def test_collects_python_dependency_behind_make_environment(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            makefile = root / "Makefile"
            makefile.write_text(
                "validate-tests:\n"
                "\t$(CI_TEST_GIT_ENV) python3 -m unittest discover tests/\n",
                encoding="utf-8",
            )

            with mock.patch.object(generator, "REPO_ROOT", raw_root):
                dependencies = generator.collect_deps()

        self.assertEqual(
            dependencies,
            [
                {
                    "source": "Makefile",
                    "target": "validate-tests",
                    "dependency": "unittest",
                    "evidence": (
                        "$(CI_TEST_GIT_ENV) python3 -m unittest discover tests/"
                    ),
                    "documented": "*unclear*",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
