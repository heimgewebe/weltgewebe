"""Regression tests for the Semantic Search v1 architecture, goldset and benchmark."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from scripts.search.benchmark_relevance import (
    DEFAULT_RESULT,
    OllamaClient,
    check_result,
    contains_raw_vectors,
    current_substring_rank,
    hybrid_rank,
    lexical_reference_rank,
)
from scripts.search.validate_relevance_goldset import ValidationError, validate_goldset

ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = ROOT / "contracts/search/relevance-goldset.schema.json"
DATASET_PATH = ROOT / "contracts/search/examples/relevance-goldset.example.json"
ARCHITECTURE_PATH = ROOT / "architecture/semantic-search.md"


class SemanticSearchContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
        cls.case_by_id = {case["id"]: case for case in cls.dataset["cases"]}

    def test_checked_in_goldset_is_valid_and_synthetic(self) -> None:
        validate_goldset(self.dataset, self.schema)
        self.assertEqual(self.dataset["schema_version"], 2)
        self.assertEqual(self.dataset["privacy_class"], "synthetic")
        self.assertGreaterEqual(len(self.dataset["nodes"]), 20)
        self.assertGreaterEqual(len(self.dataset["cases"]), 20)
        self.assertTrue(all(node["contains_personal_data"] is False for node in self.dataset["nodes"]))
        self.assertTrue(all(case["contains_personal_data"] is False for case in self.dataset["cases"]))

    def test_duplicate_case_ids_are_rejected(self) -> None:
        dataset = copy.deepcopy(self.dataset)
        dataset["cases"].append(copy.deepcopy(dataset["cases"][0]))
        with self.assertRaisesRegex(ValidationError, "duplicate case id"):
            validate_goldset(dataset, self.schema)

    def test_duplicate_node_ids_are_rejected(self) -> None:
        dataset = copy.deepcopy(self.dataset)
        dataset["nodes"].append(copy.deepcopy(dataset["nodes"][0]))
        with self.assertRaisesRegex(ValidationError, "duplicate node id"):
            validate_goldset(dataset, self.schema)

    def test_unknown_node_reference_is_rejected(self) -> None:
        dataset = copy.deepcopy(self.dataset)
        dataset["cases"][0]["excluded_node_ids"] = ["syn-node-unknown-reference"]
        with self.assertRaisesRegex(ValidationError, "unknown nodes"):
            validate_goldset(dataset, self.schema)

    def test_relevant_node_outside_visible_context_is_rejected(self) -> None:
        dataset = copy.deepcopy(self.dataset)
        dataset["cases"][0]["relevant_node_ids"] = ["syn-node-private-garden"]
        with self.assertRaisesRegex(ValidationError, "not visible"):
            validate_goldset(dataset, self.schema)

    def test_excluded_node_inside_visible_context_is_rejected(self) -> None:
        dataset = copy.deepcopy(self.dataset)
        dataset["cases"][0]["excluded_node_ids"] = ["syn-node-community-garden"]
        with self.assertRaisesRegex(ValidationError, "excluded nodes are visible"):
            validate_goldset(dataset, self.schema)

    def test_hidden_or_deleted_node_cannot_be_visible(self) -> None:
        for node_id in ("syn-node-hidden-bike-cellar", "syn-node-deleted-repair-archive"):
            with self.subTest(node_id=node_id):
                dataset = copy.deepcopy(self.dataset)
                dataset["cases"][0]["visibility_context"]["visible_node_ids"].append(node_id)
                with self.assertRaisesRegex(ValidationError, "is not active"):
                    validate_goldset(dataset, self.schema)

    def test_visible_node_must_match_active_filters(self) -> None:
        dataset = copy.deepcopy(self.dataset)
        dataset["cases"][0]["visibility_context"]["active_filters"]["kinds"] = ["Beratung"]
        with self.assertRaisesRegex(ValidationError, "violates active filters"):
            validate_goldset(dataset, self.schema)

    def test_personal_data_flag_is_rejected(self) -> None:
        dataset = copy.deepcopy(self.dataset)
        dataset["nodes"][0]["contains_personal_data"] = True
        with self.assertRaisesRegex(ValidationError, "expected constant False"):
            validate_goldset(dataset, self.schema)

    def test_common_pii_patterns_are_rejected_even_with_false_flags(self) -> None:
        samples = (
            ("Kontakt person@example.invalid", "email-like"),
            ("Rückruf unter +49 30 1234567", "phone-like"),
            ("Interner Dienst 192.168.1.1", "IPv4-like"),
        )
        for query, message in samples:
            with self.subTest(query=query):
                dataset = copy.deepcopy(self.dataset)
                dataset["cases"][0]["query"] = query
                with self.assertRaisesRegex(ValidationError, message):
                    validate_goldset(dataset, self.schema)

    def test_current_substring_baseline_mirrors_existing_product_scope(self) -> None:
        exact = self.case_by_id["search-exact-title-community-garden"]
        semantic = self.case_by_id["search-semantic-food-rescue"]
        self.assertEqual(current_substring_rank(self.dataset, exact)[0], "syn-node-community-garden")
        self.assertEqual(current_substring_rank(self.dataset, semantic), [])

    def test_lexical_reference_handles_typo_and_never_leaks_hidden_node(self) -> None:
        case = self.case_by_id["search-typo-bike-workshop"]
        ranking = lexical_reference_rank(self.dataset, case)
        self.assertEqual(ranking[0], "syn-node-bike-workshop")
        self.assertNotIn("syn-node-hidden-bike-cellar", ranking)

    def test_hybrid_rank_cannot_displace_exact_title_with_vector_similarity(self) -> None:
        case = self.case_by_id["search-exact-title-community-garden"]
        active_ids = [node["id"] for node in self.dataset["nodes"] if node["status"] == "active"]
        vectors = {node_id: [0.0, 1.0] for node_id in active_ids}
        vectors["syn-node-community-garden"] = [1.0, 0.0]
        ranking = hybrid_rank(self.dataset, case, [0.0, 1.0], vectors)
        self.assertEqual(ranking[0], "syn-node-community-garden")

    def test_benchmark_client_rejects_external_or_authenticated_origins(self) -> None:
        for url in ("https://example.invalid", "http://user:secret@127.0.0.1:11434", "http://127.0.0.1:11434/api"):
            with self.subTest(url=url), self.assertRaisesRegex(ValueError, "loopback"):
                OllamaClient(url)
        OllamaClient("http://127.0.0.1:11434")

    def test_raw_vector_fields_are_forbidden_in_benchmark_evidence(self) -> None:
        self.assertTrue(contains_raw_vectors({"embedding": [0.1, 0.2]}))
        self.assertFalse(contains_raw_vectors({"model": {"dimensions": 1024}}))

    def test_checked_in_benchmark_evidence_is_current(self) -> None:
        check_result(DEFAULT_RESULT, DATASET_PATH, SCHEMA_PATH)

    def test_architecture_names_t002_decision_and_hard_boundaries(self) -> None:
        text = ARCHITECTURE_PATH.read_text(encoding="utf-8")
        required = (
            "PostgreSQL ist die einzige persistente Wahrheit",
            "Reine Vektorsuche ist verboten",
            "Sichtbarkeit und Löschstatus werden in derselben serverseitigen",
            "Garnrollen werden in v1 nicht eingebettet",
            "T002-Messung",
            "qwen3-embedding:4b",
            "keine Produktionsfreigabe",
            "separate SemantAH-Runtime",
        )
        for phrase in required:
            self.assertIn(phrase, text)

    def test_manifest_registers_canonical_architecture_document(self) -> None:
        manifest = (ROOT / "manifest/repo-index.yaml").read_text(encoding="utf-8")
        self.assertIn("- semantic-search.md", manifest)


if __name__ == "__main__":
    unittest.main()
