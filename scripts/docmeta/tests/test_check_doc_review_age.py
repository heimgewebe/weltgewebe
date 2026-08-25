import datetime
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.docmeta import check_doc_review_age as review_age


class ReviewAfterLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "docs").mkdir()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write(self, name: str, frontmatter: str) -> str:
        rel = f"docs/{name}.md"
        (self.root / rel).write_text(
            f"---\n{frontmatter}\n---\n\n# {name}\n",
            encoding="utf-8",
        )
        return rel

    def _run(self, rel: str, *, mode: str = "warn", today: str = "2026-08-24"):
        errors: list[str] = []
        warnings: list[str] = []
        report: dict = {}
        with patch.object(review_age, "_tracked_markdown_files", return_value=[rel]):
            review_age._check_review_after(
                root=str(self.root),
                today=datetime.date.fromisoformat(today),
                mode=mode,
                errors=errors,
                warnings=warnings,
                freshness_report=report,
            )
        return errors, warnings, report

    def test_due_active_document_warns_in_current_warn_policy(self):
        rel = self._write(
            "active",
            "id: docs.active\nstatus: active\nlifecycle_state: active\nreview_after: 2026-08-23",
        )
        errors, warnings, report = self._run(rel, mode="warn")
        self.assertEqual(errors, [])
        self.assertEqual(len(warnings), 1)
        self.assertTrue(report["docs.active"]["review_due"])
        self.assertEqual(report["docs.active"]["review_due_days"], 1)

    def test_due_active_document_fails_closed_in_strict_mode(self):
        rel = self._write(
            "strict",
            "id: docs.strict\nstatus: active\nreview_after: 2026-08-24",
        )
        errors, warnings, report = self._run(rel, mode="strict")
        self.assertEqual(warnings, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("due/overdue", errors[0])
        self.assertTrue(report["docs.strict"]["review_due"])

    def test_superseded_document_does_not_reactivate_when_deadline_is_old(self):
        rel = self._write(
            "retired",
            "id: docs.retired\nstatus: deprecated\nlifecycle_state: superseded\nreview_after: 2026-07-01",
        )
        errors, warnings, report = self._run(rel, mode="strict")
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertTrue(report["docs.retired"]["review_retired"])
        self.assertFalse(report["docs.retired"]["review_due"])

    def test_future_review_after_is_not_due(self):
        rel = self._write(
            "future",
            "id: docs.future\nstatus: active\nreview_after: 2026-08-25",
        )
        errors, warnings, report = self._run(rel, mode="strict")
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertFalse(report["docs.future"]["review_due"])

    def test_review_after_rejects_non_literal_iso_date_forms(self):
        for index, value in enumerate(("20260824", "2026-W35-1"), start=1):
            with self.subTest(value=value):
                rel = self._write(
                    f"invalid-shape-{index}",
                    f"id: docs.invalid-shape-{index}\nstatus: active\nreview_after: {value}",
                )
                errors, warnings, report = self._run(rel, mode="warn")
                self.assertEqual(warnings, [])
                self.assertEqual(len(errors), 1)
                self.assertIn("Must be YYYY-MM-DD", errors[0])
                self.assertIsNone(report[f"docs.invalid-shape-{index}"]["review_due"])

    def test_invalid_review_after_is_always_an_error(self):
        rel = self._write(
            "invalid",
            "id: docs.invalid\nstatus: active\nreview_after: tomorrow",
        )
        errors, warnings, report = self._run(rel, mode="warn")
        self.assertEqual(warnings, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("Invalid 'review_after'", errors[0])
        self.assertIsNone(report["docs.invalid"]["review_due"])

    def test_today_override_parser_is_deterministic(self):
        self.assertEqual(
            review_age._today_from_arg("2026-08-24"),
            datetime.date(2026, 8, 24),
        )
        for invalid in ("24.08.2026", "20260824", "2026-W35-1"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    review_age._today_from_arg(invalid)


if __name__ == "__main__":
    unittest.main()
