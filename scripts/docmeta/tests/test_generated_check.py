import tempfile
import unittest
from pathlib import Path

from scripts.docmeta.generated_check import write_or_check


class GeneratedCheckTests(unittest.TestCase):
    def test_check_passes_without_rewriting_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "out.md"
            target.write_text("same\n", encoding="utf-8")
            before = target.stat().st_mtime_ns
            self.assertEqual(write_or_check(target, "same\n", check=True), 0)
            self.assertEqual(target.read_text(encoding="utf-8"), "same\n")
            self.assertEqual(target.stat().st_mtime_ns, before)

    def test_check_fails_without_rewriting_stale_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "out.md"
            target.write_text("old\n", encoding="utf-8")
            self.assertEqual(write_or_check(target, "new\n", check=True), 1)
            self.assertEqual(target.read_text(encoding="utf-8"), "old\n")

    def test_write_mode_creates_parent_and_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "nested" / "out.md"
            self.assertEqual(write_or_check(target, "content\n"), 0)
            self.assertEqual(target.read_text(encoding="utf-8"), "content\n")


if __name__ == "__main__":
    unittest.main()
