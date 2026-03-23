import unittest

from scripts.docmeta.validate_schema import validate_data_against_schema


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


if __name__ == '__main__':
    unittest.main()
