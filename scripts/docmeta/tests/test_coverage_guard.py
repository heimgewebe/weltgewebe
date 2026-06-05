import os
import shutil
import subprocess
import tempfile
import unittest

# Repo root is three levels up from scripts/docmeta/tests/.
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
GUARD = os.path.join(REPO_ROOT, "scripts", "docmeta", "coverage-guard.sh")

# coverage-guard.sh reads audit/impl-registry.yaml relative to CWD and checks a
# hardcoded set of CRITICAL_PATHS, skipping any critical path whose directory
# does not exist. By running it in a throwaway tree that only materialises the
# critical directory under test, we can exercise the path-matching logic in
# isolation without touching the real repo.


class CoverageGuardScopeTest(unittest.TestCase):
    def _run(self, registry_content, critical_dirs):
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmpdir, ignore_errors=True)

        os.makedirs(os.path.join(tmpdir, "audit"))
        with open(os.path.join(tmpdir, "audit", "impl-registry.yaml"), "w", encoding="utf-8") as f:
            f.write(registry_content)

        for d in critical_dirs:
            os.makedirs(os.path.join(tmpdir, d), exist_ok=True)

        return subprocess.run(
            ["bash", GUARD],
            cwd=tmpdir,
            capture_output=True,
            text=True,
        )

    @staticmethod
    def _registry(path):
        return (
            "---\n"
            "implementations:\n"
            "  - id: impl.under.test\n"
            f"    path: {path}\n"
            "    impl_type: schema\n"
            "    status: active\n"
            "    documented_by: []\n"
            "    verified_by: []\n"
        )

    def test_exact_path_counts_as_coverage(self):
        result = self._run(self._registry("contracts/domain/"), ["contracts/domain"])
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("coverage-guard pass.", result.stdout)

    def test_subpath_does_not_cover_critical_path(self):
        # A registry entry that is a *sub-path* of a critical path must NOT
        # satisfy that critical path — otherwise a narrow proof would overclaim
        # coverage for a broader surface.
        result = self._run(
            self._registry("contracts/domain/examples/"), ["contracts/domain"]
        )
        self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
        self.assertIn(
            "Critical implementation missing from registry: contracts/domain",
            result.stdout,
        )

    def test_parent_path_does_not_cover_critical_path(self):
        # The inverse must hold too: a broader registry entry (contracts/) must
        # not satisfy a narrower critical path (contracts/domain).
        result = self._run(self._registry("contracts/"), ["contracts/domain"])
        self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
        self.assertIn(
            "Critical implementation missing from registry: contracts/domain",
            result.stdout,
        )


if __name__ == "__main__":
    unittest.main()
