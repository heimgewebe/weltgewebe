import ast
import io
import inspect
import json
import os
import shutil
import tempfile
import textwrap
import unittest
from collections import deque
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

from scripts.docmeta.review_impact import main, _get_depends_on


class QueueProbe(deque):
    """Record FIFO behavior and fail if the traversal uses deque.pop()."""

    instances: list["QueueProbe"] = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_size = len(self)
        self.popped = []
        self.__class__.instances.append(self)

    def append(self, item):
        super().append(item)
        self.max_size = max(self.max_size, len(self))

    def popleft(self):
        item = super().popleft()
        self.popped.append(item)
        return item

    def pop(self, *args, **kwargs):
        raise AssertionError("breadth-first queue must not delete from the front with pop")


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
    def test_small_graph_output_bytes_are_deterministic(
        self, mock_parse_repo_index, mock_parse_review_policy
    ):
        """A small fan-out keeps exact JSON and Markdown byte ordering."""
        mock_parse_review_policy.return_value = {
            "mode": "warn", "strict_manifest": False,
            "warn_days": 90, "fail_days": 180,
        }
        mock_parse_repo_index.return_value = {
            "zones": {
                "norm": {
                    "path": "docs/",
                    "canonical_docs": ["root.md", "z.md", "a.md"],
                }
            }
        }
        self._write_doc("docs/root.md", "---\nid: root\n---\n")
        self._write_doc("docs/z.md", "---\nid: z\ndepends_on:\n  - root\n---\n")
        self._write_doc("docs/a.md", "---\nid: a\ndepends_on:\n  - root\n---\n")

        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            with patch('scripts.docmeta.review_impact.REPO_ROOT', self.temp_dir):
                main()

        json_path = os.path.join(self.temp_dir, "artifacts", "docmeta", "impact.json")
        with open(json_path, 'r', encoding='utf-8') as f:
            json_bytes = f.read()
        self.assertEqual(
            json_bytes,
            "{\n"
            '  "missing_ids": [],\n'
            '  "cycles": [],\n'
            '  "impacts": {\n'
            '    "root": {\n'
            '      "file": "docs/root.md",\n'
            '      "transitive_impacts": [\n'
            '        "docs/a.md",\n'
            '        "docs/z.md"\n'
            "      ]\n"
            "    },\n"
            '    "z": {\n'
            '      "file": "docs/z.md",\n'
            '      "transitive_impacts": []\n'
            "    },\n"
            '    "a": {\n'
            '      "file": "docs/a.md",\n'
            '      "transitive_impacts": []\n'
            "    }\n"
            "  }\n"
            "}",
        )

        md_path = os.path.join(self.temp_dir, "artifacts", "docmeta", "impact.md")
        with open(md_path, 'r', encoding='utf-8') as f:
            markdown_bytes = f.read()
        self.assertEqual(
            markdown_bytes,
            "# Dependency Graph & Impact Report\n\n"
            "## Missing IDs\n\n"
            "No missing ids.\n\n"
            "## Cycles\n\nNo cycles detected.\n\n"
            "## Transitive Impact\n\n"
            "### a (`docs/a.md`)\n\n"
            "No dependents.\n\n"
            "### root (`docs/root.md`)\n\n"
            "- docs/a.md\n"
            "- docs/z.md\n\n"
            "### z (`docs/z.md`)\n\n"
            "No dependents.\n\n",
        )

    @patch('scripts.docmeta.review_impact.parse_review_policy')
    @patch('scripts.docmeta.review_impact.parse_repo_index')
    def test_cycle_and_duplicate_edges_keep_fifo_characteristics(
        self, mock_parse_repo_index, mock_parse_review_policy
    ):
        """Duplicate enqueues stay observable while visited nodes terminate cycles."""
        mock_parse_review_policy.return_value = {
            "mode": "warn", "strict_manifest": False,
            "warn_days": 90, "fail_days": 180,
        }
        mock_parse_repo_index.return_value = {
            "zones": {
                "norm": {
                    "path": "docs/",
                    "canonical_docs": ["a.md", "b.md"],
                }
            }
        }
        self._write_doc(
            "docs/a.md",
            "---\nid: doc-a\ndepends_on:\n  - doc-b\n  - doc-b\n---\n",
        )
        self._write_doc("docs/b.md", "---\nid: doc-b\ndepends_on:\n  - doc-a\n---\n")
        QueueProbe.instances = []

        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            with (
                patch('scripts.docmeta.review_impact.REPO_ROOT', self.temp_dir),
                patch('scripts.docmeta.review_impact.deque', QueueProbe),
            ):
                main()

        data = self._load_impact_json()
        self.assertEqual(data["cycles"], [["doc-a", "doc-b", "doc-a"]])
        self.assertEqual(
            data["impacts"]["doc-a"]["transitive_impacts"],
            ["docs/a.md", "docs/b.md"],
        )
        self.assertEqual(QueueProbe.instances[0].popped, ["doc-a", "doc-b", "doc-a", "doc-a"])

    @patch('scripts.docmeta.review_impact.parse_review_policy')
    @patch('scripts.docmeta.review_impact.parse_repo_index')
    def test_transitive_impact_has_no_depth_cutoff(
        self, mock_parse_repo_index, mock_parse_review_policy
    ):
        """The deepest node in a long chain remains transitively reachable."""
        depth = 40
        canonical_docs = [f"node-{index:02d}.md" for index in range(depth + 1)]
        mock_parse_review_policy.return_value = {
            "mode": "warn", "strict_manifest": False,
            "warn_days": 90, "fail_days": 180,
        }
        mock_parse_repo_index.return_value = {
            "zones": {"norm": {"path": "docs/", "canonical_docs": canonical_docs}}
        }
        self._write_doc("docs/node-00.md", "---\nid: node-00\n---\n")
        for index in range(1, depth + 1):
            self._write_doc(
                f"docs/node-{index:02d}.md",
                "---\n"
                f"id: node-{index:02d}\n"
                "depends_on:\n"
                f"  - node-{index - 1:02d}\n"
                "---\n",
            )

        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            with patch('scripts.docmeta.review_impact.REPO_ROOT', self.temp_dir):
                main()

        impacts = self._load_impact_json()["impacts"]["node-00"]["transitive_impacts"]
        self.assertEqual(len(impacts), depth)
        self.assertEqual(impacts[0], "docs/node-01.md")
        self.assertEqual(impacts[-1], f"docs/node-{depth:02d}.md")

    @patch('scripts.docmeta.review_impact.parse_review_policy')
    @patch('scripts.docmeta.review_impact.parse_repo_index')
    def test_broad_level_queue_avoids_front_deletions(
        self, mock_parse_repo_index, mock_parse_review_policy
    ):
        """A broad graph uses popleft and never a linear-time pop(0)."""
        breadth = 512
        child_docs = [f"child-{index:04d}.md" for index in reversed(range(breadth))]
        mock_parse_review_policy.return_value = {
            "mode": "warn", "strict_manifest": False,
            "warn_days": 90, "fail_days": 180,
        }
        mock_parse_repo_index.return_value = {
            "zones": {
                "norm": {
                    "path": "docs/",
                    "canonical_docs": ["root.md", *child_docs],
                }
            }
        }
        self._write_doc("docs/root.md", "---\nid: root\n---\n")
        for child_doc in child_docs:
            child_id = child_doc.removesuffix(".md")
            self._write_doc(
                f"docs/{child_doc}",
                f"---\nid: {child_id}\ndepends_on:\n  - root\n---\n",
            )
        QueueProbe.instances = []

        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            with (
                patch('scripts.docmeta.review_impact.REPO_ROOT', self.temp_dir),
                patch('scripts.docmeta.review_impact.deque', QueueProbe),
            ):
                main()

        root_queue = QueueProbe.instances[0]
        self.assertEqual(root_queue.max_size, breadth)
        self.assertEqual(root_queue.popped[0], "root")
        self.assertEqual(root_queue.popped[1:4], ["child-0511", "child-0510", "child-0509"])
        impacts = self._load_impact_json()["impacts"]["root"]["transitive_impacts"]
        self.assertEqual(impacts, sorted(f"docs/{child_doc}" for child_doc in child_docs))

        tree = ast.parse(textwrap.dedent(inspect.getsource(main)))
        front_deletions = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "pop"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == 0
        ]
        popleft_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "popleft"
        ]
        self.assertEqual(front_deletions, [])
        self.assertEqual(len(popleft_calls), 1)

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
    def test_missing_id_warn_mode_emits_stderr_and_exits_zero(
        self, mock_parse_repo_index, mock_parse_review_policy
    ):
        """Warn mode reports missing IDs on stderr without failing."""
        mock_parse_review_policy.return_value = {
            "mode": "warn", "strict_manifest": False,
            "warn_days": 90, "fail_days": 180,
        }
        mock_parse_repo_index.return_value = {
            "zones": {
                "norm": {
                    "path": "docs/",
                    "canonical_docs": ["no_id.md"],
                }
            }
        }
        self._write_doc("docs/no_id.md", "---\ntitle: No ID\n---\n")

        captured_out = io.StringIO()
        captured_err = io.StringIO()
        with redirect_stdout(captured_out), redirect_stderr(captured_err):
            with patch('scripts.docmeta.review_impact.REPO_ROOT', self.temp_dir):
                main()

        self.assertIn("warning", captured_err.getvalue().lower())
        self.assertIn("docs/no_id.md", captured_err.getvalue())
        self.assertNotIn("warning", captured_out.getvalue().lower())
        self.assertIn("completed successfully", captured_out.getvalue())

    @patch('scripts.docmeta.review_impact.parse_review_policy')
    @patch('scripts.docmeta.review_impact.parse_repo_index')
    def test_missing_id_warn_mode_no_frontmatter_emits_stderr_and_exits_zero(
        self, mock_parse_repo_index, mock_parse_review_policy
    ):
        """Warn mode reports canonical documents without frontmatter."""
        mock_parse_review_policy.return_value = {
            "mode": "warn", "strict_manifest": False,
            "warn_days": 90, "fail_days": 180,
        }
        mock_parse_repo_index.return_value = {
            "zones": {
                "norm": {
                    "path": "docs/",
                    "canonical_docs": ["no_frontmatter.md"],
                }
            }
        }
        self._write_doc("docs/no_frontmatter.md", "Body without frontmatter\n")

        captured_out = io.StringIO()
        captured_err = io.StringIO()
        with redirect_stdout(captured_out), redirect_stderr(captured_err):
            with patch('scripts.docmeta.review_impact.REPO_ROOT', self.temp_dir):
                main()

        self.assertIn("warning", captured_err.getvalue().lower())
        self.assertIn("docs/no_frontmatter.md", captured_err.getvalue())
        self.assertNotIn("warning", captured_out.getvalue().lower())
        self.assertIn("completed successfully", captured_out.getvalue())

        data = self._load_impact_json()
        self.assertIn("missing_ids", data)
        self.assertIn("docs/no_frontmatter.md", data["missing_ids"])

    @patch('scripts.docmeta.review_impact.parse_review_policy')
    @patch('scripts.docmeta.review_impact.parse_repo_index')
    def test_missing_id_warn_mode_empty_frontmatter_emits_stderr_and_exits_zero(
        self, mock_parse_repo_index, mock_parse_review_policy
    ):
        """Warn mode reports canonical documents with empty frontmatter."""
        mock_parse_review_policy.return_value = {
            "mode": "warn", "strict_manifest": False,
            "warn_days": 90, "fail_days": 180,
        }
        mock_parse_repo_index.return_value = {
            "zones": {
                "norm": {
                    "path": "docs/",
                    "canonical_docs": ["empty_frontmatter.md"],
                }
            }
        }
        self._write_doc("docs/empty_frontmatter.md", "---\n---\nBody\n")

        captured_out = io.StringIO()
        captured_err = io.StringIO()
        with redirect_stdout(captured_out), redirect_stderr(captured_err):
            with patch('scripts.docmeta.review_impact.REPO_ROOT', self.temp_dir):
                main()

        self.assertIn("warning", captured_err.getvalue().lower())
        self.assertIn("docs/empty_frontmatter.md", captured_err.getvalue())
        self.assertNotIn("warning", captured_out.getvalue().lower())

        data = self._load_impact_json()
        self.assertIn("missing_ids", data)
        self.assertIn("docs/empty_frontmatter.md", data["missing_ids"])

    @patch('scripts.docmeta.review_impact.parse_review_policy')
    @patch('scripts.docmeta.review_impact.parse_repo_index')
    def test_missing_id_empty_frontmatter_strict_mode_exits(
        self, mock_parse_repo_index, mock_parse_review_policy
    ):
        """Empty frontmatter remains blocking in strict mode."""
        mock_parse_review_policy.return_value = {
            "mode": "strict", "strict_manifest": False,
            "warn_days": 90, "fail_days": 180,
        }
        mock_parse_repo_index.return_value = {
            "zones": {
                "norm": {
                    "path": "docs/",
                    "canonical_docs": ["empty_frontmatter.md"],
                }
            }
        }
        self._write_doc("docs/empty_frontmatter.md", "---\n---\nBody\n")

        captured_out = io.StringIO()
        captured_err = io.StringIO()
        with self.assertRaises(SystemExit) as ctx:
            with redirect_stdout(captured_out), redirect_stderr(captured_err):
                with patch('scripts.docmeta.review_impact.REPO_ROOT', self.temp_dir):
                    main()

        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("error", captured_err.getvalue().lower())
        self.assertIn("missing", captured_err.getvalue().lower())
        self.assertIn("docs/empty_frontmatter.md", captured_err.getvalue())

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
    def test_missing_id_fail_closed_mode_exits(
        self, mock_parse_repo_index, mock_parse_review_policy
    ):
        """Documents missing IDs remain blocking in fail-closed mode."""
        mock_parse_review_policy.return_value = {
            "mode": "fail-closed", "strict_manifest": False,
            "warn_days": 90, "fail_days": 180,
        }
        mock_parse_repo_index.return_value = {
            "zones": {
                "norm": {
                    "path": "docs/",
                    "canonical_docs": ["no_id.md"],
                }
            }
        }
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

    def test_empty_direct_overrides_relations(self):
        """An explicit empty depends_on wins over a legacy relations entry.

        Keeps review_impact consistent with docmeta.extract_depends_on: a present
        (even empty) direct field is canonical and must not fall back to relations.
        Because the direct field is a valid list while a legacy relation still
        exists, the dual-source warning fires so the stale entry can be cleaned up.
        """
        fm = {
            'depends_on': [],
            'relations': [
                {'type': 'depends_on', 'target': 'doc-legacy'},
            ],
        }
        captured_err = io.StringIO()
        with redirect_stderr(captured_err):
            result = _get_depends_on(fm, doc_id='test-doc')
        self.assertEqual(result, [])
        self.assertIn("Warning", captured_err.getvalue())

    def test_malformed_direct_no_fallback_and_no_warning(self):
        """A malformed (non-list) direct depends_on returns [] and emits NO
        dual-source warning: surfacing the type error is the schema's job, not
        review_impact's. The legacy relations entry must not be used as fallback."""
        fm = {
            'depends_on': 'doc-a',
            'relations': [
                {'type': 'depends_on', 'target': 'doc-legacy'},
            ],
        }
        captured_err = io.StringIO()
        with redirect_stderr(captured_err):
            result = _get_depends_on(fm, doc_id='test-doc')
        self.assertEqual(result, [])
        self.assertEqual(captured_err.getvalue(), "")


if __name__ == '__main__':
    unittest.main()
