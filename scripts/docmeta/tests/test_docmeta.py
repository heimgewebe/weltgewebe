import os
import tempfile
import unittest

from scripts.docmeta.docmeta import parse_frontmatter, parse_repo_index, parse_review_policy

class TestDocMetaParser(unittest.TestCase):
    def test_parse_frontmatter_crlf_eof(self):
        content = "---\r\nid: test-id\r\nrole: norm\r\n---"
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name

        try:
            data = parse_frontmatter(temp_path)
            self.assertIsNotNone(data)
            self.assertEqual(data.get('id'), 'test-id')
            self.assertEqual(data.get('role'), 'norm')
        finally:
            os.remove(temp_path)

    def test_parse_frontmatter_spacing(self):
        content = "---\n id : test \n role : norm \n---\n"
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name

        try:
            data = parse_frontmatter(temp_path)
            self.assertIsNotNone(data)
            self.assertEqual(data.get('id'), 'test')
            self.assertEqual(data.get('role'), 'norm')
        finally:
            os.remove(temp_path)

class TestDocMetaStrictParsers(unittest.TestCase):
    def test_repo_index_typo_fail(self):
        content = "---\nzonez:\n  norm:\n    path: architecture/\n"
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name

        try:
            with self.assertRaisesRegex(ValueError, "Unknown key at root level 'zonez'"):
                parse_repo_index(manifest_path=temp_path, strict_manifest=True)
        finally:
            os.remove(temp_path)

    def test_strict_manifest_missing_canonical_docs_fails(self):
        content = "---\nzones:\n  norm:\n    path: architecture/\nchecks:\n"
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name

        try:
            with self.assertRaisesRegex(ValueError, "Strict Mode: Zone 'norm' has no canonical_docs."):
                parse_repo_index(manifest_path=temp_path, strict_manifest=True)
        finally:
            os.remove(temp_path)

    def test_review_policy_missing_mode(self):
        content = "---\ndefault_review_cycle_days: 90\n"
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name

        try:
            with self.assertRaisesRegex(ValueError, "Missing required key 'mode'"):
                parse_review_policy(policy_path=temp_path)
        finally:
            os.remove(temp_path)

    def test_review_policy_missing_cycle_days(self):
        content = "---\nmode: warn\n"
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name

        try:
            with self.assertRaisesRegex(ValueError, "Missing required key 'default_review_cycle_days'"):
                parse_review_policy(policy_path=temp_path)
        finally:
            os.remove(temp_path)

    def test_review_policy_invalid_days(self):
        content = "---\ndefault_review_cycle_days: x\nmode: warn\n"
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name

        try:
            with self.assertRaisesRegex(ValueError, "Invalid default_review_cycle_days.*Must be a positive integer."):
                parse_review_policy(policy_path=temp_path, strict_manifest=True)
        finally:
            os.remove(temp_path)

    def test_repo_index_excessive_whitespace(self):
        content = """
# some comments

zones:
  norm:
    path: architecture/
    canonical_docs:
      - doc1.md

      - doc2.md

checks:
  - check.py
"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name

        try:
            data = parse_repo_index(manifest_path=temp_path)
            self.assertEqual(len(data['zones']['norm']['canonical_docs']), 2)
            self.assertEqual(data['checks'][0], 'check.py')
        finally:
            os.remove(temp_path)

    def test_strict_manifest_empty_zones_fails(self):
        content = "---\nzones:\nchecks:\n"
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name

        try:
            with self.assertRaisesRegex(ValueError, "The 'zones' section cannot be empty when strict_manifest=True"):
                parse_repo_index(manifest_path=temp_path, strict_manifest=True)
        finally:
            os.remove(temp_path)

    def test_repo_index_malformed_missing_colon(self):
        content = "zones\n  norm:\n    path: architecture/\n"
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name

        try:
            with self.assertRaisesRegex(ValueError, "Expected key-value or key: at root level"):
                parse_repo_index(manifest_path=temp_path)
        finally:
            os.remove(temp_path)

    def test_review_policy_unknown_key_strict_fail(self):
        content = "---\ndefault_review_cycle_days: 90\nmode: warn\nstrict_manifest: true\nunknown_key: val\n"
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name

        try:
            with self.assertRaisesRegex(ValueError, "Unknown key 'unknown_key' in review policy"):
                parse_review_policy(policy_path=temp_path, strict_manifest=True)
        finally:
            os.remove(temp_path)

if __name__ == '__main__':
    unittest.main()
