import unittest

from scripts.docmeta.generate_relates_to_audit import (
    compute_per_doc_type_counts,
    find_dominant_relates_to,
    find_direction_candidates,
    find_supersedes_gaps,
    find_relates_to_clusters,
    _check_supersession_pattern,
    generate_system_dominance_warning,
    find_extreme_dominance_docs,
    collect_negative_examples,
    DOMINANCE_RATIO,
    MIN_RELATIONS_FOR_DOMINANCE,
    MIN_RELATIONS_FOR_DIRECTION,
    EXTREME_DOMINANCE_RATIO,
    SYSTEM_DOMINANCE_THRESHOLD,
)


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


class TestDominantRelatesTo(unittest.TestCase):
    """Tests for relates_to dominance detection (Phase 1)."""

    def test_empty(self):
        self.assertEqual(find_dominant_relates_to({}), [])

    def test_below_threshold(self):
        doc_counts = {
            "a.md": {"relates_to": 3, "depends_on": 0, "supersedes": 0, "total": 3},
        }
        result = find_dominant_relates_to(doc_counts)
        self.assertEqual(result, [])

    def test_dominant_detected(self):
        doc_counts = {
            "a.md": {"relates_to": 5, "depends_on": 0, "supersedes": 0, "total": 5},
        }
        result = find_dominant_relates_to(doc_counts)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], "a.md")
        self.assertEqual(result[0][1], 5)

    def test_mixed_not_dominant(self):
        doc_counts = {
            "a.md": {"relates_to": 3, "depends_on": 2, "supersedes": 1, "total": 6},
        }
        result = find_dominant_relates_to(doc_counts)
        self.assertEqual(result, [])

    def test_exactly_at_boundary(self):
        # 80% exactly should NOT trigger (> not >=)
        doc_counts = {
            "a.md": {"relates_to": 4, "depends_on": 1, "supersedes": 0, "total": 5},
        }
        result = find_dominant_relates_to(doc_counts)
        self.assertEqual(result, [])

    def test_sorted_by_count(self):
        doc_counts = {
            "a.md": {"relates_to": 6, "depends_on": 0, "supersedes": 0, "total": 6},
            "b.md": {"relates_to": 10, "depends_on": 0, "supersedes": 0, "total": 10},
        }
        result = find_dominant_relates_to(doc_counts)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0][0], "b.md")
        self.assertEqual(result[1][0], "a.md")


class TestDirectionCandidates(unittest.TestCase):
    """Tests for missing direction detection (Phase 2)."""

    def test_empty(self):
        self.assertEqual(find_direction_candidates({}), [])

    def test_only_relates_to_detected(self):
        doc_counts = {
            "a.md": {"relates_to": 5, "depends_on": 0, "supersedes": 0, "total": 5},
        }
        result = find_direction_candidates(doc_counts)
        self.assertEqual(len(result), 1)

    def test_mixed_types_excluded(self):
        doc_counts = {
            "a.md": {"relates_to": 4, "depends_on": 1, "supersedes": 0, "total": 5},
        }
        result = find_direction_candidates(doc_counts)
        self.assertEqual(result, [])

    def test_below_threshold_excluded(self):
        doc_counts = {
            "a.md": {"relates_to": 4, "depends_on": 0, "supersedes": 0, "total": 4},
        }
        result = find_direction_candidates(doc_counts)
        self.assertEqual(result, [])


class TestSupersedesGaps(unittest.TestCase):
    """Tests for supersedes gap detection (Phase 3)."""

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
    """Tests for relates_to cluster analysis (Phase 4)."""

    def test_empty(self):
        clusters = find_relates_to_clusters([])
        self.assertEqual(clusters, [])

    def test_single_cluster(self):
        edges = [
            ("a.md", "relates_to", "b.md"),
            ("b.md", "relates_to", "c.md"),
        ]
        clusters = find_relates_to_clusters(edges)
        self.assertEqual(len(clusters), 1)
        self.assertEqual(len(clusters[0]), 3)

    def test_two_clusters(self):
        edges = [
            ("a.md", "relates_to", "b.md"),
            ("c.md", "relates_to", "d.md"),
        ]
        clusters = find_relates_to_clusters(edges)
        self.assertEqual(len(clusters), 2)
        self.assertEqual(len(clusters[0]), 2)
        self.assertEqual(len(clusters[1]), 2)

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


class TestSystemDominanceWarning(unittest.TestCase):
    """Tests for system-level dominance warning (Phase 2 intervention)."""

    def test_no_warning_when_empty(self):
        result = generate_system_dominance_warning({}, 0)
        self.assertIsNone(result)

    def test_no_warning_below_threshold(self):
        type_dist = {"relates_to": 90, "depends_on": 10}
        result = generate_system_dominance_warning(type_dist, 100)
        self.assertIsNone(result)

    def test_warning_above_threshold(self):
        type_dist = {"relates_to": 97, "depends_on": 3}
        result = generate_system_dominance_warning(type_dist, 100)
        self.assertIsNotNone(result)
        self.assertIn("dominiert", result)
        self.assertIn("97%", result)

    def test_exactly_at_threshold_no_warning(self):
        type_dist = {"relates_to": 95, "depends_on": 5}
        result = generate_system_dominance_warning(type_dist, 100)
        self.assertIsNone(result)

    def test_all_relates_to(self):
        type_dist = {"relates_to": 100}
        result = generate_system_dominance_warning(type_dist, 100)
        self.assertIsNotNone(result)


class TestExtremeDominanceDocs(unittest.TestCase):
    """Tests for extreme dominance detection (Phase 1 intervention)."""

    def test_empty(self):
        self.assertEqual(find_extreme_dominance_docs({}), [])

    def test_below_count_threshold(self):
        doc_counts = {
            "a.md": {"relates_to": 4, "depends_on": 0, "supersedes": 0, "total": 4},
        }
        result = find_extreme_dominance_docs(doc_counts)
        self.assertEqual(result, [])

    def test_extreme_detected(self):
        doc_counts = {
            "a.md": {"relates_to": 9, "depends_on": 1, "supersedes": 0, "total": 10},
        }
        result = find_extreme_dominance_docs(doc_counts)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], "a.md")

    def test_exactly_at_90_percent(self):
        # ≥90% should trigger (>= not >)
        doc_counts = {
            "a.md": {"relates_to": 9, "depends_on": 1, "supersedes": 0, "total": 10},
        }
        result = find_extreme_dominance_docs(doc_counts)
        self.assertEqual(len(result), 1)

    def test_100_percent_detected(self):
        doc_counts = {
            "a.md": {"relates_to": 5, "depends_on": 0, "supersedes": 0, "total": 5},
        }
        result = find_extreme_dominance_docs(doc_counts)
        self.assertEqual(len(result), 1)

    def test_below_90_excluded(self):
        doc_counts = {
            "a.md": {"relates_to": 4, "depends_on": 1, "supersedes": 0, "total": 5},
        }
        result = find_extreme_dominance_docs(doc_counts)
        self.assertEqual(result, [])

    def test_sorted_by_count(self):
        doc_counts = {
            "a.md": {"relates_to": 5, "depends_on": 0, "supersedes": 0, "total": 5},
            "b.md": {"relates_to": 10, "depends_on": 0, "supersedes": 0, "total": 10},
        }
        result = find_extreme_dominance_docs(doc_counts)
        self.assertEqual(result[0][0], "b.md")


class TestCollectNegativeExamples(unittest.TestCase):
    """Tests for negative example collection (Phase 3 intervention)."""

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
