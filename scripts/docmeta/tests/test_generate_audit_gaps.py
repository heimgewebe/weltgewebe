import os
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch
import io
from contextlib import redirect_stdout, redirect_stderr

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

        # Doc 4: Duplicate ID with NO gaps (should clear previous)
        with open(os.path.join(self.temp_dir, "architecture", "doc4.md"), 'w', encoding='utf-8') as f:
            f.write("---\n"
                    "id: doc-no-gaps-override\n"
                    "---\n")

        with open(os.path.join(self.temp_dir, "architecture", "doc5.md"), 'w', encoding='utf-8') as f:
            f.write("---\n"
                    "id: doc-no-gaps-override\n"
                    "audit_gaps:\n"
                    "  - some gap\n"
                    "---\n")

        with open(os.path.join(self.temp_dir, "architecture", "doc6.md"), 'w', encoding='utf-8') as f:
            f.write("---\n"
                    "id: doc-no-gaps-override\n"
                    "---\n")

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    @patch('scripts.docmeta.generate_audit_gaps.parse_review_policy')
    @patch('scripts.docmeta.generate_audit_gaps.parse_repo_index')
    def test_generate_audit_gaps_overwrite(self, mock_parse_repo_index, mock_parse_review_policy):
        mock_parse_review_policy.return_value = {"mode": "warn", "strict_manifest": False}
        mock_parse_repo_index.return_value = self.repo_index

        # Redirect stdout and stderr
        captured_output = io.StringIO()
        captured_error = io.StringIO()

        with redirect_stdout(captured_output), redirect_stderr(captured_error):
            with patch('scripts.docmeta.generate_audit_gaps.REPO_ROOT', self.temp_dir):
                main()

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

    @patch('scripts.docmeta.generate_audit_gaps.parse_review_policy')
    @patch('scripts.docmeta.generate_audit_gaps.parse_repo_index')
    def test_generate_audit_gaps_clear_ghost_gaps(self, mock_parse_repo_index, mock_parse_review_policy):
        mock_parse_review_policy.return_value = {"mode": "warn", "strict_manifest": False}

        # Adjust canonical docs for this test
        repo_index_ghost = {
            "zones": {
                "norm": {
                    "path": "architecture/",
                    "canonical_docs": ["doc4.md", "doc5.md", "doc6.md"]
                }
            }
        }
        mock_parse_repo_index.return_value = repo_index_ghost

        # Redirect stdout and stderr
        captured_output = io.StringIO()
        captured_error = io.StringIO()

        with redirect_stdout(captured_output), redirect_stderr(captured_error):
            with patch('scripts.docmeta.generate_audit_gaps.REPO_ROOT', self.temp_dir):
                main()

        # Assert output JSON
        json_path = os.path.join(self.temp_dir, "artifacts", "docmeta", "audit_gaps.json")
        self.assertTrue(os.path.exists(json_path))

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # doc5 introduces a gap, but doc6 (last) clears it.
        self.assertEqual(data["total_gaps"], 0)
        self.assertEqual(data["documents_with_gaps"], 0)
        self.assertNotIn("doc-no-gaps-override", data["gaps"])

        # Assert duplicate ID warning was printed to stderr
        err_out = captured_error.getvalue()
        self.assertIn("Warning: Duplicate ID 'doc-no-gaps-override' found", err_out)

if __name__ == '__main__':
    unittest.main()
