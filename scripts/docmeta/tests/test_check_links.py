import os
import unittest
import tempfile
import json
import shutil

class TestCheckLinks(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.repo_root = os.path.join(self.temp_dir, 'repo')
        os.makedirs(self.repo_root)

        # Create architecture directory
        self.arch_dir = os.path.join(self.repo_root, 'architecture')
        os.makedirs(self.arch_dir)

        self.doc_path = os.path.join(self.arch_dir, 'test_doc.md')

        # Create artifacts dir
        self.artifacts_dir = os.path.join(self.repo_root, 'artifacts', 'docmeta')
        os.makedirs(self.artifacts_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def run_check_links(self, doc_content, index_content=None, mode='strict'):
        import scripts.docmeta.check_links as cl
        from unittest.mock import patch

        with open(self.doc_path, 'w') as f:
            f.write(doc_content)

        if index_content is not None:
            with open(os.path.join(self.artifacts_dir, 'docs.index.json'), 'w') as f:
                json.dump(index_content, f)

        # Mock the functions to return our test paths
        def mock_parse_repo_index(strict_manifest=False):
            return {"zones": {"norm": {"path": "architecture", "canonical_docs": ["test_doc.md"]}}}

        def mock_parse_review_policy():
            return {"mode": mode, "strict_manifest": False}

        with patch('scripts.docmeta.check_links.parse_repo_index', side_effect=mock_parse_repo_index), \
             patch('scripts.docmeta.check_links.parse_review_policy', side_effect=mock_parse_review_policy), \
             patch('scripts.docmeta.check_links.REPO_ROOT', self.repo_root):

             # Capture stdout and stderr
             import io
             from contextlib import redirect_stdout, redirect_stderr

             f_out = io.StringIO()
             f_err = io.StringIO()

             with redirect_stdout(f_out), redirect_stderr(f_err):
                 try:
                     cl.main()
                     exit_code = 0
                 except SystemExit as e:
                     exit_code = e.code

             return exit_code, f_out.getvalue(), f_err.getvalue()

    def test_doc_link_without_id_strict(self):
        """1. doc: Link ohne ID -> Malformed, mode-strict = failure"""
        exit_code, out, err = self.run_check_links("This is a [link](doc:)", index_content={"docs": []}, mode='strict')
        self.assertEqual(exit_code, 1)
        self.assertIn("Malformed doc: link", err)
        self.assertIn("missing canonical ID", err)

    def test_doc_link_without_id_warn(self):
        """1. doc: Link ohne ID -> Malformed, mode-warn = warning"""
        exit_code, out, err = self.run_check_links("This is a [link](doc:)", index_content={"docs": []}, mode='warn')
        self.assertEqual(exit_code, 0)
        self.assertIn("Malformed doc: link", err)
        self.assertIn("missing canonical ID", err)

    def test_doc_link_unknown_id_strict(self):
        """2. doc:unknown.id -> broken, mode-strict = failure"""
        exit_code, out, err = self.run_check_links("This is a [link](doc:unknown.id)", index_content={"docs": []}, mode='strict')
        self.assertEqual(exit_code, 1)
        self.assertIn("Broken link", err)
        self.assertIn("does not exist", err)

    def test_doc_link_known_id(self):
        """3. doc:known.id bei vorhandenem index -> pass"""
        index = {"docs": [{"id": "known.id"}]}
        exit_code, out, err = self.run_check_links("This is a [link](doc:known.id)", index_content=index, mode='strict')
        self.assertEqual(exit_code, 0)
        self.assertNotIn("Broken link", err)

    def test_missing_index_warn(self):
        """4a. index fehlt, doc: links existieren, warn -> kein exit 1"""
        exit_code, out, err = self.run_check_links("This is a [link](doc:some.id)", index_content=None, mode='warn')
        self.assertEqual(exit_code, 0)
        self.assertIn("Docs index missing", err)

    def test_missing_index_strict(self):
        """4b. index fehlt, doc: links existieren, strict -> exit 1"""
        exit_code, out, err = self.run_check_links("This is a [link](doc:some.id)", index_content=None, mode='strict')
        self.assertEqual(exit_code, 1)
        self.assertIn("Docs index missing", err)

    def test_doc_link_fragment(self):
        """5. doc:known.id#sec mit Index -> pass"""
        index = {"docs": [{"id": "known.id"}]}
        exit_code, out, err = self.run_check_links("This is a [link](doc:known.id#sec)", index_content=index, mode='strict')
        self.assertEqual(exit_code, 0)
        self.assertNotIn("Broken link", err)
        self.assertNotIn("Errors", err)

    def test_file_link_fragment(self):
        """6. architecture/overview.md#sec -> prüft Datei-Existenz ohne Fragment"""
        # Create the file it points to
        with open(os.path.join(self.arch_dir, 'overview.md'), 'w') as f:
            f.write("content")

        exit_code, out, err = self.run_check_links("This is a [link](overview.md#sec)", index_content=None, mode='strict')
        self.assertEqual(exit_code, 0)
        self.assertNotIn("Broken link", err)

if __name__ == '__main__':
    unittest.main()
