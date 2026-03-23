import unittest

from scripts.docmeta.generate_knowledge_gaps import is_meaningful_gap


class TestIsMeaningfulGap(unittest.TestCase):
    """Tests for the is_meaningful_gap filter function."""

    def test_none_returns_false(self):
        self.assertFalse(is_meaningful_gap(None))

    def test_bool_true_returns_false(self):
        self.assertFalse(is_meaningful_gap(True))

    def test_bool_false_returns_false(self):
        self.assertFalse(is_meaningful_gap(False))

    def test_empty_string_returns_false(self):
        self.assertFalse(is_meaningful_gap(""))

    def test_placeholder_false(self):
        self.assertFalse(is_meaningful_gap("false"))

    def test_placeholder_true(self):
        self.assertFalse(is_meaningful_gap("true"))

    def test_placeholder_none(self):
        self.assertFalse(is_meaningful_gap("none"))

    def test_placeholder_null(self):
        self.assertFalse(is_meaningful_gap("null"))

    def test_placeholder_unknown(self):
        self.assertFalse(is_meaningful_gap("unknown"))

    def test_placeholder_na(self):
        self.assertFalse(is_meaningful_gap("n/a"))

    def test_placeholder_empty_list(self):
        self.assertFalse(is_meaningful_gap("[]"))

    def test_placeholder_empty_dict(self):
        self.assertFalse(is_meaningful_gap("{}"))

    def test_meaningful_string_gap_description(self):
        self.assertTrue(is_meaningful_gap("Missing authentication docs"))

    def test_meaningful_string_needs_review(self):
        self.assertTrue(is_meaningful_gap("Needs review"))

    def test_case_insensitivity_false_upper(self):
        self.assertFalse(is_meaningful_gap("FALSE"))

    def test_case_insensitivity_true_mixed(self):
        self.assertFalse(is_meaningful_gap("True"))

    def test_case_insensitivity_none_mixed(self):
        self.assertFalse(is_meaningful_gap("None"))

    def test_whitespace_only_returns_false(self):
        self.assertFalse(is_meaningful_gap("   "))

    def test_numeric_zero(self):
        # str(0).strip().lower() == "0" which is not a placeholder
        self.assertTrue(is_meaningful_gap(0))

    def test_numeric_nonzero(self):
        self.assertTrue(is_meaningful_gap(42))


if __name__ == '__main__':
    unittest.main()
