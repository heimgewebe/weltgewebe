import os
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch
import sys
import io

from scripts.docmeta.generate_audit_gaps import main

class TestGenerateAuditGaps(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

        # Mock repo index structure
        self.repo_index = {
            "zones": {
                "norm": {
                    "path": "architecture/",
                    "canonical_docs": ["doc1.md", "doc2.md", "doc3.md"]
                }
            }
        }

        # Create directories
        os.makedirs(os.path.join(self.temp_dir, "architecture"))

        # Doc 1: Normal with gaps
        with open(os.path.join(self.temp_dir, "architecture", "doc1.md"), 'w', encoding='utf-8') as f:
            f.write("---\n"
                    "id: doc-1\n"
                    "audit_gaps:\n"
                    "  - gap 1 in doc 1\n"
                    "  - gap 2 in doc 1\n"
                    "---\n")

        # Doc 2: No gaps
        with open(os.path.join(self.temp_dir, "architecture", "doc2.md"), 'w', encoding='utf-8') as f:
            f.write("---\n"
                    "id: doc-2\n"
                    "---\n")

        # Doc 3: Duplicate ID as Doc 1 to test overwriting and total_gaps count
        with open(os.path.join(self.temp_dir, "architecture", "doc3.md"), 'w', encoding='utf-8') as f:
            f.write("---\n"
                    "id: doc-1\n"
                    "audit_gaps:\n"
                    "  - overriding gap\n"
                    "---\n")

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    @patch('scripts.docmeta.generate_audit_gaps.parse_review_policy')
    @patch('scripts.docmeta.generate_audit_gaps.parse_repo_index')
    def test_generate_audit_gaps(self, mock_parse_repo_index, mock_parse_review_policy):
        mock_parse_review_policy.return_value = {"mode": "warn", "strict_manifest": False}
        mock_parse_repo_index.return_value = self.repo_index

        # Redirect stdout and stderr
        captured_output = io.StringIO()
        captured_error = io.StringIO()
        sys.stdout = captured_output
        sys.stderr = captured_error

        try:
            with patch('scripts.docmeta.generate_audit_gaps.REPO_ROOT', self.temp_dir):
                main()
        finally:
            sys.stdout = sys.__stdout__
            sys.stderr = sys.__stderr__

        # Assert output JSON
        json_path = os.path.join(self.temp_dir, "artifacts", "docmeta", "audit_gaps.json")
        self.assertTrue(os.path.exists(json_path))

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Total gaps should be 1 (because doc3 overrides doc1's 2 gaps with its 1 gap)
        self.assertEqual(data["total_gaps"], 1)
        self.assertEqual(data["documents_with_gaps"], 1)
        self.assertIn("doc-1", data["gaps"])
        self.assertEqual(data["gaps"]["doc-1"]["gaps"], ["overriding gap"])
        self.assertEqual(data["gaps"]["doc-1"]["file"], "architecture/doc3.md")

        # Assert duplicate ID warning was printed to stderr
        err_out = captured_error.getvalue()
        self.assertIn("Warning: Duplicate ID 'doc-1' found", err_out)
        self.assertIn("Overwriting previous entries", err_out)

if __name__ == '__main__':
    unittest.main()
