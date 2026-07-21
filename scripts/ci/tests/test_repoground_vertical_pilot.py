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

    def test_call_graph_blocker_requires_real_size_overrun(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        blocker = mutated["call_graph_blocker"]
        blocker["artifact_bytes"] = blocker["readonly_adapter_max_bytes"]
        blocker["over_limit_bytes"] = 0
        errors = self.validator.validate(mutated)
        self.assertTrue(any("above the safe adapter limit" in error for error in errors))

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


if __name__ == "__main__":
    unittest.main()
