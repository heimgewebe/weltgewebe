import os
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch
import io
from contextlib import redirect_stdout, redirect_stderr

from scripts.docmeta.export_docs_index import main

class TestExportDocsIndex(unittest.TestCase):
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

        # Doc 1: Normal doc
        self._write_doc("architecture/doc1.md", "---\nid: doc-1\nrole: norm\n---\n")

        # Doc 2: Different doc
        self._write_doc("architecture/doc2.md", "---\nid: doc-2\nrole: reality\n---\n")

        # Doc 3: Duplicate ID as Doc 1
        self._write_doc("architecture/doc3.md", "---\nid: doc-1\nrole: norm\n---\n")

    def _write_doc(self, relpath, content):
        full_path = os.path.normpath(os.path.join(self.temp_dir, relpath))
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    @patch('scripts.docmeta.export_docs_index.parse_review_policy')
    @patch('scripts.docmeta.export_docs_index.parse_repo_index')
    def test_export_docs_index_warn_mode(self, mock_parse_repo_index, mock_parse_review_policy):
        mock_parse_review_policy.return_value = {"mode": "warn", "strict_manifest": False}
        mock_parse_repo_index.return_value = self.repo_index

        captured_output = io.StringIO()
        captured_error = io.StringIO()

        with redirect_stdout(captured_output), redirect_stderr(captured_error):
            with patch('scripts.docmeta.export_docs_index.REPO_ROOT', self.temp_dir):
                main()

        # Assert output JSON exists
        json_path = os.path.join(self.temp_dir, "artifacts", "docmeta", "docs.index.json")
        self.assertTrue(os.path.exists(json_path))

        # Assert duplicate ID warning was printed to stderr
        err_out = captured_error.getvalue()
        self.assertIn("Warning: Duplicate ID 'doc-1'", err_out)
        self.assertIn("'architecture/doc1.md' and 'architecture/doc3.md'", err_out)
        self.assertIn("Overwriting.", err_out)

        # Assert JSON deduplicated the ID
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        docs = data.get("docs") if isinstance(data, dict) else data
        if docs is None:
            docs = []

        self.assertIsInstance(docs, list)

        doc_1_entries = [d for d in docs if d.get("id") == "doc-1"]
        self.assertEqual(len(doc_1_entries), 1)
        self.assertEqual(doc_1_entries[0].get("path"), "architecture/doc3.md")

    @patch('scripts.docmeta.export_docs_index.parse_review_policy')
    @patch('scripts.docmeta.export_docs_index.parse_repo_index')
    def test_export_docs_index_strict_mode(self, mock_parse_repo_index, mock_parse_review_policy):
        mock_parse_review_policy.return_value = {"mode": "strict", "strict_manifest": True}
        mock_parse_repo_index.return_value = self.repo_index

        captured_output = io.StringIO()
        captured_error = io.StringIO()

        with self.assertRaises(SystemExit) as cm:
            with redirect_stdout(captured_output), redirect_stderr(captured_error):
                with patch('scripts.docmeta.export_docs_index.REPO_ROOT', self.temp_dir):
                    main()

        self.assertEqual(cm.exception.code, 1)

        # Assert duplicate ID error was printed to stderr
        err_out = captured_error.getvalue()
        self.assertIn("Error: Duplicate ID 'doc-1'", err_out)
        self.assertIn("'architecture/doc1.md' and 'architecture/doc3.md'", err_out)

if __name__ == '__main__':
    unittest.main()
