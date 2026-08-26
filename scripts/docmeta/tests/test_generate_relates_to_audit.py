import ast
import inspect
import textwrap
import unittest
from collections import deque
from unittest.mock import patch

from scripts.docmeta import generate_relates_to_audit
from scripts.docmeta.generate_relates_to_audit import (
    collect_relations_graph,
    compute_per_doc_type_counts,
    find_supersedes_gaps,
    find_relates_to_clusters,
    _check_supersession_pattern,
    collect_negative_examples,
)


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


class TestRelationDiscovery(unittest.TestCase):
    def test_walk_error_fails_closed(self):
        def failing_walk(*_args, **kwargs):
            kwargs["onerror"](OSError("discovery denied"))
            return []

        with patch.object(generate_relates_to_audit.os, "walk", side_effect=failing_walk):
            with self.assertRaises(OSError):
                collect_relations_graph()

    def test_markdown_read_error_fails_closed(self):
        walk = [("/repo/docs", [], ["broken.md"])]
        with (
            patch.object(generate_relates_to_audit.os, "walk", return_value=walk),
            patch("builtins.open", side_effect=OSError("read denied")),
        ):
            with self.assertRaises(OSError):
                collect_relations_graph()


class TestPerDocTypeCounts(unittest.TestCase):
    """Tests for per-document relation type counting."""

    def test_empty(self):
        counts = compute_per_doc_type_counts([])
        self.assertEqual(counts, {})

    def test_single_doc(self):
        edges = [
            ("a.md", "relates_to", "b.md"),
            ("a.md", "depends_on", "c.md"),
            ("a.md", "relates_to", "d.md"),
        ]
        counts = compute_per_doc_type_counts(edges)
        self.assertEqual(counts["a.md"]["relates_to"], 2)
        self.assertEqual(counts["a.md"]["depends_on"], 1)
        self.assertEqual(counts["a.md"]["total"], 3)

    def test_multiple_docs(self):
        edges = [
            ("a.md", "relates_to", "b.md"),
            ("b.md", "supersedes", "c.md"),
        ]
        counts = compute_per_doc_type_counts(edges)
        self.assertEqual(counts["a.md"]["total"], 1)
        self.assertEqual(counts["b.md"]["total"], 1)
        self.assertEqual(counts["b.md"]["supersedes"], 1)


class TestSupersedesGaps(unittest.TestCase):
    """Tests for supersedes gap detection."""

    def test_no_gaps_different_names(self):
        gaps = find_supersedes_gaps({"docs/foo.md", "docs/bar.md"})
        self.assertEqual(gaps, [])

    def test_v2_suffix_detected(self):
        gaps = find_supersedes_gaps({"docs/foo.md", "docs/foo-v2.md"})
        self.assertEqual(len(gaps), 1)
        self.assertIn("v2", gaps[0][2])

    def test_deprecated_suffix_detected(self):
        gaps = find_supersedes_gaps({"docs/api.md", "docs/api-deprecated.md"})
        self.assertEqual(len(gaps), 1)
        self.assertIn("deprecated", gaps[0][2])

    def test_different_directories_no_match(self):
        gaps = find_supersedes_gaps({"docs/a/foo.md", "docs/b/foo-v2.md"})
        self.assertEqual(gaps, [])

    def test_no_false_positive_unrelated(self):
        gaps = find_supersedes_gaps({"docs/vision.md", "docs/techstack.md"})
        self.assertEqual(gaps, [])


class TestSupersessionPattern(unittest.TestCase):
    """Tests for the supersession pattern heuristic."""

    def test_v2_match(self):
        result = _check_supersession_pattern("foo", "foo-v2")
        self.assertIsNotNone(result)

    def test_legacy_match(self):
        result = _check_supersession_pattern("api", "api-legacy")
        self.assertIsNotNone(result)

    def test_no_match(self):
        result = _check_supersession_pattern("vision", "techstack")
        self.assertIsNone(result)

    def test_reverse_order(self):
        result = _check_supersession_pattern("foo-new", "foo")
        self.assertIsNotNone(result)


class TestRelatesToClusters(unittest.TestCase):
    """Tests for relates_to cluster analysis."""

    def test_empty(self):
        clusters = find_relates_to_clusters([])
        self.assertEqual(clusters, [])

    def test_single_cluster(self):
        edges = [
            ("a.md", "relates_to", "b.md"),
            ("b.md", "relates_to", "c.md"),
        ]
        clusters = find_relates_to_clusters(edges)
        self.assertEqual(clusters, [["a.md", "b.md", "c.md"]])

    def test_cycle_and_duplicate_edges_keep_fifo_characteristics(self):
        edges = [
            ("a.md", "relates_to", "b.md"),
            ("a.md", "relates_to", "b.md"),
            ("a.md", "relates_to", "c.md"),
            ("c.md", "relates_to", "a.md"),
        ]
        QueueProbe.instances = []

        with patch.object(generate_relates_to_audit, "deque", QueueProbe):
            clusters = find_relates_to_clusters(edges)

        self.assertEqual(clusters, [["a.md", "b.md", "c.md"]])
        self.assertEqual(QueueProbe.instances[0].popped, ["a.md", "b.md", "c.md"])

    def test_chain_has_no_depth_cutoff(self):
        depth = 64
        edges = [
            (f"node-{index:03d}.md", "relates_to", f"node-{index + 1:03d}.md")
            for index in range(depth)
        ]

        clusters = find_relates_to_clusters(edges)

        self.assertEqual(len(clusters), 1)
        self.assertEqual(len(clusters[0]), depth + 1)
        self.assertEqual(clusters[0][0], "node-000.md")
        self.assertEqual(clusters[0][-1], f"node-{depth:03d}.md")

    def test_broad_level_queue_avoids_front_deletions(self):
        breadth = 1024
        edges = [
            ("00-root.md", "relates_to", f"node-{index:04d}.md")
            for index in reversed(range(breadth))
        ]
        QueueProbe.instances = []

        with patch.object(generate_relates_to_audit, "deque", QueueProbe):
            clusters = find_relates_to_clusters(edges)

        self.assertEqual(
            clusters,
            [["00-root.md", *(f"node-{index:04d}.md" for index in range(breadth))]],
        )
        self.assertEqual(QueueProbe.instances[0].max_size, breadth)
        self.assertEqual(
            QueueProbe.instances[0].popped[:4],
            ["00-root.md", "node-0000.md", "node-0001.md", "node-0002.md"],
        )

        tree = ast.parse(textwrap.dedent(inspect.getsource(find_relates_to_clusters)))
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

    def test_two_clusters(self):
        edges = [
            ("a.md", "relates_to", "b.md"),
            ("c.md", "relates_to", "d.md"),
        ]
        clusters = find_relates_to_clusters(edges)
        self.assertEqual(len(clusters), 2)
        self.assertEqual(len(clusters[0]), 2)
        self.assertEqual(len(clusters[1]), 2)

    def test_equal_sized_clusters_have_deterministic_order(self):
        edges = [
            ("z.md", "relates_to", "m.md"),
            ("b.md", "relates_to", "a.md"),
        ]

        clusters = find_relates_to_clusters(edges)

        self.assertEqual(clusters, [["a.md", "b.md"], ["m.md", "z.md"]])

    def test_depends_on_ignored(self):
        edges = [
            ("a.md", "depends_on", "b.md"),
            ("c.md", "relates_to", "d.md"),
        ]
        clusters = find_relates_to_clusters(edges)
        self.assertEqual(len(clusters), 1)
        self.assertNotIn("a.md", clusters[0])

    def test_sorted_by_size(self):
        edges = [
            ("a.md", "relates_to", "b.md"),
            ("c.md", "relates_to", "d.md"),
            ("c.md", "relates_to", "e.md"),
        ]
        clusters = find_relates_to_clusters(edges)
        self.assertTrue(len(clusters[0]) >= len(clusters[1]))


class TestCollectNegativeExamples(unittest.TestCase):
    """Tests for concrete example collection."""

    def test_empty(self):
        result = collect_negative_examples([], {})
        self.assertEqual(result, [])

    def test_collects_examples(self):
        edges = [
            ("a.md", "relates_to", "b.md"),
            ("a.md", "relates_to", "c.md"),
            ("a.md", "relates_to", "d.md"),
        ]
        doc_counts = {
            "a.md": {"relates_to": 3, "depends_on": 0, "supersedes": 0, "total": 3},
        }
        result = collect_negative_examples(edges, doc_counts, max_examples=3)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], "a.md")
        self.assertEqual(len(result[0][1]), 3)

    def test_respects_max_examples(self):
        edges = [
            ("a.md", "relates_to", "x.md"),
            ("a.md", "relates_to", "y.md"),
            ("b.md", "relates_to", "x.md"),
            ("b.md", "relates_to", "z.md"),
            ("c.md", "relates_to", "x.md"),
            ("c.md", "relates_to", "w.md"),
            ("d.md", "relates_to", "x.md"),
            ("d.md", "relates_to", "v.md"),
        ]
        doc_counts = {
            "a.md": {"relates_to": 2, "depends_on": 0, "supersedes": 0, "total": 2},
            "b.md": {"relates_to": 2, "depends_on": 0, "supersedes": 0, "total": 2},
            "c.md": {"relates_to": 2, "depends_on": 0, "supersedes": 0, "total": 2},
            "d.md": {"relates_to": 2, "depends_on": 0, "supersedes": 0, "total": 2},
        }
        result = collect_negative_examples(edges, doc_counts, max_examples=2)
        self.assertEqual(len(result), 2)

    def test_single_relation_excluded(self):
        edges = [("a.md", "relates_to", "b.md")]
        doc_counts = {
            "a.md": {"relates_to": 1, "depends_on": 0, "supersedes": 0, "total": 1},
        }
        result = collect_negative_examples(edges, doc_counts)
        self.assertEqual(result, [])

    def test_sorted_by_most_relates_to(self):
        edges = [
            ("a.md", "relates_to", "x.md"),
            ("a.md", "relates_to", "y.md"),
            ("b.md", "relates_to", "x.md"),
            ("b.md", "relates_to", "y.md"),
            ("b.md", "relates_to", "z.md"),
        ]
        doc_counts = {
            "a.md": {"relates_to": 2, "depends_on": 0, "supersedes": 0, "total": 2},
            "b.md": {"relates_to": 3, "depends_on": 0, "supersedes": 0, "total": 3},
        }
        result = collect_negative_examples(edges, doc_counts, max_examples=2)
        self.assertEqual(result[0][0], "b.md")


if __name__ == "__main__":
    unittest.main()
