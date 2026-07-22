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

    def test_forged_reduction_cannot_pass_mechanical_gate(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        case = mutated["cases"][0]
        case["capsule"]["context_bytes"] = case["baseline"]["payload_bytes"]
        case["capsule"]["ratio"] = 1.0
        case["capsule"]["reduction_pct"] = 99.0
        errors = self.validator.validate(mutated)
        self.assertTrue(
            any("reduction_pct must match byte accounting" in error for error in errors)
        )
        self.assertTrue(
            any(
                "qualifying cases do not match recomputed measurements" in error
                for error in errors
            )
        )

    def test_unavailable_or_stale_baseline_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        mutated["cases"][0]["baseline"]["available"] = False
        mutated["cases"][1]["baseline"]["freshness_status"] = "stale"
        errors = self.validator.validate(mutated)
        self.assertTrue(any("paired baseline must be available" in error for error in errors))
        self.assertTrue(any("paired baseline must be fresh" in error for error in errors))

    def test_false_call_graph_use_without_consumed_evidence_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        case = next(
            case for case in mutated["cases"] if case["profile"] == "database_auth"
        )
        case["capsule"]["retrieval_lanes"]["skipped"].remove("call_graph")
        case["capsule"]["retrieval_lanes"]["used"].append("call_graph")
        errors = self.validator.validate(mutated)
        self.assertTrue(
            any(
                "call_graph must be skipped without coherent consumed evidence" in error
                for error in errors
            )
        )

    def test_consumed_call_graph_evidence_must_claim_used_lane(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        case = next(
            case
            for case in mutated["cases"]
            if case["profile"] == "deployment_kubernetes"
        )
        case["capsule"]["retrieval_lanes"]["used"].remove("call_graph")
        case["capsule"]["retrieval_lanes"]["skipped"].append("call_graph")
        errors = self.validator.validate(mutated)
        self.assertTrue(
            any(
                "consumed call-graph evidence must be explicitly claimed in used retrieval lanes" in error
                for error in errors
            )
        )

    def test_impact_context_blocked_cannot_pass_truth_gate(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        case = mutated["cases"][0]
        case["capsule"]["stop_criteria"]["triggered"].append("impact_context_blocked")
        errors = self.validator.validate(mutated)
        self.assertTrue(any("impact_context_blocked must be absent" in error for error in errors))

    def test_dirty_overlay_must_not_enter_revision_diff(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        mutated["cases"][0]["capsule"]["dirty_overlay"][
            "included_in_revision_diff"
        ] = True
        errors = self.validator.validate(mutated)
        self.assertTrue(any("dirty overlay must be excluded" in error for error in errors))

    def test_delivery_chain_failure_blocks_default_promotion(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        mutated["delivery_chain"]["status"] = "blocked"
        errors = self.validator.validate(mutated)
        self.assertTrue(any("delivery chain must pass bounded evidence" in error for error in errors))
        self.assertIn(
            "default promotion cannot be claimed without all promotion gates",
            errors,
        )

    def test_controlled_live_case_is_required_and_bound_to_source_bundle(self) -> None:
        missing = copy.deepcopy(self.evidence)
        missing["cases"] = [
            case for case in missing["cases"] if case["profile"] != "controlled_live"
        ]
        errors = self.validator.validate(missing)
        self.assertIn(
            "exactly three gold cases plus one controlled live case are required",
            errors,
        )

        stale = copy.deepcopy(self.evidence)
        live = next(
            case for case in stale["cases"] if case["profile"] == "controlled_live"
        )
        live["target_commit"] = "0" * 40
        live["target_revision"] = "0" * 40
        errors = self.validator.validate(stale)
        self.assertIn(
            "controlled_live target commit must equal source bundle git_commit",
            errors,
        )
        self.assertIn(
            "default promotion cannot be claimed without all promotion gates",
            errors,
        )

    def test_delivery_evidence_omissions_block_default_promotion(self) -> None:
        mutations = {
            "contract": (
                lambda data: data["delivery_chain"].pop("contract_evidence"),
                "delivery chain must bind explicit contract evidence",
            ),
            "ci": (
                lambda data: data["delivery_chain"].pop("ci_evidence"),
                "delivery chain must bind explicit CI evidence",
            ),
            "deployment": (
                lambda data: data["delivery_chain"].pop("deployment_evidence"),
                "delivery chain must bind explicit deployment evidence",
            ),
            "runtime": (
                lambda data: data["delivery_chain"].pop("runtime_proof"),
                "delivery chain must bind an executed runtime proof",
            ),
            "recovery": (
                lambda data: data["delivery_chain"].pop("recovery_evidence"),
                "delivery chain must bind explicit recovery evidence",
            ),
            "rollback_risks": (
                lambda data: data["delivery_chain"].update({"rollback_risks": []}),
                "delivery chain must enumerate rollback/recovery risks",
            ),
        }
        for name, (mutate, expected_error) in mutations.items():
            with self.subTest(name=name):
                mutated = copy.deepcopy(self.evidence)
                mutate(mutated)
                errors = self.validator.validate(mutated)
                self.assertIn(expected_error, errors)
                self.assertIn(
                    "default promotion cannot be claimed without all promotion gates",
                    errors,
                )

    def test_runtime_proof_must_bind_exact_successful_live_identity(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        runtime = mutated["delivery_chain"]["runtime_proof"]
        runtime["head_sha"] = "0" * 40
        runtime["public_identity_step_conclusion"] = "failure"
        runtime["production_receipt_uploaded"] = False
        errors = self.validator.validate(mutated)
        self.assertIn("runtime proof must bind the exact deployment case target", errors)
        self.assertIn(
            "runtime proof must include successful public identity verification", errors
        )
        self.assertIn("runtime proof must include an uploaded production receipt", errors)
        self.assertIn(
            "default promotion cannot be claimed without all promotion gates", errors
        )

    def test_source_bundle_must_be_fresh_and_healthy(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        mutated["source_bundle"]["freshness"] = "stale"
        mutated["source_bundle"]["post_emit_health"] = "fail"
        errors = self.validator.validate(mutated)
        self.assertIn("source bundle must be fresh_exact", errors)
        self.assertIn("source_bundle.post_emit_health must be pass", errors)

    def test_source_bundle_generator_must_match_measured_repoground_runtime(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        mutated["source_bundle"]["generator_runtime_commit"] = "0" * 40
        errors = self.validator.validate(mutated)
        self.assertIn(
            "source_bundle.generator_runtime_commit must match repoground_runtime_commit",
            errors,
        )

    def test_consumed_call_graph_needs_explicit_relation_provenance(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        case = next(
            case
            for case in mutated["cases"]
            if case["profile"] == "deployment_kubernetes"
        )
        case["capsule"]["representative_causal_relations"] = []
        errors = self.validator.validate(mutated)
        self.assertTrue(
            any(
                "consumed call graph needs explicit coherent relation provenance" in error
                for error in errors
            )
        )

    def test_target_symbol_count_must_match_explicit_evidence(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        case = next(
            case
            for case in mutated["cases"]
            if case["profile"] == "deployment_kubernetes"
        )
        case["capsule"]["target_symbols"] = case["capsule"]["target_symbols"][:-1]
        errors = self.validator.validate(mutated)
        self.assertTrue(
            any("target symbol count must match explicit evidence" in error for error in errors)
        )

    def test_empty_or_unresolved_baseline_evidence_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        baseline = mutated["cases"][1]["baseline"]
        baseline["resolved_evidence_status"] = "degraded"
        baseline["snippet_count"] = 0
        errors = self.validator.validate(mutated)
        self.assertTrue(
            any("paired baseline must contain resolved evidence" in error for error in errors)
        )
        self.assertTrue(any("baseline snippet_count must be positive" in error for error in errors))

    def test_measurement_worktree_must_be_evidence_only_dirty(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        mutated["measurement_worktree"]["dirty_scope"] = "mixed"
        mutated["measurement_worktree"]["dirty_paths"].append("apps/api/src/lib.rs")
        errors = self.validator.validate(mutated)
        self.assertIn("measurement worktree dirty scope must be evidence_only", errors)
        self.assertIn(
            "measurement worktree dirty paths must equal the four evidence files",
            errors,
        )

    def test_every_gold_case_requires_related_test_evidence(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        case = mutated["cases"][0]
        case["capsule"]["related_tests"] = []
        case["capsule"]["related_tests_included"] = 0
        errors = self.validator.validate(mutated)
        self.assertTrue(
            any("every gold case must include at least one related test" in error for error in errors)
        )


if __name__ == "__main__":
    unittest.main()
