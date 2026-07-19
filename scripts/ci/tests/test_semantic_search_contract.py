"""Regression tests for the Semantic Search v1 architecture, goldset and benchmark."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.search.benchmark_relevance import (
    DEFAULT_RESULT,
    OllamaClient,
    _NoRedirectHandler,
    check_result,
    contains_raw_vectors,
    current_substring_rank,
    evaluate_model,
    hybrid_rank,
    lexical_reference_rank,
    validate_result_shape,
    verify_quality_evidence,
)
from scripts.search.validate_relevance_goldset import ValidationError, load_json_object, validate_goldset

ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = ROOT / "contracts/search/relevance-goldset.schema.json"
DATASET_PATH = ROOT / "contracts/search/examples/relevance-goldset.example.json"
ARCHITECTURE_PATH = ROOT / "architecture/semantic-search.md"


class SemanticSearchContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
        cls.result = json.loads(DEFAULT_RESULT.read_text(encoding="utf-8"))
        cls.case_by_id = {case["id"]: case for case in cls.dataset["cases"]}

    def test_json_loader_rejects_duplicate_keys_and_non_finite_numbers(self) -> None:
        samples = (
            ('{"value": 1, "value": 2}', "duplicate JSON property"),
            ('{"value": NaN}', "non-finite JSON number"),
            ('{"value": Infinity}', "non-finite JSON number"),
        )
        for payload, message in samples:
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "fixture.json"
                path.write_text(payload, encoding="utf-8")
                with self.assertRaisesRegex(ValidationError, message):
                    load_json_object(path)

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

    def test_goldset_requires_natural_cases_and_all_rank_classes(self) -> None:
        dataset = copy.deepcopy(self.dataset)
        for case in dataset["cases"]:
            case["natural_language"] = False
        with self.assertRaisesRegex(ValidationError, "natural-language"):
            validate_goldset(dataset, self.schema)

        dataset = copy.deepcopy(self.dataset)
        dataset["cases"] = [case for case in dataset["cases"] if case["expected_rank_class"] != "exact_tag"]
        with self.assertRaisesRegex(ValidationError, "missing required rank classes"):
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
        for url in (
            "https://example.invalid",
            "http://localhost:11434",
            "http://user:secret@127.0.0.1:11434",
            "http://127.0.0.1:11434/api",
        ):
            with self.subTest(url=url), self.assertRaisesRegex(ValueError, "loopback"):
                OllamaClient(url)
        client = OllamaClient("http://127.0.0.1:11434")
        self.assertTrue(any(isinstance(handler, _NoRedirectHandler) for handler in client.opener.handlers))

    def test_benchmark_client_rejects_non_finite_or_boolean_vectors(self) -> None:
        for value in (float("nan"), float("inf"), True):
            with self.subTest(value=value):
                client = OllamaClient("http://127.0.0.1:11434")
                client._request = lambda path, payload, value=value: {"embeddings": [[value]]}  # type: ignore[method-assign]
                with self.assertRaisesRegex(RuntimeError, "invalid embedding"):
                    client.embed("synthetic-model", ["text"])

    def test_raw_vector_fields_are_forbidden_in_benchmark_evidence(self) -> None:
        self.assertTrue(contains_raw_vectors({"embedding": [0.1, 0.2]}))
        self.assertTrue(contains_raw_vectors({"payload": [0.1] * 32}))
        self.assertFalse(contains_raw_vectors({"model": {"dimensions": 1024}}))

    def test_benchmark_result_rejects_unknown_fields_and_raw_numeric_payloads(self) -> None:
        result = copy.deepcopy(self.result)
        result["unexpected"] = "field"
        with self.assertRaisesRegex(ValidationError, "invalid shape"):
            validate_result_shape(result)

        result = copy.deepcopy(self.result)
        result["environment"]["payload"] = [0.1] * 32
        with self.assertRaisesRegex(ValidationError, "invalid shape"):
            validate_result_shape(result)

    def test_result_checker_binds_goldset_validator_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = copy.deepcopy(self.result)
            result["validator_source_sha256"] = "0" * 64
            path = Path(temporary) / "result.json"
            path.write_text(json.dumps(result), encoding="utf-8")
            with self.assertRaisesRegex(ValidationError, "validator source hash"):
                check_result(path, DATASET_PATH, SCHEMA_PATH)

    def test_result_checker_binds_model_size_order_and_measurement_counts(self) -> None:
        mutations = (
            (lambda result: result["models"][1]["model"].__setitem__("size_bytes", 1), "strictly increasing"),
            (lambda result: result["models"][0]["performance"].__setitem__("document_count", 18), "document count"),
            (lambda result: result["models"][0]["performance"].__setitem__("query_count", 23), "query count"),
        )
        for mutate, message in mutations:
            with self.subTest(message=message), tempfile.TemporaryDirectory() as temporary:
                result = copy.deepcopy(self.result)
                mutate(result)
                path = Path(temporary) / "result.json"
                path.write_text(json.dumps(result), encoding="utf-8")
                with self.assertRaisesRegex(ValidationError, message):
                    check_result(path, DATASET_PATH, SCHEMA_PATH)

    def test_model_quality_aggregates_are_recomputed_from_rankings(self) -> None:
        quality = copy.deepcopy(self.result["models"][0]["quality"])
        quality["top1_relevant_count"] += 1
        with self.assertRaisesRegex(ValidationError, "inconsistent"):
            verify_quality_evidence(self.dataset, quality)

    def test_model_quality_evidence_rejects_hidden_ranked_nodes(self) -> None:
        quality = copy.deepcopy(self.result["models"][0]["quality"])
        quality["cases"][0]["ranked_node_ids"][0] = "syn-node-hidden-bike-cellar"
        with self.assertRaisesRegex(ValidationError, "inconsistent"):
            verify_quality_evidence(self.dataset, quality)

    def test_model_identity_change_during_measurement_is_rejected(self) -> None:
        class ChangingClient:
            def __init__(self) -> None:
                self.calls = 0

            def identity(self, model: str) -> dict[str, object]:
                self.calls += 1
                return {
                    "name": model,
                    "digest": "sha256:" + ("a" if self.calls == 1 else "b") * 64,
                    "size_bytes": 1,
                    "family": "test",
                    "parameter_size": "test",
                    "quantization_level": "test",
                }

            def embed(self, model: str, texts: list[str]) -> tuple[list[list[float]], float]:
                return [[1.0, 0.0] for _ in texts], 0.0

        with self.assertRaisesRegex(RuntimeError, "identity changed"):
            evaluate_model(self.dataset, "synthetic-model", ChangingClient())

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
