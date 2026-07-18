"""Regression tests for the Semantic Search v1 architecture and goldset contract."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

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

    def test_checked_in_goldset_is_valid_and_synthetic(self) -> None:
        validate_goldset(self.dataset, self.schema)
        self.assertEqual(self.dataset["privacy_class"], "synthetic")
        self.assertTrue(all(case["contains_personal_data"] is False for case in self.dataset["cases"]))

    def test_duplicate_case_ids_are_rejected(self) -> None:
        dataset = copy.deepcopy(self.dataset)
        dataset["cases"].append(copy.deepcopy(dataset["cases"][0]))
        with self.assertRaisesRegex(ValidationError, "duplicate case id"):
            validate_goldset(dataset, self.schema)

    def test_relevant_node_outside_visible_context_is_rejected(self) -> None:
        dataset = copy.deepcopy(self.dataset)
        dataset["cases"][0]["relevant_node_ids"] = ["syn-node-not-visible"]
        with self.assertRaisesRegex(ValidationError, "not visible"):
            validate_goldset(dataset, self.schema)

    def test_excluded_node_inside_visible_context_is_rejected(self) -> None:
        dataset = copy.deepcopy(self.dataset)
        dataset["cases"][0]["excluded_node_ids"] = ["syn-node-community-garden"]
        with self.assertRaisesRegex(ValidationError, "excluded nodes are visible"):
            validate_goldset(dataset, self.schema)

    def test_personal_data_flag_is_rejected(self) -> None:
        dataset = copy.deepcopy(self.dataset)
        dataset["cases"][0]["contains_personal_data"] = True
        with self.assertRaisesRegex(ValidationError, "expected constant False"):
            validate_goldset(dataset, self.schema)

    def test_email_like_content_is_rejected_even_with_false_flag(self) -> None:
        dataset = copy.deepcopy(self.dataset)
        dataset["cases"][0]["query"] = "Kontakt person@example.invalid"
        with self.assertRaisesRegex(ValidationError, "email-like"):
            validate_goldset(dataset, self.schema)

    def test_architecture_names_hard_boundaries_and_current_reality(self) -> None:
        text = ARCHITECTURE_PATH.read_text(encoding="utf-8")
        required = (
            "PostgreSQL ist die einzige persistente Wahrheit",
            "Reine Vektorsuche ist verboten",
            "Sichtbarkeit und Löschstatus werden in derselben serverseitigen",
            "Garnrollen werden in v1 nicht eingebettet",
            "Eine serverseitige Search-API",
            "JSONL weiterhin als Code-Default",
            "T001 ist ein Architektur- und Testgrundlagen-Schnitt",
            "separate SemantAH-Runtime",
        )
        for phrase in required:
            self.assertIn(phrase, text)

    def test_manifest_registers_canonical_architecture_document(self) -> None:
        manifest = (ROOT / "manifest/repo-index.yaml").read_text(encoding="utf-8")
        self.assertIn("- semantic-search.md", manifest)


if __name__ == "__main__":
    unittest.main()
