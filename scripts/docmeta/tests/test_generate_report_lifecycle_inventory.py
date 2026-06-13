import tempfile
import unittest
from pathlib import Path

import scripts.docmeta.generate_report_lifecycle_inventory as gen


class TestGenerateReportLifecycleInventory(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "docs" / "reports").mkdir(parents=True, exist_ok=True)
        (self.root / "docs" / "tasks").mkdir(parents=True, exist_ok=True)
        (self.root / "docs" / "_generated").mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write(self, rel_path: str, content: str) -> Path:
        path = self.root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_collect_reports_parses_complete_frontmatter(self) -> None:
        report_path = self._write(
            "docs/reports/alpha.md",
            """---
id: docs.reports.alpha
title: Alpha
doc_type: report
status: active
lifecycle: observed
owner_task: docs/tasks/alpha.md
review_after: 2026-12-01
superseded_by: docs/reports/beta.md
relations:
  - type: relates_to
    target: docs/reports/beta.md
---
# Alpha
""",
        )
        self._write("docs/tasks/alpha.md", f"Uses {_rel(report_path, self.root)}\n")

        with temporary_repo_root(self.root):
            records = gen.collect_reports(self.root / "docs" / "reports")

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertTrue(record.has_frontmatter)
        self.assertEqual(record.doc_id, "docs.reports.alpha")
        self.assertEqual(record.title, "Alpha")
        self.assertEqual(record.lifecycle, "observed")
        self.assertEqual(record.owner_task, "docs/tasks/alpha.md")
        self.assertEqual(record.review_after, "2026-12-01")
        self.assertEqual(record.superseded_by, "docs/reports/beta.md")
        self.assertEqual(record.relations_count, 1)
        self.assertEqual(record.relation_types, ("relates_to",))
        self.assertEqual(record.relation_targets, ("docs/reports/beta.md",))
        self.assertEqual(record.referenced_by_paths, ("docs/tasks/alpha.md",))
        self.assertEqual(record.missing_lifecycle_fields, ())
        self.assertEqual(record.frontmatter_parse_warning, "")

    def test_collect_reports_keeps_report_without_frontmatter(self) -> None:
        self._write("docs/reports/no-frontmatter.md", "# No frontmatter\n")

        with temporary_repo_root(self.root):
            records = gen.collect_reports(self.root / "docs" / "reports")

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertFalse(record.has_frontmatter)
        self.assertEqual(record.frontmatter_parse_warning, "frontmatter missing")

    def test_missing_lifecycle_fields_are_diagnostic_only(self) -> None:
        self._write(
            "docs/reports/partial.md",
            """---
id: docs.reports.partial
title: Partial
doc_type: report
status: active
---
# Partial
""",
        )

        with temporary_repo_root(self.root):
            records = gen.collect_reports(self.root / "docs" / "reports")
            markdown = gen.render_inventory(records)

        self.assertEqual(records[0].missing_lifecycle_fields, ("lifecycle", "owner_task", "review_after", "superseded_by"))
        self.assertIn("descriptive only", markdown)
        self.assertIn("not policy violations", markdown)
        self.assertNotIn("invalid", markdown.lower())
        self.assertNotIn("must fix", markdown.lower())

    def test_reference_search_finds_exact_report_paths(self) -> None:
        report_path = self._write(
            "docs/reports/bar.md",
            """---
id: docs.reports.bar
title: Bar
doc_type: report
status: active
---
# Bar
""",
        )
        self._write("docs/tasks/foo.md", f"Reference {_rel(report_path, self.root)}\n")

        with temporary_repo_root(self.root):
            records = gen.collect_reports(self.root / "docs" / "reports")

        self.assertEqual(records[0].referenced_by_paths, ("docs/tasks/foo.md",))

    def test_inventory_is_sorted_deterministically_by_path(self) -> None:
        self._write("docs/reports/zeta.md", "# Zeta\n")
        self._write("docs/reports/alpha.md", "# Alpha\n")

        with temporary_repo_root(self.root):
            records = gen.collect_reports(self.root / "docs" / "reports")

        self.assertEqual([record.path for record in records], ["docs/reports/alpha.md", "docs/reports/zeta.md"])


def _rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


class temporary_repo_root:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.original_repo_root = gen.REPO_ROOT
        self.original_reports_dir = gen.REPORTS_DIR
        self.original_output_path = gen.OUTPUT_PATH
        self.original_reference_search_paths = gen.REFERENCE_SEARCH_PATHS

    def __enter__(self) -> None:
        gen.REPO_ROOT = self.root
        gen.REPORTS_DIR = self.root / "docs" / "reports"
        gen.OUTPUT_PATH = self.root / "docs" / "_generated" / "report-lifecycle-inventory.md"
        gen.REFERENCE_SEARCH_PATHS = [
            self.root / "docs" / "tasks",
            self.root / "docs" / "blueprints",
            self.root / "docs" / "reports",
            self.root / "docs" / "proofs",
            self.root / "docs" / "roadmap.md",
            self.root / "docs" / "_generated",
        ]

    def __exit__(self, exc_type, exc, tb) -> None:
        gen.REPO_ROOT = self.original_repo_root
        gen.REPORTS_DIR = self.original_reports_dir
        gen.OUTPUT_PATH = self.original_output_path
        gen.REFERENCE_SEARCH_PATHS = self.original_reference_search_paths


if __name__ == "__main__":
    unittest.main()
