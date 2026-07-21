from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
VALIDATOR_PATH = ROOT / "scripts/ci/validate_repoground_vertical_pilot.py"
EVIDENCE_PATH = ROOT / "scripts/ci/fixtures/repoground_vertical_pilot.v1.json"


def load_validator():
    spec = importlib.util.spec_from_file_location(
        "weltgewebe_repoground_vertical_pilot_validator", VALIDATOR_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {VALIDATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RepoGroundVerticalPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.validator = load_validator()
        cls.evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))

    def test_committed_evidence_is_internally_consistent(self) -> None:
        self.assertEqual(self.validator.validate(self.evidence), [])

    def test_missing_critical_path_breaks_quality_gate(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        case = mutated["cases"][0]
        case["missing_critical_paths"] = [case["expected_critical_paths"][0]]
        errors = self.validator.validate(mutated)
        self.assertTrue(any("critical-path coverage" in error for error in errors))

    def test_default_promotion_cannot_be_claimed_while_delivery_chain_is_blocked(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        mutated["promotion_recommendation"] = "promote_default"
        errors = self.validator.validate(mutated)
        self.assertIn("default promotion must remain withheld", errors)

    def test_t007_proof_requires_real_legacy_limit_overrun_and_bounded_access(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        access = mutated["call_graph_access"]
        access["artifact_bytes"] = access["legacy_readonly_limit_bytes"]
        access["over_limit_bytes"] = 0
        access["bounded_access_status"] = "blocked"
        errors = self.validator.validate(mutated)
        self.assertTrue(any("larger than the legacy read limit" in error for error in errors))
        self.assertIn("bounded call graph access must pass", errors)

    def test_reintroduced_artifact_too_large_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        case = mutated["cases"][0]
        case["capsule"]["artifact_too_large_present"] = True
        mutated["call_graph_access"]["artifact_too_large_case_ids"] = [case["id"]]
        errors = self.validator.validate(mutated)
        self.assertTrue(any("artifact_too_large must be absent" in error for error in errors))
        self.assertIn("post-T007 pilot must have no artifact_too_large cases", errors)

    def test_heuristic_related_test_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        case = mutated["cases"][1]
        case["capsule"]["heuristic_related_test_count"] = 1
        case["capsule"]["related_tests"] = [
            {"path": "tests/test_guess.py", "evidence_type": "heuristic"}
        ]
        errors = self.validator.validate(mutated)
        self.assertTrue(any("heuristic related tests must be zero" in error for error in errors))
        self.assertTrue(any("accepted evidence" in error for error in errors))

    def test_forged_reduction_cannot_pass_mechanical_gate(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        case = mutated["cases"][0]
        case["capsule"]["context_bytes"] = case["baseline"]["payload_bytes"]
        case["capsule"]["ratio"] = 1.0
        case["capsule"]["reduction_pct"] = 99.0
        errors = self.validator.validate(mutated)
        self.assertTrue(any("reduction_pct must match byte accounting" in error for error in errors))
        self.assertTrue(any("qualifying cases do not match recomputed measurements" in error for error in errors))

    def test_unavailable_baseline_or_capsule_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        mutated["cases"][0]["baseline"]["available"] = False
        mutated["cases"][1]["capsule"]["available"] = False
        errors = self.validator.validate(mutated)
        self.assertTrue(any("paired baseline must be available" in error for error in errors))
        self.assertTrue(any("capsule must be available" in error for error in errors))

    def test_delivery_chain_cannot_be_marked_complete_without_missing_evidence(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        mutated["delivery_chain_assessment"]["status"] = "pass"
        mutated["delivery_chain_assessment"]["missing"].pop("runtime_proof")
        mutated["acceptance"]["delivery_chain"] = "pass"
        mutated["overall_status"] = "verified"
        errors = self.validator.validate(mutated)
        self.assertTrue(any("delivery chain must remain blocked" in error for error in errors))
        self.assertTrue(any("contracts, runtime_proof and rollback_risks" in error for error in errors))
        self.assertTrue(any("narrowed post-T007 blocker" in error for error in errors))
        self.assertTrue(any("overall_status must remain blocked" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
