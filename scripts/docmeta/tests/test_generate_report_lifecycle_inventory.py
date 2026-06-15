import tempfile
import unittest
from pathlib import Path

import scripts.docmeta.generate_report_lifecycle_inventory as gen


class TestGenerateReportLifecycleInventory(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self._mkdir("docs/reports")
        self._mkdir("docs/tasks")
        self._mkdir("docs/blueprints")
        self._mkdir("docs/proofs")
        self._mkdir("docs/adr")
        self._mkdir("docs/specs")
        self._mkdir("docs/_generated")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _mkdir(self, rel_path: str) -> None:
        (self.root / rel_path).mkdir(parents=True, exist_ok=True)

    def _write(self, rel_path: str, content: str) -> Path:
        path = self.root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def _config(self) -> gen.InventoryConfig:
        return gen.InventoryConfig(
            repo_root=self.root,
            reports_dir=self.root / "docs" / "reports",
            output_path=self.root / "docs" / "_generated" / "report-lifecycle-inventory.md",
            primary_search_paths=(self.root / "docs",),
            derived_search_paths=(self.root / "docs" / "_generated",),
        )

    def test_collect_reports_parses_complete_frontmatter(self) -> None:
        report_path = self._write(
            "docs/reports/alpha.md",
            """---
id: docs.reports.alpha
title: Alpha
doc_type: report
status: active
lifecycle_state: active
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

        records = gen.collect_reports(self._config())

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertTrue(record.has_frontmatter)
        self.assertEqual(record.doc_id, "docs.reports.alpha")
        self.assertEqual(record.title, "Alpha")
        self.assertEqual(record.lifecycle, "observed")
        self.assertEqual(record.lifecycle_state, "active")
        self.assertEqual(record.owner_task, "docs/tasks/alpha.md")
        self.assertEqual(record.review_after, "2026-12-01")
        self.assertEqual(record.superseded_by, "docs/reports/beta.md")
        self.assertEqual(record.relations_count, 1)
        self.assertEqual(record.relation_types, ("relates_to",))
        self.assertEqual(record.relation_targets, ("docs/reports/beta.md",))
        self.assertEqual(record.primary_referenced_by_paths, ("docs/tasks/alpha.md",))
        self.assertEqual(record.derived_referenced_by_paths, ())
        self.assertEqual(record.absent_core_lifecycle_fields, ())
        self.assertFalse(record.missing_supersession_target)
        self.assertEqual(record.frontmatter_parse_warning, "")

    def test_collect_reports_keeps_report_without_frontmatter(self) -> None:
        self._write("docs/reports/no-frontmatter.md", "# No frontmatter\n")

        records = gen.collect_reports(self._config())

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertFalse(record.has_frontmatter)
        self.assertEqual(record.frontmatter_parse_warning, "frontmatter missing")

    def test_missing_core_lifecycle_metadata_is_diagnostic_only(self) -> None:
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

        records = gen.collect_reports(self._config())
        markdown = gen.render_inventory(records)

        self.assertEqual(
            records[0].absent_core_lifecycle_fields,
            ("lifecycle", "owner_task", "review_after", "lifecycle_state"),
        )
        self.assertIn("descriptive only", markdown)
        self.assertNotIn("invalid", markdown.lower())
        self.assertNotIn("must fix", markdown.lower())
        self.assertNotIn("violation", markdown.lower())

    def test_generated_references_do_not_count_as_primary_references(self) -> None:
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
        self._write("docs/_generated/doc-index.md", f"Derived {_rel(report_path, self.root)}\n")

        records = gen.collect_reports(self._config())

        self.assertEqual(records[0].primary_referenced_by_paths, ())
        self.assertEqual(records[0].referenced_by_count, 0)

    def test_generated_references_appear_as_derived_references(self) -> None:
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
        self._write("docs/_generated/doc-index.md", f"Derived {_rel(report_path, self.root)}\n")

        records = gen.collect_reports(self._config())

        self.assertEqual(records[0].derived_referenced_by_paths, ("docs/_generated/doc-index.md",))

    def test_adr_references_count_as_primary_references(self) -> None:
        report_path = self._write(
            "docs/reports/auth-status-matrix.md",
            """---
id: docs.reports.auth-status-matrix
title: Auth Status Matrix
doc_type: reference
status: active
---
# Auth Status Matrix
""",
        )
        self._write(
            "docs/adr/ADR-0006__auth-magic-link-session-passkey.md",
            f"See {_rel(report_path, self.root)}.\n",
        )

        records = gen.collect_reports(self._config())

        self.assertEqual(
            records[0].primary_referenced_by_paths,
            ("docs/adr/ADR-0006__auth-magic-link-session-passkey.md",),
        )

    def test_specs_references_count_as_primary_references(self) -> None:
        report_path = self._write(
            "docs/reports/passkey-register-verify-prep.md",
            """---
id: docs.reports.passkey
title: Passkey Prep
doc_type: report
status: active
---
# Passkey Prep
""",
        )
        self._write(
            "docs/specs/auth-api.md",
            f"See {_rel(report_path, self.root)}.\n",
        )

        records = gen.collect_reports(self._config())

        self.assertEqual(
            records[0].primary_referenced_by_paths,
            ("docs/specs/auth-api.md",),
        )

    def test_exact_path_matching_accepts_sentence_period(self) -> None:
        report_path = self._write(
            "docs/reports/foo.md",
            """---
status: active
---
# Foo
""",
        )
        self._write("docs/tasks/check.md", f"Read {_rel(report_path, self.root)}.\n")

        records = gen.collect_reports(self._config())

        self.assertEqual(records[0].primary_referenced_by_paths, ("docs/tasks/check.md",))

    def test_exact_path_pattern_accepts_plain_path(self) -> None:
        pattern = gen._compile_path_reference_pattern("docs/reports/foo.md")
        self.assertTrue(pattern.search("docs/reports/foo.md"))

    def test_exact_path_pattern_accepts_sentence_period(self) -> None:
        pattern = gen._compile_path_reference_pattern("docs/reports/foo.md")
        self.assertTrue(pattern.search("docs/reports/foo.md."))

    def test_exact_path_pattern_accepts_comma_after_path(self) -> None:
        pattern = gen._compile_path_reference_pattern("docs/reports/foo.md")
        self.assertTrue(pattern.search("docs/reports/foo.md,"))

    def test_exact_path_pattern_accepts_semicolon_after_path(self) -> None:
        pattern = gen._compile_path_reference_pattern("docs/reports/foo.md")
        self.assertTrue(pattern.search("docs/reports/foo.md;"))

    def test_exact_path_pattern_accepts_closing_parenthesis_after_path(self) -> None:
        pattern = gen._compile_path_reference_pattern("docs/reports/foo.md")
        self.assertTrue(pattern.search("(docs/reports/foo.md)"))

    def test_exact_path_pattern_accepts_backtick_wrapped_path(self) -> None:
        pattern = gen._compile_path_reference_pattern("docs/reports/foo.md")
        self.assertTrue(pattern.search("`docs/reports/foo.md`"))

    def test_exact_path_pattern_accepts_anchor_suffix(self) -> None:
        pattern = gen._compile_path_reference_pattern("docs/reports/foo.md")
        self.assertTrue(pattern.search("docs/reports/foo.md#section"))

    def test_exact_path_pattern_rejects_old_suffix(self) -> None:
        pattern = gen._compile_path_reference_pattern("docs/reports/foo.md")
        self.assertFalse(pattern.search("docs/reports/foo.md.old"))

    def test_exact_path_pattern_rejects_bak_suffix(self) -> None:
        pattern = gen._compile_path_reference_pattern("docs/reports/foo.md")
        self.assertFalse(pattern.search("docs/reports/foo.md.bak"))

    def test_exact_path_pattern_rejects_dash_suffix(self) -> None:
        pattern = gen._compile_path_reference_pattern("docs/reports/foo.md")
        self.assertFalse(pattern.search("docs/reports/foo.md-extra"))

    def test_exact_path_pattern_rejects_underscore_suffix(self) -> None:
        pattern = gen._compile_path_reference_pattern("docs/reports/foo.md")
        self.assertFalse(pattern.search("docs/reports/foo.md_extra"))

    def test_exact_path_pattern_rejects_slash_suffix(self) -> None:
        pattern = gen._compile_path_reference_pattern("docs/reports/foo.md")
        self.assertFalse(pattern.search("docs/reports/foo.md/extra"))

    def test_superseded_by_not_absent_for_active_reports(self) -> None:
        self._write(
            "docs/reports/active.md",
            """---
id: docs.reports.active
title: Active
doc_type: report
status: active
lifecycle_state: active
lifecycle: observed
owner_task: docs/tasks/active.md
review_after: 2026-12-01
---
# Active
""",
        )

        record = gen.collect_reports(self._config())[0]

        self.assertEqual(record.absent_core_lifecycle_fields, ())
        self.assertFalse(record.missing_supersession_target)

    def test_superseded_lifecycle_state_without_superseded_by_is_reported(self) -> None:
        self._write(
            "docs/reports/superseded.md",
            """---
id: docs.reports.superseded
title: Superseded
doc_type: report
status: deprecated
lifecycle_state: superseded
lifecycle: observed
owner_task: docs/tasks/superseded.md
review_after: 2026-12-01
---
# Superseded
""",
        )

        record = gen.collect_reports(self._config())[0]

        self.assertTrue(record.missing_supersession_target)

    def test_superseded_lifecycle_state_matching_is_case_insensitive(self) -> None:
        self._write(
            "docs/reports/superseded.md",
            """---
id: docs.reports.superseded
title: Superseded
doc_type: report
status: deprecated
lifecycle_state: Superseded
lifecycle: observed
owner_task: docs/tasks/superseded.md
review_after: 2026-12-01
---
# Superseded
""",
        )

        record = gen.collect_reports(self._config())[0]

        self.assertTrue(record.missing_supersession_target)

    def test_deprecated_without_lifecycle_state_is_not_terminal(self) -> None:
        self._write(
            "docs/reports/legacy.md",
            """---
id: docs.reports.legacy
title: Legacy
doc_type: report
status: deprecated
lifecycle: legacy
owner_task: OPT-ARC-001
review_after: 2026-12-01
---
# Legacy
""",
        )

        record = gen.collect_reports(self._config())[0]

        self.assertFalse(record.missing_supersession_target)
        self.assertIn("lifecycle_state", record.absent_core_lifecycle_fields)

    def test_archived_lifecycle_state_without_superseded_by_is_not_supersession_gap(self) -> None:
        self._write(
            "docs/reports/archived.md",
            """---
id: docs.reports.archived
title: Archived
doc_type: report
status: deprecated
lifecycle: legacy
owner_task: OPT-ARC-001
review_after: 2026-12-01
lifecycle_state: archived
---
# Archived
""",
        )

        record = gen.collect_reports(self._config())[0]

        self.assertFalse(record.missing_supersession_target)
        self.assertEqual(record.lifecycle_state, "archived")
        self.assertNotIn("lifecycle_state", record.absent_core_lifecycle_fields)

    def test_supersession_target_diagnostics_render_lifecycle_state(self) -> None:
        self._write(
            "docs/reports/superseded.md",
            """---
id: docs.reports.superseded
title: Superseded
doc_type: report
status: deprecated
lifecycle_state: superseded
lifecycle: observed
owner_task: docs/tasks/superseded.md
review_after: 2026-12-01
---
# Superseded
""",
        )
        markdown = gen.render_inventory(gen.collect_reports(self._config()))
        self.assertIn("## Supersession Target Diagnostics", markdown)
        self.assertIn("| Path | lifecycle_state | Diagnostic |", markdown)
        self.assertIn(
            "| docs/reports/superseded.md | superseded | missing superseded_by target |",
            markdown,
        )

    def test_relations_are_rendered_in_markdown_output(self) -> None:
        self._write(
            "docs/reports/rel.md",
            """---
id: docs.reports.rel
title: Relation
doc_type: report
status: active
relations:
  - type: relates_to
    target: docs/reports/other.md
---
# Relation
""",
        )

        markdown = gen.render_inventory(gen.collect_reports(self._config()))

        self.assertIn("files_with_lifecycle_state", markdown)
        self.assertIn("files_missing_lifecycle_state", markdown)
        self.assertIn("| Path | doc_type | status | lifecycle_state |", markdown)
        self.assertIn("supersession target diagnostic", markdown)
        self.assertIn("## Relations", markdown)
        self.assertIn("relates_to", markdown)
        self.assertIn("docs/reports/other.md", markdown)

    def test_relation_target_pipe_is_escaped_in_markdown_table(self) -> None:
        self._write(
            "docs/reports/rel.md",
            """---
id: docs.reports.rel
title: Relation
doc_type: report
status: active
relations:
  - type: relates_to
    target: docs/reports/other|broken.md
---
# Relation
""",
        )

        markdown = gen.render_inventory(gen.collect_reports(self._config()))

        self.assertIn("docs/reports/other&#124;broken.md", markdown)
        self.assertNotIn("docs/reports/other|broken.md", markdown)

    def test_doc_type_distribution_is_rendered(self) -> None:
        self._write("docs/reports/a.md", "---\ndoc_type: report\nstatus: active\n---\n")
        self._write("docs/reports/b.md", "---\ndoc_type: reference\nstatus: active\n---\n")

        markdown = gen.render_inventory(gen.collect_reports(self._config()))

        self.assertIn("## Doc Type Distribution", markdown)
        self.assertIn("| report | 1 |", markdown)
        self.assertIn("| reference | 1 |", markdown)

    def test_collect_reports_uses_config_instead_of_global_mutation(self) -> None:
        self._write("docs/reports/alpha.md", "---\nstatus: active\n---\n")

        records = gen.collect_reports(self._config())

        self.assertEqual([record.path for record in records], ["docs/reports/alpha.md"])

    def test_inventory_is_sorted_deterministically_by_path(self) -> None:
        self._write("docs/reports/zeta.md", "# Zeta\n")
        self._write("docs/reports/alpha.md", "# Alpha\n")

        records = gen.collect_reports(self._config())

        self.assertEqual([record.path for record in records], ["docs/reports/alpha.md", "docs/reports/zeta.md"])


def _rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


if __name__ == "__main__":
    unittest.main()
