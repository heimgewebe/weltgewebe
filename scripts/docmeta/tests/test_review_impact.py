import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

from scripts.docmeta.review_impact import main, _get_depends_on


class TestReviewImpact(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def _write_doc(self, relpath, content):
        full_path = os.path.normpath(os.path.join(self.temp_dir, relpath))
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def _load_impact_json(self):
        json_path = os.path.join(self.temp_dir, "artifacts", "docmeta", "impact.json")
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------
    @patch('scripts.docmeta.review_impact.parse_review_policy')
    @patch('scripts.docmeta.review_impact.parse_repo_index')
    def test_linear_chain_no_cycles(self, mock_parse_repo_index, mock_parse_review_policy):
        """A -> B -> C: no cycles, transitive impacts propagate."""
        mock_parse_review_policy.return_value = {
            "mode": "warn", "strict_manifest": False,
            "warn_days": 90, "fail_days": 180,
        }
        repo_index = {
            "zones": {
                "norm": {
                    "path": "docs/",
                    "canonical_docs": ["a.md", "b.md", "c.md"],
                }
            }
        }
        mock_parse_repo_index.return_value = repo_index

        # C has no deps, B depends on C, A depends on B
        self._write_doc("docs/c.md", "---\nid: doc-c\n---\n")
        self._write_doc("docs/b.md", "---\nid: doc-b\ndepends_on:\n  - doc-c\n---\n")
        self._write_doc("docs/a.md", "---\nid: doc-a\ndepends_on:\n  - doc-b\n---\n")

        captured_out = io.StringIO()
        captured_err = io.StringIO()
        with redirect_stdout(captured_out), redirect_stderr(captured_err):
            with patch('scripts.docmeta.review_impact.REPO_ROOT', self.temp_dir):
                main()

        data = self._load_impact_json()
        self.assertEqual(data["cycles"], [])

        # Changing doc-c should transitively impact both doc-b and doc-a
        impacts_c = data["impacts"]["doc-c"]["transitive_impacts"]
        self.assertIn("docs/b.md", impacts_c)
        self.assertIn("docs/a.md", impacts_c)

        # Changing doc-b should impact doc-a
        impacts_b = data["impacts"]["doc-b"]["transitive_impacts"]
        self.assertIn("docs/a.md", impacts_b)

        # doc-a has no dependents
        self.assertEqual(data["impacts"]["doc-a"]["transitive_impacts"], [])

    @patch('scripts.docmeta.review_impact.parse_review_policy')
    @patch('scripts.docmeta.review_impact.parse_repo_index')
    def test_simple_cycle_detected(self, mock_parse_repo_index, mock_parse_review_policy):
        """A -> B -> A: cycle detected."""
        mock_parse_review_policy.return_value = {
            "mode": "warn", "strict_manifest": False,
            "warn_days": 90, "fail_days": 180,
        }
        repo_index = {
            "zones": {
                "norm": {
                    "path": "docs/",
                    "canonical_docs": ["a.md", "b.md"],
                }
            }
        }
        mock_parse_repo_index.return_value = repo_index

        self._write_doc("docs/a.md", "---\nid: doc-a\ndepends_on:\n  - doc-b\n---\n")
        self._write_doc("docs/b.md", "---\nid: doc-b\ndepends_on:\n  - doc-a\n---\n")

        captured_out = io.StringIO()
        captured_err = io.StringIO()
        with redirect_stdout(captured_out), redirect_stderr(captured_err):
            with patch('scripts.docmeta.review_impact.REPO_ROOT', self.temp_dir):
                main()

        data = self._load_impact_json()
        self.assertGreater(len(data["cycles"]), 0)

        err = captured_err.getvalue()
        self.assertIn("cycle", err.lower())

    @patch('scripts.docmeta.review_impact.parse_review_policy')
    @patch('scripts.docmeta.review_impact.parse_repo_index')
    def test_no_dependencies(self, mock_parse_repo_index, mock_parse_review_policy):
        """No dependencies at all: no cycles, no impacts."""
        mock_parse_review_policy.return_value = {
            "mode": "warn", "strict_manifest": False,
            "warn_days": 90, "fail_days": 180,
        }
        repo_index = {
            "zones": {
                "norm": {
                    "path": "docs/",
                    "canonical_docs": ["a.md", "b.md"],
                }
            }
        }
        mock_parse_repo_index.return_value = repo_index

        self._write_doc("docs/a.md", "---\nid: doc-a\n---\n")
        self._write_doc("docs/b.md", "---\nid: doc-b\n---\n")

        captured_out = io.StringIO()
        captured_err = io.StringIO()
        with redirect_stdout(captured_out), redirect_stderr(captured_err):
            with patch('scripts.docmeta.review_impact.REPO_ROOT', self.temp_dir):
                main()

        data = self._load_impact_json()
        self.assertEqual(data["cycles"], [])
        self.assertEqual(data["impacts"]["doc-a"]["transitive_impacts"], [])
        self.assertEqual(data["impacts"]["doc-b"]["transitive_impacts"], [])

    @patch('scripts.docmeta.review_impact.parse_review_policy')
    @patch('scripts.docmeta.review_impact.parse_repo_index')
    def test_missing_id_strict_mode_exits(self, mock_parse_repo_index, mock_parse_review_policy):
        """Documents missing 'id' in strict mode should cause exit."""
        mock_parse_review_policy.return_value = {
            "mode": "strict", "strict_manifest": False,
            "warn_days": 90, "fail_days": 180,
        }
        repo_index = {
            "zones": {
                "norm": {
                    "path": "docs/",
                    "canonical_docs": ["no_id.md"],
                }
            }
        }
        mock_parse_repo_index.return_value = repo_index

        self._write_doc("docs/no_id.md", "---\ntitle: No ID\n---\n")

        captured_out = io.StringIO()
        captured_err = io.StringIO()
        with self.assertRaises(SystemExit) as ctx:
            with redirect_stdout(captured_out), redirect_stderr(captured_err):
                with patch('scripts.docmeta.review_impact.REPO_ROOT', self.temp_dir):
                    main()

        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("missing", captured_err.getvalue().lower())

    @patch('scripts.docmeta.review_impact.parse_review_policy')
    @patch('scripts.docmeta.review_impact.parse_repo_index')
    def test_json_artifact_structure(self, mock_parse_repo_index, mock_parse_review_policy):
        """Output JSON has expected top-level keys."""
        mock_parse_review_policy.return_value = {
            "mode": "warn", "strict_manifest": False,
            "warn_days": 90, "fail_days": 180,
        }
        repo_index = {
            "zones": {
                "norm": {
                    "path": "docs/",
                    "canonical_docs": ["a.md"],
                }
            }
        }
        mock_parse_repo_index.return_value = repo_index

        self._write_doc("docs/a.md", "---\nid: doc-a\n---\n")

        captured_out = io.StringIO()
        captured_err = io.StringIO()
        with redirect_stdout(captured_out), redirect_stderr(captured_err):
            with patch('scripts.docmeta.review_impact.REPO_ROOT', self.temp_dir):
                main()

        data = self._load_impact_json()
        self.assertIn("missing_ids", data)
        self.assertIn("cycles", data)
        self.assertIn("impacts", data)

        # Markdown artifact should also exist
        md_path = os.path.join(self.temp_dir, "artifacts", "docmeta", "impact.md")
        self.assertTrue(os.path.exists(md_path))


class TestGetDependsOn(unittest.TestCase):
    """Unit tests for the _get_depends_on helper."""

    def test_direct_depends_on_only(self):
        """Direct depends_on field is returned when present."""
        fm = {'depends_on': ['doc-x', 'doc-y']}
        self.assertEqual(_get_depends_on(fm), ['doc-x', 'doc-y'])

    def test_relations_fallback(self):
        """Relations array is used when depends_on is absent."""
        fm = {
            'relations': [
                {'type': 'depends_on', 'target': 'doc-z'},
            ],
        }
        self.assertEqual(_get_depends_on(fm), ['doc-z'])

    def test_dual_source_warns(self):
        """Warning emitted when both sources define depends_on."""
        fm = {
            'depends_on': ['doc-a'],
            'relations': [
                {'type': 'depends_on', 'target': 'doc-b'},
            ],
        }
        captured_err = io.StringIO()
        with redirect_stderr(captured_err):
            result = _get_depends_on(fm, doc_id='test-doc')
        # depends_on wins
        self.assertEqual(result, ['doc-a'])
        err = captured_err.getvalue()
        self.assertIn("Warning", err)
        self.assertIn("test-doc", err)
        self.assertIn("depends_on", err)

    def test_no_warning_single_source(self):
        """No warning when only one source provides data."""
        fm = {'depends_on': ['doc-a']}
        captured_err = io.StringIO()
        with redirect_stderr(captured_err):
            _get_depends_on(fm, doc_id='test-doc')
        self.assertEqual(captured_err.getvalue(), "")

    def test_empty_returns_empty(self):
        """Empty frontmatter returns empty list."""
        self.assertEqual(_get_depends_on({}), [])


if __name__ == '__main__':
    unittest.main()
