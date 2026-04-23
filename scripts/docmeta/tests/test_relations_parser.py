"""
Tests for the centralized relations parser and cross-tool consistency.

Proves:
1. relations_parser.py is the single source of truth
2. All tools use the same parser (no divergent interpretations)
3. parse_frontmatter() handles relations as List[Dict]
4. collect_file_relations() works correctly
"""

import os
import tempfile
import unittest

from scripts.docmeta.relations_parser import (
    extract_relations_from_content,
    collect_file_relations,
)
from scripts.docmeta.docmeta import parse_frontmatter, extract_depends_on


class TestRelationsParserCentralized(unittest.TestCase):
    """Tests that the centralized parser is the canonical implementation."""

    def test_basic_extraction(self):
        content = (
            "---\n"
            "id: test\n"
            "relations:\n"
            "  - type: relates_to\n"
            "    target: docs/foo.md\n"
            "  - type: supersedes\n"
            "    target: docs/bar.md\n"
            "---\n"
            "body\n"
        )
        rels = extract_relations_from_content(content)
        self.assertEqual(len(rels), 2)
        self.assertEqual(rels[0], {"type": "relates_to", "target": "docs/foo.md"})
        self.assertEqual(rels[1], {"type": "supersedes", "target": "docs/bar.md"})

    def test_extra_keys_preserved(self):
        """Extra keys MUST survive parsing so validators can reject them."""
        content = (
            "---\n"
            "id: test\n"
            "relations:\n"
            "  - type: relates_to\n"
            "    target: docs/foo.md\n"
            "    label: something\n"
            "---\n"
        )
        rels = extract_relations_from_content(content)
        self.assertEqual(len(rels), 1)
        self.assertIn("label", rels[0])
        self.assertEqual(rels[0]["label"], "something")

    def test_missing_type_not_dropped(self):
        """Entry with target but no type must NOT be silently dropped."""
        content = (
            "---\n"
            "id: test\n"
            "relations:\n"
            "  - target: docs/foo.md\n"
            "---\n"
        )
        rels = extract_relations_from_content(content)
        self.assertEqual(len(rels), 1)
        self.assertIn("target", rels[0])
        self.assertNotIn("type", rels[0])

    def test_missing_target_not_dropped(self):
        """Entry with type but no target must NOT be silently dropped."""
        content = (
            "---\n"
            "id: test\n"
            "relations:\n"
            "  - type: relates_to\n"
            "---\n"
        )
        rels = extract_relations_from_content(content)
        self.assertEqual(len(rels), 1)
        self.assertIn("type", rels[0])
        self.assertNotIn("target", rels[0])

    def test_empty_relations_list(self):
        content = "---\nid: test\nrelations: []\n---\nbody\n"
        rels = extract_relations_from_content(content)
        self.assertEqual(rels, [])

    def test_no_frontmatter(self):
        content = "Just a markdown file."
        rels = extract_relations_from_content(content)
        self.assertEqual(rels, [])

    def test_bare_list_item_returned_as_string(self):
        """Bare list items (not key-value dicts) are returned as strings."""
        content = (
            "---\n"
            "id: test\n"
            "relations:\n"
            "  - just-a-string\n"
            "---\n"
        )
        rels = extract_relations_from_content(content)
        self.assertEqual(len(rels), 1)
        self.assertIsInstance(rels[0], str)


class TestCollectFileRelations(unittest.TestCase):
    """Tests for collect_file_relations helper."""

    def test_collects_from_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = os.path.join(tmpdir, "docs")
            os.makedirs(docs_dir)

            # File with relations
            with open(os.path.join(docs_dir, "a.md"), "w") as f:
                f.write(
                    "---\nid: a\nrelations:\n"
                    "  - type: relates_to\n"
                    "    target: docs/b.md\n"
                    "---\n"
                )

            # File without relations
            with open(os.path.join(docs_dir, "b.md"), "w") as f:
                f.write("---\nid: b\nrelations: []\n---\n")

            result = collect_file_relations(["docs"], tmpdir)
            self.assertIn("docs/a.md", result)
            self.assertIn("docs/b.md", result)
            self.assertEqual(len(result["docs/a.md"]), 1)
            self.assertEqual(result["docs/a.md"][0]["type"], "relates_to")
            self.assertEqual(result["docs/b.md"], [])

    def test_excludes_generated(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gen_dir = os.path.join(tmpdir, "docs", "_generated")
            os.makedirs(gen_dir)
            with open(os.path.join(gen_dir, "index.md"), "w") as f:
                f.write("---\nid: gen\n---\n")

            result = collect_file_relations(["docs"], tmpdir)
            self.assertNotIn("docs/_generated/index.md", result)

    def test_nonexistent_dir_skipped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = collect_file_relations(["nonexistent"], tmpdir)
            self.assertEqual(result, {})


class TestParseFrontmatterRelations(unittest.TestCase):
    """Tests that parse_frontmatter() handles relations as List[Dict]."""

    def test_relations_as_list_of_dicts(self):
        content = (
            "---\n"
            "id: test\n"
            "title: Test\n"
            "relations:\n"
            "  - type: relates_to\n"
            "    target: docs/foo.md\n"
            "  - type: depends_on\n"
            "    target: docs/bar.md\n"
            "---\n"
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            path = f.name

        try:
            data = parse_frontmatter(path)
            self.assertIsNotNone(data)
            rels = data.get("relations", [])
            self.assertIsInstance(rels, list)
            self.assertEqual(len(rels), 2)
            # Must be dicts, not strings
            self.assertIsInstance(rels[0], dict)
            self.assertIsInstance(rels[1], dict)
            self.assertEqual(rels[0]["type"], "relates_to")
            self.assertEqual(rels[0]["target"], "docs/foo.md")
            self.assertEqual(rels[1]["type"], "depends_on")
            self.assertEqual(rels[1]["target"], "docs/bar.md")
        finally:
            os.remove(path)

    def test_empty_relations_inline(self):
        content = "---\nid: test\nrelations: []\n---\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            path = f.name

        try:
            data = parse_frontmatter(path)
            self.assertIsNotNone(data)
            self.assertEqual(data.get("relations"), [])
        finally:
            os.remove(path)

    def test_relations_with_extra_keys_preserved(self):
        """parse_frontmatter must preserve extra keys in relation dicts."""
        content = (
            "---\n"
            "id: test\n"
            "relations:\n"
            "  - type: relates_to\n"
            "    target: docs/foo.md\n"
            "    note: extra\n"
            "---\n"
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            path = f.name

        try:
            data = parse_frontmatter(path)
            rels = data.get("relations", [])
            self.assertEqual(len(rels), 1)
            self.assertIn("note", rels[0])
            self.assertEqual(rels[0]["note"], "extra")
        finally:
            os.remove(path)

    def test_relations_followed_by_other_fields(self):
        """Relations block followed by other fields must parse correctly."""
        content = (
            "---\n"
            "id: test\n"
            "relations:\n"
            "  - type: relates_to\n"
            "    target: docs/foo.md\n"
            "verifies_with:\n"
            "  - scripts/check.py\n"
            "---\n"
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            path = f.name

        try:
            data = parse_frontmatter(path)
            rels = data.get("relations", [])
            self.assertEqual(len(rels), 1)
            self.assertIsInstance(rels[0], dict)
            self.assertEqual(rels[0]["type"], "relates_to")
            vw = data.get("verifies_with", [])
            self.assertEqual(vw, ["scripts/check.py"])
        finally:
            os.remove(path)


class TestExtractDependsOnWithDicts(unittest.TestCase):
    """Tests that extract_depends_on works with proper dict-based relations."""

    def test_filters_depends_on(self):
        fm = {
            "relations": [
                {"type": "relates_to", "target": "docs/a.md"},
                {"type": "depends_on", "target": "docs/b.md"},
                {"type": "depends_on", "target": "docs/c.md"},
            ]
        }
        deps = extract_depends_on(fm)
        self.assertEqual(deps, ["docs/b.md", "docs/c.md"])

    def test_empty_relations(self):
        fm = {"relations": []}
        deps = extract_depends_on(fm)
        self.assertEqual(deps, [])

    def test_no_relations_key(self):
        fm = {}
        deps = extract_depends_on(fm)
        self.assertEqual(deps, [])


class TestParserContract(unittest.TestCase):
    """
    Contract-proving tests: explicitly verify what the parser supports
    and what it does NOT support.

    See architecture/docmeta.schema.md § Parser Contract for the normative
    specification.
    """

    # --- POSITIVE: supported subset ---

    def test_target_before_type(self):
        """Key order within an entry is irrelevant."""
        content = (
            "---\n"
            "id: test\n"
            "relations:\n"
            "  - target: docs/foo.md\n"
            "    type: relates_to\n"
            "---\n"
        )
        rels = extract_relations_from_content(content)
        self.assertEqual(len(rels), 1)
        self.assertEqual(rels[0]["type"], "relates_to")
        self.assertEqual(rels[0]["target"], "docs/foo.md")

    def test_double_quoted_values_stripped(self):
        """Double-quoted values have their quotes removed."""
        content = (
            "---\n"
            "id: test\n"
            "relations:\n"
            '  - type: "relates_to"\n'
            '    target: "docs/foo.md"\n'
            "---\n"
        )
        rels = extract_relations_from_content(content)
        self.assertEqual(len(rels), 1)
        self.assertEqual(rels[0]["type"], "relates_to")
        self.assertEqual(rels[0]["target"], "docs/foo.md")

    def test_single_quoted_values_stripped(self):
        """Single-quoted values have their quotes removed."""
        content = (
            "---\n"
            "id: test\n"
            "relations:\n"
            "  - type: 'relates_to'\n"
            "    target: 'docs/foo.md'\n"
            "---\n"
        )
        rels = extract_relations_from_content(content)
        self.assertEqual(len(rels), 1)
        self.assertEqual(rels[0]["type"], "relates_to")
        self.assertEqual(rels[0]["target"], "docs/foo.md")

    def test_blank_lines_between_entries(self):
        """Blank lines between relation entries are tolerated."""
        content = (
            "---\n"
            "id: test\n"
            "relations:\n"
            "  - type: relates_to\n"
            "    target: docs/a.md\n"
            "\n"
            "  - type: supersedes\n"
            "    target: docs/b.md\n"
            "---\n"
        )
        rels = extract_relations_from_content(content)
        self.assertEqual(len(rels), 2)
        self.assertEqual(rels[0]["target"], "docs/a.md")
        self.assertEqual(rels[1]["target"], "docs/b.md")

    def test_comment_lines_ignored(self):
        """Comment lines inside the relations block are skipped."""
        content = (
            "---\n"
            "id: test\n"
            "relations:\n"
            "  # this is a comment\n"
            "  - type: relates_to\n"
            "    target: docs/foo.md\n"
            "---\n"
        )
        rels = extract_relations_from_content(content)
        self.assertEqual(len(rels), 1)
        self.assertEqual(rels[0]["type"], "relates_to")
        self.assertEqual(rels[0]["target"], "docs/foo.md")

    def test_extra_keys_preserved_in_entry(self):
        """Additional keys beyond type/target survive for downstream checks."""
        content = (
            "---\n"
            "id: test\n"
            "relations:\n"
            "  - type: relates_to\n"
            "    target: docs/foo.md\n"
            "    label: important\n"
            "    note: extra info\n"
            "---\n"
        )
        rels = extract_relations_from_content(content)
        self.assertEqual(len(rels), 1)
        self.assertEqual(rels[0]["label"], "important")
        self.assertEqual(rels[0]["note"], "extra info")

    # --- NEGATIVE: explicitly unsupported ---

    def test_inline_mapping_not_parsed_correctly(self):
        """Inline mappings are NOT supported — not parsed into proper dicts."""
        content = (
            "---\n"
            "id: test\n"
            "relations:\n"
            "  - {type: relates_to, target: docs/foo.md}\n"
            "---\n"
        )
        rels = extract_relations_from_content(content)
        self.assertEqual(len(rels), 1)
        # The inline mapping is misinterpreted: the parser splits on the first
        # colon and produces a dict with a garbage key like "{type".  This is
        # acceptable — the downstream validator will reject the entry because
        # it lacks proper "type" and "target" keys.
        if isinstance(rels[0], dict):
            self.assertNotIn("type", rels[0])
            self.assertNotIn("target", rels[0])

    def test_mismatched_quotes_not_stripped(self):
        """Mismatched quotes are preserved (no partial stripping)."""
        content = (
            "---\n"
            "id: test\n"
            "relations:\n"
            "  - type: relates_to\n"
            "    target: \"docs/foo.md'\n"
            "---\n"
        )
        rels = extract_relations_from_content(content)
        self.assertEqual(len(rels), 1)
        # Mismatched quotes are NOT stripped
        self.assertEqual(rels[0]["target"], "\"docs/foo.md'")


class TestParserConsistency(unittest.TestCase):
    """
    Proves that the centralized parser and parse_frontmatter
    produce consistent results for the same input.
    """

    def test_same_relations_from_both_paths(self):
        """Both parsing paths must extract identical relation data."""
        content = (
            "---\n"
            "id: consistency-test\n"
            "title: Test\n"
            "status: active\n"
            "summary: Testing parser consistency.\n"
            "relations:\n"
            "  - type: relates_to\n"
            "    target: docs/vision.md\n"
            "  - type: depends_on\n"
            "    target: docs/datenmodell.md\n"
            "  - type: supersedes\n"
            "    target: docs/old.md\n"
            "---\n"
            "Body text.\n"
        )

        # Path 1: centralized parser
        rels_from_parser = extract_relations_from_content(content)

        # Path 2: parse_frontmatter
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            path = f.name

        try:
            fm = parse_frontmatter(path)
            rels_from_frontmatter = fm.get("relations", [])
        finally:
            os.remove(path)

        # Both must produce the same result
        self.assertEqual(len(rels_from_parser), len(rels_from_frontmatter))
        for p, f in zip(rels_from_parser, rels_from_frontmatter):
            self.assertEqual(p, f)


if __name__ == "__main__":
    unittest.main()
