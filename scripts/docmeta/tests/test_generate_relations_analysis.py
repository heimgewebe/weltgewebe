import unittest
from collections import defaultdict

from scripts.docmeta.generate_relations_analysis import (
    find_cycles,
    compute_degree_stats,
    find_isolated_docs,
    find_hubs,
    compute_type_distribution,
    generate_warnings,
    HUB_OUTBOUND_THRESHOLD,
    HUB_INBOUND_THRESHOLD,
)


class TestFindCycles(unittest.TestCase):
    """Tests for depends_on cycle detection."""

    def test_no_cycles_empty(self):
        cycles = find_cycles([])
        self.assertEqual(cycles, [])

    def test_no_cycles_linear(self):
        edges = [
            ("a.md", "depends_on", "b.md"),
            ("b.md", "depends_on", "c.md"),
        ]
        cycles = find_cycles(edges)
        self.assertEqual(cycles, [])

    def test_simple_cycle(self):
        edges = [
            ("a.md", "depends_on", "b.md"),
            ("b.md", "depends_on", "a.md"),
        ]
        cycles = find_cycles(edges)
        self.assertTrue(len(cycles) > 0)
        # Cycle should contain both nodes
        cycle_nodes = set()
        for cycle in cycles:
            cycle_nodes.update(cycle)
        self.assertIn("a.md", cycle_nodes)
        self.assertIn("b.md", cycle_nodes)

    def test_three_node_cycle(self):
        edges = [
            ("a.md", "depends_on", "b.md"),
            ("b.md", "depends_on", "c.md"),
            ("c.md", "depends_on", "a.md"),
        ]
        cycles = find_cycles(edges)
        self.assertTrue(len(cycles) > 0)

    def test_relates_to_ignored(self):
        # relates_to edges should NOT trigger cycle detection
        edges = [
            ("a.md", "relates_to", "b.md"),
            ("b.md", "relates_to", "a.md"),
        ]
        cycles = find_cycles(edges)
        self.assertEqual(cycles, [])

    def test_supersedes_ignored(self):
        edges = [
            ("a.md", "supersedes", "b.md"),
            ("b.md", "supersedes", "a.md"),
        ]
        cycles = find_cycles(edges)
        self.assertEqual(cycles, [])


class TestDegreeStats(unittest.TestCase):
    """Tests for degree computation."""

    def test_empty(self):
        stats = compute_degree_stats([], set())
        self.assertEqual(stats, {})

    def test_basic_counts(self):
        all_docs = {"a.md", "b.md", "c.md"}
        edges = [
            ("a.md", "relates_to", "b.md"),
            ("a.md", "depends_on", "c.md"),
            ("b.md", "relates_to", "c.md"),
        ]
        stats = compute_degree_stats(edges, all_docs)
        self.assertEqual(stats["a.md"]["outbound"], 2)
        self.assertEqual(stats["a.md"]["inbound"], 0)
        self.assertEqual(stats["b.md"]["outbound"], 1)
        self.assertEqual(stats["b.md"]["inbound"], 1)
        self.assertEqual(stats["c.md"]["outbound"], 0)
        self.assertEqual(stats["c.md"]["inbound"], 2)


class TestFindIsolated(unittest.TestCase):
    """Tests for isolated document detection."""

    def test_no_isolated(self):
        stats = {
            "docs/a.md": {"outbound": 1, "inbound": 0},
            "docs/b.md": {"outbound": 0, "inbound": 1},
        }
        isolated = find_isolated_docs(stats)
        self.assertEqual(isolated, [])

    def test_isolated_found(self):
        stats = {
            "docs/a.md": {"outbound": 1, "inbound": 0},
            "docs/lonely.md": {"outbound": 0, "inbound": 0},
        }
        isolated = find_isolated_docs(stats)
        self.assertEqual(isolated, ["docs/lonely.md"])

    def test_index_excluded(self):
        stats = {
            "docs/index.md": {"outbound": 0, "inbound": 0},
            "docs/foo/README.md": {"outbound": 0, "inbound": 0},
        }
        isolated = find_isolated_docs(stats)
        self.assertEqual(isolated, [])


class TestFindHubs(unittest.TestCase):
    """Tests for hub detection."""

    def test_no_hubs(self):
        stats = {
            "docs/a.md": {
                "outbound": 1, "inbound": 1,
                "outbound_by_type": defaultdict(int),
                "inbound_by_type": defaultdict(int),
            },
        }
        outbound, inbound = find_hubs(stats)
        self.assertEqual(outbound, [])
        self.assertEqual(inbound, [])

    def test_outbound_hub(self):
        stats = {
            "docs/hub.md": {
                "outbound": HUB_OUTBOUND_THRESHOLD,
                "inbound": 0,
                "outbound_by_type": defaultdict(int),
                "inbound_by_type": defaultdict(int),
            },
        }
        outbound, inbound = find_hubs(stats)
        self.assertEqual(len(outbound), 1)
        self.assertEqual(outbound[0][0], "docs/hub.md")

    def test_inbound_hub(self):
        stats = {
            "docs/central.md": {
                "outbound": 0,
                "inbound": HUB_INBOUND_THRESHOLD,
                "outbound_by_type": defaultdict(int),
                "inbound_by_type": defaultdict(int),
            },
        }
        outbound, inbound = find_hubs(stats)
        self.assertEqual(len(inbound), 1)
        self.assertEqual(inbound[0][0], "docs/central.md")


class TestTypeDistribution(unittest.TestCase):
    """Tests for type distribution counting."""

    def test_empty(self):
        dist = compute_type_distribution([])
        self.assertEqual(dist, {})

    def test_counts(self):
        edges = [
            ("a.md", "relates_to", "b.md"),
            ("a.md", "relates_to", "c.md"),
            ("b.md", "depends_on", "c.md"),
            ("c.md", "supersedes", "d.md"),
        ]
        dist = compute_type_distribution(edges)
        self.assertEqual(dist["relates_to"], 2)
        self.assertEqual(dist["depends_on"], 1)
        self.assertEqual(dist["supersedes"], 1)


class TestGenerateWarnings(unittest.TestCase):
    """Tests for warning generation."""

    def test_no_warnings(self):
        edges = [("a.md", "relates_to", "b.md")]
        stats = {
            "a.md": {
                "outbound": 1, "inbound": 0,
                "outbound_by_type": defaultdict(int),
                "inbound_by_type": defaultdict(int),
            },
            "b.md": {
                "outbound": 0, "inbound": 1,
                "outbound_by_type": defaultdict(int),
                "inbound_by_type": defaultdict(int),
            },
        }
        warnings = generate_warnings(edges, stats, [])
        self.assertEqual(warnings, [])

    def test_cycle_warning(self):
        cycles = [["a.md", "b.md", "a.md"]]
        warnings = generate_warnings([], {}, cycles)
        self.assertTrue(any("cycle" in w for w in warnings))

    def test_hub_warning(self):
        stats = {
            "docs/hub.md": {
                "outbound": HUB_OUTBOUND_THRESHOLD + 1,
                "inbound": 0,
                "outbound_by_type": defaultdict(int),
                "inbound_by_type": defaultdict(int),
            },
        }
        warnings = generate_warnings([], stats, [])
        self.assertTrue(any("outbound" in w.lower() or "over-linking" in w for w in warnings))


if __name__ == "__main__":
    unittest.main()
