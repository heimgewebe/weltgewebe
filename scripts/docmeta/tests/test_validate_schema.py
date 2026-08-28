import json
import os
import tempfile
import unittest

from scripts.docmeta.docmeta import REPO_ROOT, parse_frontmatter
from scripts.docmeta.validate_schema import (
    parser_parity_errors,
    parse_frontmatter_with_pyyaml,
    validate_attention_source_paths,
    validate_attention_source_semantics,
    validate_attention_source_zone,
    validate_canonical_semantics,
    validate_data_against_schema,
)


class TestValidateDataAgainstSchema(unittest.TestCase):
    """Tests for the validate_data_against_schema pure function."""

    def test_valid_object_all_required_fields(self):
        schema = {
            "type": "object",
            "required": ["id", "title"],
            "properties": {
                "id": {"type": "string"},
                "title": {"type": "string"},
            },
        }
        data = {"id": "doc-1", "title": "My Document"}
        errors = validate_data_against_schema(data, schema)
        self.assertEqual(errors, [])

    def test_missing_required_field(self):
        schema = {
            "type": "object",
            "required": ["id", "title"],
            "properties": {
                "id": {"type": "string"},
                "title": {"type": "string"},
            },
        }
        data = {"id": "doc-1"}
        errors = validate_data_against_schema(data, schema)
        self.assertEqual(len(errors), 1)
        self.assertIn("title", errors[0])
        self.assertIn("missing required field", errors[0])

    def test_wrong_type_expected_object_got_string(self):
        schema = {"type": "object", "properties": {}}
        data = "not an object"
        errors = validate_data_against_schema(data, schema)
        self.assertEqual(len(errors), 1)
        self.assertIn("expected object", errors[0])
        self.assertIn("got str", errors[0])

    def test_string_enum_invalid_value(self):
        schema = {"type": "string", "enum": ["active", "draft", "archived"]}
        data = "deleted"
        errors = validate_data_against_schema(data, schema)
        self.assertEqual(len(errors), 1)
        self.assertIn("'deleted'", errors[0])
        self.assertIn("not one of", errors[0])

    def test_string_enum_valid_value(self):
        schema = {"type": "string", "enum": ["active", "draft", "archived"]}
        errors = validate_data_against_schema("active", schema)
        self.assertEqual(errors, [])

    def test_string_minlength_too_short(self):
        schema = {"type": "string", "minLength": 5}
        errors = validate_data_against_schema("ab", schema)
        self.assertEqual(len(errors), 1)
        self.assertIn("minLength", errors[0])

    def test_string_minlength_exact(self):
        schema = {"type": "string", "minLength": 3}
        errors = validate_data_against_schema("abc", schema)
        self.assertEqual(errors, [])

    def test_string_pattern_no_match(self):
        schema = {"type": "string", "pattern": r"^[a-z]+\.[a-z]+$"}
        errors = validate_data_against_schema("UPPER", schema)
        self.assertEqual(len(errors), 1)
        self.assertIn("does not match pattern", errors[0])

    def test_string_pattern_match(self):
        schema = {"type": "string", "pattern": r"^[a-z]+\.[a-z]+$"}
        errors = validate_data_against_schema("foo.bar", schema)
        self.assertEqual(errors, [])

    def test_array_items_schema_applied(self):
        schema = {
            "type": "array",
            "items": {"type": "string", "minLength": 2},
        }
        data = ["ok", "x"]
        errors = validate_data_against_schema(data, schema)
        self.assertEqual(len(errors), 1)
        self.assertIn("[1]", errors[0])
        self.assertIn("minLength", errors[0])

    def test_array_all_valid_items(self):
        schema = {
            "type": "array",
            "items": {"type": "string"},
        }
        errors = validate_data_against_schema(["a", "b", "c"], schema)
        self.assertEqual(errors, [])

    def test_array_wrong_type(self):
        schema = {"type": "array", "items": {"type": "string"}}
        errors = validate_data_against_schema("not a list", schema)
        self.assertEqual(len(errors), 1)
        self.assertIn("expected array", errors[0])

    def test_nested_object_validation(self):
        schema = {
            "type": "object",
            "properties": {
                "meta": {
                    "type": "object",
                    "required": ["version"],
                    "properties": {
                        "version": {"type": "string"},
                    },
                }
            },
        }
        data = {"meta": {}}
        errors = validate_data_against_schema(data, schema)
        self.assertEqual(len(errors), 1)
        self.assertIn("root.meta", errors[0])
        self.assertIn("version", errors[0])

    def test_additional_properties_rejected(self):
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "id": {"type": "string"},
            },
        }
        data = {"id": "ok", "extra": "bad"}
        errors = validate_data_against_schema(data, schema)
        self.assertEqual(len(errors), 1)
        self.assertIn("unexpected property", errors[0])
        self.assertIn("extra", errors[0])

    def test_additional_properties_allowed_by_default(self):
        schema = {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
            },
        }
        data = {"id": "ok", "extra": "fine"}
        errors = validate_data_against_schema(data, schema)
        self.assertEqual(errors, [])

    def test_empty_data_no_required_fields(self):
        schema = {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
            },
        }
        errors = validate_data_against_schema({}, schema)
        self.assertEqual(errors, [])


class TestCanonicalDocmetaSchema(unittest.TestCase):
    """Tests the real contracts/docmeta.schema.json against constructed frontmatter.

    Verifies that ``depends_on`` is a first-class array property and that both
    ``depends_on`` and ``verifies_with`` are mandatory for canonical documents.
    """

    @classmethod
    def setUpClass(cls):
        schema_path = os.path.join(REPO_ROOT, "contracts", "docmeta.schema.json")
        with open(schema_path, "r", encoding="utf-8") as f:
            cls.schema = json.load(f)

    def _valid_frontmatter(self, **overrides):
        fm = {
            "id": "doc.test",
            "title": "Test Document",
            "summary": "A non-empty test summary.",
            "status": "canonical",
            "role": "norm",
            "organ": "product-ui",
            "last_reviewed": "2026-07-11",
            "canonicality": "normative",
            "lifecycle_state": "active",
            "owner": "product-ui",
            "review_after": "2026-10-11",
            "depends_on": [],
            "verifies_with": [],
        }
        fm.update(overrides)
        return fm


    def test_manifest_canonicality_rejects_supporting(self):
        fm = self._valid_frontmatter(canonicality="supporting")
        errors = validate_canonical_semantics(fm)
        self.assertTrue(any("canonicality" in error for error in errors), errors)

    def test_manifest_lifecycle_must_be_active(self):
        fm = self._valid_frontmatter(lifecycle_state="archived")
        errors = validate_canonical_semantics(fm)
        self.assertTrue(any("lifecycle_state" in error for error in errors), errors)

    def test_manifest_semantics_accept_normative_active(self):
        self.assertEqual(validate_canonical_semantics(self._valid_frontmatter()), [])

    def test_depends_on_is_a_declared_property(self):
        self.assertIn("depends_on", self.schema.get("properties", {}))
        self.assertEqual(self.schema["properties"]["depends_on"].get("type"), "array")

    def test_depends_on_and_verifies_with_are_required(self):
        required = self.schema.get("required", [])
        self.assertIn("depends_on", required)
        self.assertIn("verifies_with", required)

    def test_valid_with_empty_lists_passes(self):
        fm = self._valid_frontmatter()
        self.assertEqual(validate_data_against_schema(fm, self.schema), [])

    def test_valid_with_populated_depends_on_passes(self):
        fm = self._valid_frontmatter(depends_on=["other.doc"])
        self.assertEqual(validate_data_against_schema(fm, self.schema), [])

    def test_missing_depends_on_fails(self):
        fm = self._valid_frontmatter()
        del fm["depends_on"]
        errors = validate_data_against_schema(fm, self.schema)
        self.assertTrue(any("depends_on" in e and "missing required" in e for e in errors), errors)

    def test_missing_verifies_with_fails(self):
        fm = self._valid_frontmatter()
        del fm["verifies_with"]
        errors = validate_data_against_schema(fm, self.schema)
        self.assertTrue(any("verifies_with" in e and "missing required" in e for e in errors), errors)

    def test_depends_on_wrong_type_string_fails(self):
        fm = self._valid_frontmatter(depends_on="not-a-list")
        errors = validate_data_against_schema(fm, self.schema)
        self.assertTrue(any("depends_on" in e and "expected array" in e for e in errors), errors)

    def test_depends_on_list_item_wrong_type_fails(self):
        fm = self._valid_frontmatter(depends_on=["doc-a", 123])
        errors = validate_data_against_schema(fm, self.schema)
        self.assertTrue(
            any("depends_on" in e and "expected string" in e for e in errors),
            errors,
        )


class TestMarkdownToSchemaIntegration(unittest.TestCase):
    """End-to-end proof: real markdown frontmatter → parse_frontmatter() →
    schema validation against the real contracts/docmeta.schema.json.

    Unlike TestCanonicalDocmetaSchema (which constructs Python dicts), this
    exercises the actual parser strecke so that parser and schema are proven to
    share one semantics for depends_on/verifies_with."""

    @classmethod
    def setUpClass(cls):
        schema_path = os.path.join(REPO_ROOT, "contracts", "docmeta.schema.json")
        with open(schema_path, "r", encoding="utf-8") as f:
            cls.schema = json.load(f)

    def _validate_markdown(self, body):
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".md", encoding="utf-8"
        ) as f:
            f.write(body)
            temp_path = f.name
        try:
            fm = parse_frontmatter(temp_path)
            self.assertIsNotNone(fm, "parse_frontmatter returned None")
            return validate_data_against_schema(fm, self.schema)
        finally:
            os.remove(temp_path)

    _BASE = (
        "id: doc.test\n"
        "title: Test Document\n"
        "status: canonical\n"
        "summary: A non-empty test summary.\n"
        "role: norm\n"
        "organ: product-ui\n"
        "last_reviewed: 2026-07-11\n"
        "canonicality: normative\n"
        "lifecycle_state: active\n"
        "owner: product-ui\n"
        "review_after: 2026-10-11\n"
    )

    def test_empty_lists_pass(self):
        md = f"---\n{self._BASE}depends_on: []\nverifies_with: []\n---\n"
        self.assertEqual(self._validate_markdown(md), [])

    def test_block_list_depends_on_passes(self):
        md = f"---\n{self._BASE}depends_on:\n  - doc-a\nverifies_with: []\n---\n"
        self.assertEqual(self._validate_markdown(md), [])

    def test_missing_depends_on_fails(self):
        md = f"---\n{self._BASE}verifies_with: []\n---\n"
        errors = self._validate_markdown(md)
        self.assertTrue(
            any("depends_on" in e and "missing required" in e for e in errors), errors
        )

    def test_missing_verifies_with_fails(self):
        md = f"---\n{self._BASE}depends_on: []\n---\n"
        errors = self._validate_markdown(md)
        self.assertTrue(
            any("verifies_with" in e and "missing required" in e for e in errors), errors
        )

    def test_scalar_depends_on_is_type_error(self):
        md = f"---\n{self._BASE}depends_on: doc-a\nverifies_with: []\n---\n"
        errors = self._validate_markdown(md)
        self.assertTrue(
            any("depends_on" in e and "expected array" in e for e in errors), errors
        )


class TestParserParity(unittest.TestCase):
    def _temp_markdown(self, frontmatter):
        handle = tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".md", encoding="utf-8"
        )
        handle.write(f"---\n{frontmatter}\n---\n")
        handle.close()
        self.addCleanup(lambda: os.path.exists(handle.name) and os.remove(handle.name))
        return handle.name

    def test_supported_subset_matches_pyyaml(self):
        path = self._temp_markdown(
            "id: doc.test\n"
            "title: Test\n"
            "status: canonical\n"
            "depends_on:\n  - other.doc\n"
            "relations:\n  - type: relates_to\n    target: docs/other.md\n"
            "verifies_with: []"
        )
        mini = parse_frontmatter(path)
        self.assertEqual(parser_parity_errors(path, mini), [])
        self.assertEqual(parse_frontmatter_with_pyyaml(path), mini)

    def test_unsupported_folded_scalar_is_detected(self):
        path = self._temp_markdown(
            "id: doc.test\nsummary: >\n  folded text"
        )
        mini = parse_frontmatter(path)
        errors = parser_parity_errors(path, mini)
        self.assertTrue(any("summary" in error for error in errors), errors)


class TestAttentionSourceContract(unittest.TestCase):
    def test_missing_decision_fails(self):
        errors = validate_attention_source_semantics({})
        self.assertTrue(any("attention_source_status" in error for error in errors))

    def test_none_rejects_source_payload(self):
        frontmatter = {
            "attention_source_status": "none",
            "attention_source_rationale": "No personal facts.",
        }
        self.assertEqual(validate_attention_source_semantics(frontmatter), [])

        frontmatter["attention_source_facts"] = ["stale"]
        errors = validate_attention_source_semantics(frontmatter)
        self.assertTrue(any("must be absent" in error for error in errors), errors)

    def test_source_requires_evidence_projection_and_transitions(self):
        errors = validate_attention_source_semantics(
            {
                "attention_source_status": "source",
                "attention_source_rationale": "Personal facts exist.",
            }
        )
        for field in (
            "attention_source_facts",
            "attention_projection",
            "attention_transition_tests",
        ):
            self.assertTrue(any(field in error for error in errors), errors)

    def test_blocked_requires_missing_fact_and_bureau_task(self):
        errors = validate_attention_source_semantics(
            {
                "attention_source_status": "blocked",
                "attention_source_rationale": "Truth incomplete.",
            }
        )
        self.assertTrue(
            any("attention_missing_facts" in error for error in errors), errors
        )
        self.assertTrue(
            any("attention_followup_task" in error for error in errors), errors
        )

        valid = {
            "attention_source_status": "blocked",
            "attention_source_rationale": "Truth incomplete.",
            "attention_missing_facts": ["applicant_action_required"],
            "attention_followup_task": "BUREAU-ATTENTION-T001",
        }
        self.assertEqual(validate_attention_source_semantics(valid), [])

    def test_blocked_rejects_prefix_only_bureau_task(self):
        invalid = {
            "attention_source_status": "blocked",
            "attention_source_rationale": "Truth incomplete.",
            "attention_missing_facts": ["applicant_action_required"],
            "attention_followup_task": "BUREAU-T001 invalid suffix",
        }
        errors = validate_attention_source_semantics(invalid)
        self.assertTrue(
            any("attention_followup_task" in error for error in errors), errors
        )

    def test_attention_metadata_is_rejected_outside_product_zone(self):
        errors = validate_attention_source_zone(
            {
                "attention_source_status": "none",
                "attention_source_rationale": "Not a personal source.",
            },
            "norm",
        )
        self.assertTrue(any("only allowed" in error for error in errors), errors)
        self.assertEqual(
            validate_attention_source_zone(
                {"attention_source_status": "none"}, "product"
            ),
            [],
        )

    def test_source_paths_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            apps = os.path.join(tmp, "apps")
            os.makedirs(apps)
            projection = os.path.join(apps, "projection.ts")
            with open(projection, "w", encoding="utf-8"):
                pass
            errors = validate_attention_source_paths(
                {
                    "attention_source_status": "source",
                    "attention_projection": ["apps/projection.ts"],
                    "attention_transition_tests": ["../escape.test.ts"],
                },
                repo_root=tmp,
            )
            self.assertTrue(
                any("repository-relative" in error for error in errors), errors
            )

    def test_source_paths_reject_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            errors = validate_attention_source_paths(
                {
                    "attention_source_status": "source",
                    "attention_projection": ["apps/missing.ts"],
                    "attention_transition_tests": ["tests/missing.test.ts"],
                },
                repo_root=tmp,
            )
            self.assertEqual(len(errors), 2, errors)
            self.assertTrue(all("does not exist" in error for error in errors), errors)

    def test_source_paths_reject_symlink_escape(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            outside_file = os.path.join(outside, "projection.ts")
            with open(outside_file, "w", encoding="utf-8"):
                pass
            os.symlink(outside_file, os.path.join(tmp, "escape.ts"))
            errors = validate_attention_source_paths(
                {
                    "attention_source_status": "source",
                    "attention_projection": ["escape.ts"],
                    "attention_transition_tests": ["escape.ts"],
                },
                repo_root=tmp,
            )
            self.assertEqual(len(errors), 2, errors)
            self.assertTrue(all("escapes repository" in error for error in errors), errors)

    def test_parser_supports_attention_lists_with_yaml_parity(self):
        body = (
            "---\n"
            "id: x\n"
            "attention_source_facts:\n"
            "  - fact-a\n"
            "attention_projection:\n"
            "  - apps/a.ts\n"
            "attention_transition_tests:\n"
            "  - apps/a.test.ts\n"
            "attention_missing_facts: []\n"
            "---\n"
        )
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".md", encoding="utf-8"
        ) as handle:
            handle.write(body)
            path = handle.name
        try:
            parsed = parse_frontmatter(path)
            self.assertEqual(parsed["attention_source_facts"], ["fact-a"])
            self.assertEqual(parsed["attention_projection"], ["apps/a.ts"])
            self.assertEqual(
                parsed["attention_transition_tests"], ["apps/a.test.ts"]
            )
            self.assertEqual(parsed["attention_missing_facts"], [])
            self.assertEqual(parser_parity_errors(path, parsed), [])
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
