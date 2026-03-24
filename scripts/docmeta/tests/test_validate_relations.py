import os
import tempfile
import unittest

from scripts.docmeta.validate_relations import (
    validate_relations,
    check_zone_relations_notice,
    ALLOWED_TYPES,
)
from scripts.docmeta.relations_parser import extract_relations_from_content


class TestValidateRelations(unittest.TestCase):
    """Tests for validate_relations() — the core validation logic."""

    def test_no_relations_field(self):
        errors = validate_relations("docs/foo.md", {})
        self.assertEqual(errors, [])

    def test_empty_relations_list(self):
        errors = validate_relations("docs/foo.md", {"relations": []})
        self.assertEqual(errors, [])

    def test_relations_not_a_list(self):
        errors = validate_relations("docs/foo.md", {"relations": "bad"})
        self.assertEqual(len(errors), 1)
        self.assertIn("must be a list", errors[0])

    def test_valid_relation(self):
        # Create a temp file to act as the target
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", dir=os.environ.get("REPO_ROOT", "."), delete=False
        ) as f:
            f.write("---\nid: test\n---\n")
            target_path = os.path.relpath(f.name, os.environ.get("REPO_ROOT", "."))

        try:
            fm = {"relations": [{"type": "relates_to", "target": target_path}]}
            errors = validate_relations("docs/bar.md", fm)
            self.assertEqual(errors, [])
        finally:
            os.remove(f.name)

    def test_unknown_type(self):
        fm = {"relations": [{"type": "implements", "target": "docs/something.md"}]}
        errors = validate_relations("docs/foo.md", fm)
        self.assertTrue(any("unknown relation type 'implements'" in e for e in errors))

    def test_missing_type(self):
        fm = {"relations": [{"target": "docs/something.md"}]}
        errors = validate_relations("docs/foo.md", fm)
        self.assertTrue(any("missing required key 'type'" in e for e in errors))

    def test_missing_target(self):
        fm = {"relations": [{"type": "relates_to"}]}
        errors = validate_relations("docs/foo.md", fm)
        self.assertTrue(any("missing required key 'target'" in e for e in errors))

    def test_empty_target(self):
        fm = {"relations": [{"type": "relates_to", "target": ""}]}
        errors = validate_relations("docs/foo.md", fm)
        self.assertTrue(any("'target' must be a non-empty string" in e for e in errors))

    def test_absolute_path_rejected(self):
        fm = {"relations": [{"type": "relates_to", "target": "/docs/foo.md"}]}
        errors = validate_relations("docs/bar.md", fm)
        self.assertTrue(any("repo-root-relative, not absolute" in e for e in errors))

    def test_nonexistent_target(self):
        fm = {"relations": [{"type": "relates_to", "target": "docs/does-not-exist-12345.md"}]}
        errors = validate_relations("docs/foo.md", fm)
        self.assertTrue(any("does not exist" in e for e in errors))

    def test_self_reference(self):
        fm = {"relations": [{"type": "relates_to", "target": "docs/foo.md"}]}
        errors = validate_relations("docs/foo.md", fm)
        self.assertTrue(any("self-reference" in e for e in errors))

    def test_duplicate_relation(self):
        fm = {
            "relations": [
                {"type": "relates_to", "target": "docs/target.md"},
                {"type": "relates_to", "target": "docs/target.md"},
            ]
        }
        errors = validate_relations("docs/foo.md", fm)
        self.assertTrue(any("duplicate relation" in e for e in errors))

    def test_extra_keys_rejected(self):
        fm = {"relations": [{"type": "relates_to", "target": "docs/t.md", "label": "x"}]}
        errors = validate_relations("docs/foo.md", fm)
        self.assertTrue(any("unexpected keys" in e for e in errors))

    def test_entry_not_dict(self):
        fm = {"relations": ["just a string"]}
        errors = validate_relations("docs/foo.md", fm)
        self.assertTrue(any("expected object" in e for e in errors))

    def test_allowed_types_exactly_three(self):
        self.assertEqual(ALLOWED_TYPES, {"relates_to", "depends_on", "supersedes"})

    def test_path_traversal_rejected(self):
        """Targets with .. segments that escape the repo root must be rejected."""
        fm = {"relations": [{"type": "relates_to", "target": "../../etc/passwd"}]}
        errors = validate_relations("docs/foo.md", fm)
        self.assertTrue(any("escapes repository root" in e or "does not exist" in e for e in errors))

    def test_path_traversal_within_repo_ok(self):
        """A target using .. but still resolving within the repo should not trigger
        the traversal error (though it may fail the existence check)."""
        # docs/../docs/foo.md resolves to docs/foo.md which is within repo
        fm = {"relations": [{"type": "relates_to", "target": "docs/../docs/foo.md"}]}
        errors = validate_relations("docs/bar.md", fm)
        # Should NOT contain path traversal error
        self.assertFalse(any("escapes repository root" in e for e in errors))


class TestExtractRelationsFromContent(unittest.TestCase):
    """Tests for extract_relations_from_content() — the YAML parser."""

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

    def test_empty_relations_list(self):
        content = "---\nid: test\nrelations: []\n---\nbody\n"
        rels = extract_relations_from_content(content)
        self.assertEqual(rels, [])

    def test_no_relations_field(self):
        content = "---\nid: test\ntitle: Hello\n---\nbody\n"
        rels = extract_relations_from_content(content)
        self.assertEqual(rels, [])

    def test_no_frontmatter(self):
        content = "Just a markdown file without frontmatter."
        rels = extract_relations_from_content(content)
        self.assertEqual(rels, [])

    def test_relations_with_other_fields(self):
        content = (
            "---\n"
            "id: test\n"
            "title: Title\n"
            "relations:\n"
            "  - type: depends_on\n"
            "    target: docs/dep.md\n"
            "verifies_with:\n"
            "  - scripts/check.py\n"
            "---\n"
        )
        rels = extract_relations_from_content(content)
        self.assertEqual(len(rels), 1)
        self.assertEqual(rels[0], {"type": "depends_on", "target": "docs/dep.md"})

    def test_single_relation(self):
        content = (
            "---\n"
            "id: test\n"
            "relations:\n"
            "  - type: relates_to\n"
            "    target: docs/only-one.md\n"
            "---\n"
        )
        rels = extract_relations_from_content(content)
        self.assertEqual(len(rels), 1)
        self.assertEqual(rels[0]["target"], "docs/only-one.md")

    def test_extra_keys_preserved_in_parser(self):
        """Extra keys must survive parsing so validate_relations() can reject them."""
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

    def test_missing_target_preserved(self):
        """Entry with type but no target must be returned (not silently dropped)."""
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

    def test_missing_type_preserved(self):
        """Entry with target but no type must be returned (not silently dropped)."""
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

    def test_extra_keys_caught_end_to_end(self):
        """Integration: extra keys in raw content produce validation errors."""
        content = (
            "---\n"
            "id: test\n"
            "relations:\n"
            "  - type: relates_to\n"
            "    target: docs/foo.md\n"
            "    note: extra\n"
            "---\n"
        )
        rels = extract_relations_from_content(content)
        fm = {"relations": rels}
        errors = validate_relations("docs/test.md", fm)
        self.assertTrue(any("unexpected keys" in e for e in errors))

    def test_missing_type_caught_end_to_end(self):
        """Integration: entry with no type in raw content produces validation error."""
        content = (
            "---\n"
            "id: test\n"
            "relations:\n"
            "  - target: docs/foo.md\n"
            "---\n"
        )
        rels = extract_relations_from_content(content)
        fm = {"relations": rels}
        errors = validate_relations("docs/test.md", fm)
        self.assertTrue(any("missing required key 'type'" in e for e in errors))

    def test_missing_target_caught_end_to_end(self):
        """Integration: entry with no target in raw content produces validation error."""
        content = (
            "---\n"
            "id: test\n"
            "relations:\n"
            "  - type: relates_to\n"
            "---\n"
        )
        rels = extract_relations_from_content(content)
        fm = {"relations": rels}
        errors = validate_relations("docs/test.md", fm)
        self.assertTrue(any("missing required key 'target'" in e for e in errors))


class TestZoneRelationsNotice(unittest.TestCase):
    """Tests for check_zone_relations_notice() — the decision gate trigger."""

    def test_empty_zone_relations_no_notice(self):
        """Zone files with only relations: [] should not trigger a notice."""
        with tempfile.TemporaryDirectory() as tmpdir:
            zone = os.path.join(tmpdir, "architecture")
            os.makedirs(zone)
            with open(os.path.join(zone, "test.md"), "w") as f:
                f.write("---\nid: test\nrelations: []\n---\n")
            result = check_zone_relations_notice(tmpdir)
            self.assertEqual(result, [])

    def test_nonempty_zone_relations_triggers_notice(self):
        """Zone files with actual relations should trigger a notice."""
        with tempfile.TemporaryDirectory() as tmpdir:
            zone = os.path.join(tmpdir, "architecture")
            os.makedirs(zone)
            with open(os.path.join(zone, "test.md"), "w") as f:
                f.write(
                    "---\nid: test\nrelations:\n"
                    "  - type: relates_to\n"
                    "    target: docs/foo.md\n"
                    "---\n"
                )
            result = check_zone_relations_notice(tmpdir)
            self.assertEqual(result, ["architecture/test.md"])

    def test_notice_emits_to_stderr(self):
        """When triggered, the notice must be written to stderr (not stdout)."""
        import io
        from contextlib import redirect_stderr

        with tempfile.TemporaryDirectory() as tmpdir:
            zone = os.path.join(tmpdir, "runtime")
            os.makedirs(zone)
            with open(os.path.join(zone, "doc.md"), "w") as f:
                f.write(
                    "---\nid: rt\nrelations:\n"
                    "  - type: depends_on\n"
                    "    target: docs/dep.md\n"
                    "---\n"
                )
            buf = io.StringIO()
            with redirect_stderr(buf):
                check_zone_relations_notice(tmpdir)
            output = buf.getvalue()
            self.assertIn("NOTICE", output)
            self.assertIn("decision gate triggered", output)

    def test_no_zone_dirs_no_notice(self):
        """When zone directories don't exist, no notice is emitted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = check_zone_relations_notice(tmpdir)
            self.assertEqual(result, [])

    def test_multiple_zone_files_listed(self):
        """All zone files with relations should appear in the result."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for zone_name in ("architecture", "runbooks"):
                zone = os.path.join(tmpdir, zone_name)
                os.makedirs(zone)
                with open(os.path.join(zone, "doc.md"), "w") as f:
                    f.write(
                        "---\nid: x\nrelations:\n"
                        "  - type: relates_to\n"
                        "    target: docs/x.md\n"
                        "---\n"
                    )
            result = check_zone_relations_notice(tmpdir)
            self.assertEqual(len(result), 2)
            paths = [os.path.basename(os.path.dirname(p)) for p in result]
            self.assertIn("architecture", paths)
            self.assertIn("runbooks", paths)


if __name__ == "__main__":
    unittest.main()
