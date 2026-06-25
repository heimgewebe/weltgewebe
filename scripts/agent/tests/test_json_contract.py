from __future__ import annotations

import unittest

from scripts.agent.json_contract import (
    DuplicateKeyError,
    UnsupportedSchemaError,
    loads_json_strict,
    validate_instance,
)


class TestJsonContract(unittest.TestCase):
    def test_duplicate_key_is_rejected(self):
        with self.assertRaises(DuplicateKeyError):
            loads_json_strict('{"x":1,"x":2}')

    def test_non_standard_constant_is_rejected(self):
        with self.assertRaises(ValueError):
            loads_json_strict('{"x":NaN}')

    def test_required_field_has_one_violation(self):
        schema = {
            "type": "object",
            "required": ["items"],
            "additionalProperties": False,
            "properties": {"items": {"type": "array"}},
        }
        self.assertEqual(
            validate_instance({}, schema),
            [{"path": "$.items", "message": "required field is missing"}],
        )

    def test_ref_allof_and_unique_items(self):
        schema = {
            "type": "object",
            "properties": {
                "items": {
                    "allOf": [
                        {"$ref": "#/definitions/strings"},
                        {"minItems": 1},
                    ]
                }
            },
            "definitions": {
                "strings": {
                    "type": "array",
                    "uniqueItems": True,
                    "items": {"type": "string"},
                }
            },
        }
        self.assertEqual(
            validate_instance({"items": ["x", "x"]}, schema)[0]["message"],
            "duplicate array item",
        )

    def test_unknown_keyword_fails_closed(self):
        with self.assertRaises(UnsupportedSchemaError):
            validate_instance("x", {"type": "string", "format": "uuid"})

    def test_invalid_keyword_value_fails_closed(self):
        with self.assertRaises(UnsupportedSchemaError):
            validate_instance([], {"type": "array", "uniqueItems": "yes"})


if __name__ == "__main__":
    unittest.main()
