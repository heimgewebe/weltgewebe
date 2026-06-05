import os
import shutil
import subprocess
import tempfile
import unittest

# Repo root is three levels up from scripts/docmeta/tests/.
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
GENERATOR = os.path.join(REPO_ROOT, "scripts", "docmeta", "generate-impl-index.sh")

# The generator uses CWD-relative paths for both its input registry and its
# output artifact, so it can be exercised against a throwaway fixture tree
# without ever touching the real repo.


class GenerateImplIndexTest(unittest.TestCase):
    def _run(self, registry_content):
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmpdir, ignore_errors=True)

        os.makedirs(os.path.join(tmpdir, "audit"))
        with open(os.path.join(tmpdir, "audit", "impl-registry.yaml"), "w", encoding="utf-8") as f:
            f.write(registry_content)

        result = subprocess.run(
            ["bash", GENERATOR],
            cwd=tmpdir,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)

        out_path = os.path.join(tmpdir, "docs", "_generated", "impl-index.md")
        self.assertTrue(os.path.exists(out_path), "generator did not produce impl-index.md")
        with open(out_path, encoding="utf-8") as f:
            content = f.read()
        return tmpdir, out_path, content

    @staticmethod
    def _row(content, impl_id):
        """Return the table cells for the row whose first cell equals impl_id."""
        for line in content.splitlines():
            if not line.startswith("| "):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if cells and cells[0] == impl_id:
                return cells
        return None

    def test_empty_lists_render_undocumented_and_none(self):
        registry = (
            "---\n"
            "implementations:\n"
            "  - id: impl.empty\n"
            "    path: apps/empty/\n"
            "    impl_type: service\n"
            "    status: active\n"
            "    documented_by: []\n"
            "    verified_by: []\n"
        )
        _, _, content = self._run(registry)
        cells = self._row(content, "impl.empty")
        self.assertIsNotNone(cells)
        # | implementation | path | impl_type | criticality | documented_by | verification | evidence_level |
        self.assertEqual(cells[1], "apps/empty/")
        self.assertEqual(cells[2], "service")
        self.assertEqual(cells[3], "—")  # criticality absent -> placeholder
        self.assertEqual(cells[4], "⚠ undocumented")
        self.assertEqual(cells[5], "none")
        self.assertEqual(cells[6], "—")  # evidence_level absent -> placeholder

    def test_filled_entry_renders_all_columns(self):
        registry = (
            "---\n"
            "implementations:\n"
            "  - id: impl.full\n"
            "    path: apps/full/\n"
            "    impl_type: service\n"
            "    status: active\n"
            "    criticality: high\n"
            "    evidence_level: ci\n"
            "    documented_by:\n"
            "      - docs/a.md\n"
            "      - docs/b.md\n"
            "    verified_by:\n"
            "      - .github/workflows/a.yml\n"
            "      - tests/a.rs\n"
        )
        _, _, content = self._run(registry)
        cells = self._row(content, "impl.full")
        self.assertIsNotNone(cells)
        self.assertEqual(cells[1], "apps/full/")
        self.assertEqual(cells[2], "service")
        self.assertEqual(cells[3], "high")
        self.assertEqual(cells[4], "docs/a.md, docs/b.md")
        self.assertEqual(cells[5], ".github/workflows/a.yml, tests/a.rs")
        self.assertEqual(cells[6], "ci")

    def test_impl_type_is_not_mislabeled_as_criticality(self):
        # Regression guard: impl_type must live in its own column and must not
        # leak into the criticality column when no criticality field is set.
        registry = (
            "---\n"
            "implementations:\n"
            "  - id: impl.typed\n"
            "    path: contracts/\n"
            "    impl_type: schema\n"
            "    status: active\n"
            "    documented_by:\n"
            "      - docs/a.md\n"
            "    verified_by:\n"
            "      - scripts/a.sh\n"
        )
        _, _, content = self._run(registry)
        cells = self._row(content, "impl.typed")
        self.assertIsNotNone(cells)
        self.assertEqual(cells[2], "schema")  # impl_type column
        self.assertNotEqual(cells[3], "schema")  # criticality column must NOT be impl_type
        self.assertEqual(cells[3], "—")

    def test_header_has_seven_columns(self):
        registry = (
            "---\n"
            "implementations:\n"
            "  - id: impl.x\n"
            "    path: x/\n"
            "    impl_type: config\n"
            "    status: active\n"
            "    documented_by: []\n"
            "    verified_by: []\n"
        )
        _, _, content = self._run(registry)
        header = next(
            line for line in content.splitlines() if line.startswith("| implementation |")
        )
        cells = [c.strip() for c in header.strip().strip("|").split("|")]
        self.assertEqual(
            cells,
            [
                "implementation",
                "path",
                "impl_type",
                "criticality",
                "documented_by",
                "verification",
                "evidence_level",
            ],
        )

    def test_only_impl_index_is_written(self):
        registry = (
            "---\n"
            "implementations:\n"
            "  - id: impl.x\n"
            "    path: x/\n"
            "    impl_type: config\n"
            "    status: active\n"
            "    documented_by: []\n"
            "    verified_by: []\n"
        )
        tmpdir, _, _ = self._run(registry)
        generated = os.listdir(os.path.join(tmpdir, "docs", "_generated"))
        self.assertEqual(generated, ["impl-index.md"])

    def test_generated_file_keeps_guard_invariants(self):
        registry = (
            "---\n"
            "implementations:\n"
            "  - id: impl.x\n"
            "    path: x/\n"
            "    impl_type: config\n"
            "    status: active\n"
            "    documented_by: []\n"
            "    verified_by: []\n"
        )
        _, _, content = self._run(registry)
        # generated-files-guard.sh requires both of these to be present.
        self.assertTrue(content.startswith("---\n"), "missing frontmatter block")
        self.assertIn("Generated automatically.", content)


if __name__ == "__main__":
    unittest.main()
