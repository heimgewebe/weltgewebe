import tempfile
import unittest
from pathlib import Path

from scripts.docmeta.generate_staleness_report import collect_stale, render


class StalenessReportTests(unittest.TestCase):
    def test_collects_explicit_deprecation_and_archive(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "docs").mkdir()
            (root / "docs" / "active.md").write_text(
                "---\nid: active\nstatus: active\n---\n", encoding="utf-8"
            )
            (root / "docs" / "old.md").write_text(
                "---\nid: old\nstatus: deprecated\n---\n", encoding="utf-8"
            )
            (root / "docs" / "audit.md").write_text(
                "---\nid: audit\nstatus: active\nlifecycle_state: archived\n---\n",
                encoding="utf-8",
            )
            self.assertEqual(
                collect_stale(str(root)),
                [
                    ("docs/audit.md", "active", "archived"),
                    ("docs/old.md", "deprecated", "—"),
                ],
            )

    def test_render_declares_metadata_scope(self):
        text = render()
        self.assertIn("metadata-based", text)
        self.assertNotIn("No stale documents found", text)


if __name__ == "__main__":
    unittest.main()
