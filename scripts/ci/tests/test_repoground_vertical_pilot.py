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

    def test_forged_reductions_cannot_pass_computed_mechanical_gate(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        for case in mutated["cases"][:2]:
            case["capsule"]["context_bytes"] = case["baseline"]["payload_bytes"]
            case["capsule"]["ratio"] = 1.0
            case["capsule"]["reduction_pct"] = 99.0
        errors = self.validator.validate(mutated)
        self.assertTrue(
            any("reduction_pct must match byte accounting" in error for error in errors)
        )
        self.assertIn(
            "at least two gold cases must reduce context by at least 20 percent", errors
        )
        self.assertIn(
            "default promotion cannot be claimed without all promotion gates", errors
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
        self.assertIn(
            "default promotion cannot be claimed without all promotion gates", errors
        )

    def test_dirty_overlay_must_not_enter_revision_diff(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        mutated["cases"][0]["capsule"]["dirty_overlay"][
            "included_in_revision_diff"
        ] = True
        errors = self.validator.validate(mutated)
        self.assertTrue(any("dirty overlay must be excluded" in error for error in errors))
        self.assertIn(
            "default promotion cannot be claimed without all promotion gates", errors
        )


    def test_empty_required_direct_paths_block_default_promotion(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        mutated["pilot_delivery_chain_evidence"]["required_direct_paths"] = []
        errors = self.validator.validate(mutated)
        self.assertIn(
            "delivery chain required paths must be a non-empty unique subset of direct changes",
            errors,
        )
        self.assertIn(
            "default promotion cannot be claimed without all promotion gates",
            errors,
        )

    def test_delivery_required_direct_paths_are_exact_and_unique(self) -> None:
        original = self.evidence["pilot_delivery_chain_evidence"]["required_direct_paths"]
        deployment = next(
            case for case in self.evidence["cases"] if case["profile"] == "deployment_kubernetes"
        )
        extra_direct = next(
            path for path in deployment["direct_change_paths"] if path not in original
        )
        mutations = {
            "duplicate": original + [original[0]],
            "missing": original[:-1],
            "extra": original + [extra_direct],
        }
        for name, required_paths in mutations.items():
            with self.subTest(name=name):
                mutated = copy.deepcopy(self.evidence)
                mutated["pilot_delivery_chain_evidence"][
                    "required_direct_paths"
                ] = required_paths
                errors = self.validator.validate(mutated)
                if name == "duplicate":
                    self.assertIn(
                        "delivery chain required paths must be a non-empty unique subset of direct changes",
                        errors,
                    )
                else:
                    self.assertIn(
                        "delivery chain required paths must exactly match expected deployment contract paths",
                        errors,
                    )
                self.assertIn(
                    "default promotion cannot be claimed without all promotion gates", errors
                )

    def test_delivery_contract_path_must_bind_expected_contract_test(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        mutated["pilot_delivery_chain_evidence"]["contract_evidence"][
            "path"
        ] = "scripts/weltgewebe-up"
        errors = self.validator.validate(mutated)
        self.assertIn(
            "delivery contract evidence path must be the expected contract test", errors
        )
        self.assertIn(
            "default promotion cannot be claimed without all promotion gates", errors
        )

    def test_delivery_chain_failure_blocks_default_promotion(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        mutated["pilot_delivery_chain_evidence"]["contract_evidence"][
            "conclusion"
        ] = "failure"
        errors = self.validator.validate(mutated)
        self.assertIn("delivery contract evidence must be successful", errors)
        self.assertIn(
            "default promotion cannot be claimed without all promotion gates",
            errors,
        )

    def test_delivery_binding_failures_block_default_promotion(self) -> None:
        mutations = {
            "case_id": lambda data: data["pilot_delivery_chain_evidence"].update({"case_id": "wrong"}),
            "required_direct_paths": lambda data: data["pilot_delivery_chain_evidence"].update(
                {"required_direct_paths": ["not/a/direct/change"]}
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                mutated = copy.deepcopy(self.evidence)
                mutate(mutated)
                errors = self.validator.validate(mutated)
                self.assertIn(
                    "default promotion cannot be claimed without all promotion gates",
                    errors,
                )

    def test_exact_three_gold_profiles_are_required(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        web_case = next(case for case in mutated["cases"] if case["profile"] == "web_map")
        web_case["profile"] = "database_auth"
        errors = self.validator.validate(mutated)
        self.assertIn(
            "exactly database_auth, web_map and deployment_kubernetes gold cases are required",
            errors,
        )
        self.assertIn(
            "default promotion cannot be claimed without all promotion gates", errors
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
                lambda data: data["pilot_delivery_chain_evidence"].pop("contract_evidence"),
                "delivery chain must bind explicit contract evidence",
            ),
            "ci": (
                lambda data: data["pilot_delivery_chain_evidence"].pop("ci_evidence"),
                "delivery chain must bind explicit CI evidence",
            ),
            "deployment": (
                lambda data: data["pilot_delivery_chain_evidence"].pop("deployment_evidence"),
                "delivery chain must bind explicit deployment evidence",
            ),
            "runtime": (
                lambda data: data["pilot_delivery_chain_evidence"].pop("runtime_proof"),
                "delivery chain must bind an executed runtime proof",
            ),
            "recovery": (
                lambda data: data["pilot_delivery_chain_evidence"].pop("recovery_evidence"),
                "delivery chain must bind explicit recovery evidence",
            ),
            "rollback_risks": (
                lambda data: data["pilot_delivery_chain_evidence"].update({"rollback_risks": []}),
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
        runtime = mutated["pilot_delivery_chain_evidence"]["runtime_proof"]
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
        mutated["source_bundle"]["freshness_evidence"]["remote_commit"] = "0" * 40
        mutated["source_bundle"]["post_emit_health"] = "fail"
        errors = self.validator.validate(mutated)
        self.assertIn(
            "source bundle freshness evidence remote_commit must equal source_bundle.git_commit",
            errors,
        )
        self.assertIn("source_bundle.post_emit_health must be pass", errors)
        self.assertIn(
            "default promotion cannot be claimed without all promotion gates", errors
        )

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

    def test_duplicate_target_symbol_evidence_blocks_promotion(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        case = next(
            case for case in mutated["cases"] if case["profile"] == "deployment_kubernetes"
        )
        case["capsule"]["target_symbols"].append(
            copy.deepcopy(case["capsule"]["target_symbols"][0])
        )
        case["capsule"]["target_symbols_included"] += 1
        lane = case["capsule"]["lane_counts"]["target_symbols"]
        lane["included"] += 1
        lane["considered"] += 1
        lane["policy_omitted"] -= 1
        errors = self.validator.validate(mutated)
        self.assertIn(f"{case['id']}: target symbol identities must be unique", errors)
        self.assertIn(
            "default promotion cannot be claimed without all promotion gates", errors
        )

    def test_duplicate_materialized_causal_relation_blocks_promotion(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        case = next(
            case for case in mutated["cases"] if case["profile"] == "deployment_kubernetes"
        )
        relation = copy.deepcopy(case["capsule"]["representative_causal_relations"][0])
        case["capsule"]["representative_causal_relations"].append(relation)
        case["capsule"]["call_graph_truth"]["coherent_relation_count"] = 2
        errors = self.validator.validate(mutated)
        self.assertIn(
            f"{case['id']}: representative causal relation identities must be unique",
            errors,
        )
        self.assertIn(
            "default promotion cannot be claimed without all promotion gates", errors
        )

    def test_delivery_call_graph_count_is_derived_from_materialized_relations(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        case = next(
            case
            for case in mutated["cases"]
            if case["profile"] == "deployment_kubernetes"
        )
        case["capsule"]["call_graph_truth"]["coherent_relation_count"] = 2
        errors = self.validator.validate(mutated)
        self.assertIn(
            "delivery call-graph evidence count must be derived from materialized relations",
            errors,
        )
        self.assertIn(
            "default promotion cannot be claimed without all promotion gates", errors
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
        self.assertIn(
            "default promotion cannot be claimed without all promotion gates", errors
        )

    def test_measurement_worktree_must_be_clean_or_evidence_only_dirty(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        mutated["measurement_worktree"]["dirty_scope"] = "mixed"
        mutated["measurement_worktree"]["dirty_paths"] = ["apps/api/src/lib.rs"]
        errors = self.validator.validate(mutated)
        self.assertIn(
            "clean measurement worktree must have clean scope and no dirty paths",
            errors,
        )
        self.assertIn(
            "default promotion cannot be claimed without all promotion gates",
            errors,
        )

    def test_controlled_live_budget_truncation_cannot_claim_complete_delivery(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        live = next(case for case in mutated["cases"] if case["profile"] == "controlled_live")
        live["capsule"]["complete_direct_change_delivery"] = True
        errors = self.validator.validate(mutated)
        self.assertIn(
            f"{live['id']}: controlled live budget truncation must not claim complete direct-change delivery",
            errors,
        )
        self.assertIn(
            "default promotion cannot be claimed without all promotion gates",
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

    def test_related_test_evidence_must_match_its_provenance(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        case = mutated["cases"][0]
        related = case["capsule"]["related_tests"][0]
        related["path"] = "not-a-test.txt"
        related["provenance_strength"] = "invented"
        errors = self.validator.validate(mutated)
        self.assertTrue(
            any("changed-test evidence must be a direct change" in error for error in errors)
        )
        self.assertTrue(
            any("changed-test evidence provenance must be direct_diff" in error for error in errors)
        )
        self.assertIn(
            "default promotion cannot be claimed without all promotion gates", errors
        )

    def test_gold_direct_change_delivery_cannot_be_truncated(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        case = next(case for case in mutated["cases"] if case["profile"] == "database_auth")
        case["capsule"]["lane_counts"]["direct_changes"]["included"] -= 1
        errors = self.validator.validate(mutated)
        self.assertIn(
            f"{case['id']}: every gold case must deliver all direct changes", errors
        )
        self.assertIn(
            "default promotion cannot be claimed without all promotion gates", errors
        )

    def test_controlled_live_policy_omission_accounting_is_exact(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        live = next(case for case in mutated["cases"] if case["profile"] == "controlled_live")
        live["capsule"]["lane_counts"]["direct_changes"]["policy_omitted"] -= 1
        errors = self.validator.validate(mutated)
        self.assertIn(
            f"{live['id']}: direct_changes policy_omitted must equal available minus considered",
            errors,
        )
        self.assertIn(
            "default promotion cannot be claimed without all promotion gates", errors
        )

    def test_policy_and_budget_omission_are_separately_accounted(self) -> None:
        case = next(
            case for case in self.evidence["cases"] if case["profile"] == "deployment_kubernetes"
        )
        causal = case["capsule"]["lane_counts"]["causal_relations"]
        self.assertEqual(
            causal,
            {
                "available": 21,
                "considered": 8,
                "included": 7,
                "policy_omitted": 13,
                "budget_omitted": 1,
            },
        )

        mutations = {
            "policy": (
                lambda lane: lane.update({"policy_omitted": 12}),
                f"{case['id']}: causal_relations policy_omitted must equal available minus considered",
            ),
            "budget": (
                lambda lane: lane.update({"budget_omitted": 0}),
                f"{case['id']}: causal_relations budget_omitted must equal considered minus included",
            ),
        }
        for name, (mutate, expected) in mutations.items():
            with self.subTest(name=name):
                mutated = copy.deepcopy(self.evidence)
                mutated_case = next(
                    item for item in mutated["cases"] if item["profile"] == "deployment_kubernetes"
                )
                mutate(mutated_case["capsule"]["lane_counts"]["causal_relations"] )
                errors = self.validator.validate(mutated)
                self.assertIn(expected, errors)
                self.assertIn(
                    "default promotion cannot be claimed without all promotion gates", errors
                )

    def test_budget_degradation_rejects_unknown_or_duplicate_lane_names(self) -> None:
        mutations = {
            "unknown_exhausted": lambda budget: budget["exhausted_lanes"].append(
                "invented_lane"
            ),
            "duplicate_exhausted": lambda budget: budget["exhausted_lanes"].append(
                budget["exhausted_lanes"][0]
            ),
            "unknown_policy": lambda budget: budget["policy_limited_lanes"].append(
                "invented_lane"
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                mutated = copy.deepcopy(self.evidence)
                case = next(
                    case
                    for case in mutated["cases"]
                    if case["profile"] == "deployment_kubernetes"
                )
                mutate(case["capsule"]["budget_degradation"])
                errors = self.validator.validate(mutated)
                self.assertIn(
                    "default promotion cannot be claimed without all promotion gates",
                    errors,
                )

    def test_budget_and_policy_lane_lists_must_match_omission_evidence(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        case = next(
            case for case in mutated["cases"] if case["profile"] == "deployment_kubernetes"
        )
        case["capsule"]["budget_degradation"]["exhausted_lanes"].remove(
            "causal_relations"
        )
        case["capsule"]["budget_degradation"]["policy_limited_lanes"].remove(
            "causal_relations"
        )
        errors = self.validator.validate(mutated)
        self.assertIn(
            f"{case['id']}: tracked exhausted lanes must match budget_omitted evidence", errors
        )
        self.assertIn(
            f"{case['id']}: tracked policy-limited lanes must match policy_omitted evidence",
            errors,
        )
        self.assertIn(
            "default promotion cannot be claimed without all promotion gates", errors
        )

    def test_pilot_delivery_evidence_cross_identity_must_match(self) -> None:
        mutations = {
            "contract_pr": lambda delivery: delivery["contract_evidence"].update(
                {"pr": 1}
            ),
            "contract_pr_head": lambda delivery: delivery["contract_evidence"].update(
                {"pr_head_sha": "0" * 40}
            ),
            "required_gate_head": lambda delivery: delivery["ci_evidence"][
                "required_merge_gate"
            ].update({"head_sha": "0" * 40}),
            "contract_run_head": lambda delivery: delivery["contract_evidence"].update(
                {"run_head_sha": "0" * 40}
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                mutated = copy.deepcopy(self.evidence)
                mutate(mutated["pilot_delivery_chain_evidence"])
                errors = self.validator.validate(mutated)
                self.assertIn(
                    "default promotion cannot be claimed without all promotion gates",
                    errors,
                )

    def test_production_receipt_metadata_is_content_bound(self) -> None:
        mutations = {
            "artifact_id": lambda receipt: receipt.update({"artifact_id": 0}),
            "artifact_name": lambda receipt: receipt.update({"artifact_name": "wrong"}),
            "artifact_digest": lambda receipt: receipt.update({"artifact_digest": "sha256:bad"}),
            "bound_commit": lambda receipt: receipt.update({"bound_commit": "0" * 40}),
            "workflow_run_id": lambda receipt: receipt.update({"workflow_run_id": 1}),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                mutated = copy.deepcopy(self.evidence)
                receipt = mutated["pilot_delivery_chain_evidence"]["runtime_proof"][
                    "production_receipt"
                ]
                mutate(receipt)
                errors = self.validator.validate(mutated)
                self.assertIn(
                    "default promotion cannot be claimed without all promotion gates",
                    errors,
                )

    def test_late_scope_error_blocks_default_promotion(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        mutated["promotion_scope"] = "unbounded"
        errors = self.validator.validate(mutated)
        self.assertIn(
            "promotion_scope must remain bounded to measured change-impact handoff", errors
        )
        self.assertIn(
            "default promotion cannot be claimed without all promotion gates", errors
        )

    def test_lane_included_counts_must_match_capsule_counters(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        live = next(case for case in mutated["cases"] if case["profile"] == "controlled_live")
        live["capsule"]["lane_counts"]["target_symbols"]["included"] -= 1
        errors = self.validator.validate(mutated)
        self.assertIn(
            f"{live['id']}: target_symbols lane included count must match capsule counter",
            errors,
        )
        self.assertIn(
            "default promotion cannot be claimed without all promotion gates", errors
        )

    def test_budget_evidence_contains_no_manual_required_lane_verdict(self) -> None:
        for case in self.evidence["cases"]:
            self.assertNotIn("required_lane_loss", case["capsule"]["budget_degradation"])

    def test_fixture_contains_no_manual_verdict_fields(self) -> None:
        forbidden = {
            "acceptance",
            "mechanical_promotion_gate",
            "truth_gate",
            "overall_status",
            "promotion_recommendation",
        }
        self.assertTrue(forbidden.isdisjoint(self.evidence))
        for case in self.evidence["cases"]:
            self.assertNotIn("quality_pass", case)
        self.assertNotIn("status", self.evidence["pilot_delivery_chain_evidence"])
        self.assertNotIn("freshness", self.evidence["source_bundle"])

    def test_broken_diff_binding_blocks_computed_promotion(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        mutated["cases"][0]["capsule"]["diff_binding_verified"] = False
        errors = self.validator.validate(mutated)
        self.assertTrue(any("diff binding must be verified" in error for error in errors))
        self.assertIn(
            "default promotion cannot be claimed without all promotion gates", errors
        )

    def test_broken_baseline_blocks_computed_promotion_without_acceptance_input(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        mutated["cases"][0]["baseline"]["resolved_evidence_status"] = "degraded"
        errors = self.validator.validate(mutated)
        self.assertTrue(any("paired baseline must contain resolved evidence" in error for error in errors))
        self.assertIn(
            "default promotion cannot be claimed without all promotion gates", errors
        )

    def test_case_ids_and_direct_paths_must_be_unique(self) -> None:
        mutations = {}

        def duplicate_case_id(data: dict) -> None:
            data["cases"][1]["id"] = data["cases"][0]["id"]

        def duplicate_direct_path(data: dict) -> None:
            case = next(
                item for item in data["cases"] if item["profile"] == "deployment_kubernetes"
            )
            case["direct_change_paths"].append(case["direct_change_paths"][0])
            case["changed_path_count"] += 1
            lane = case["capsule"]["lane_counts"]["direct_changes"]
            lane["available"] += 1
            lane["considered"] += 1
            lane["included"] += 1

        def duplicate_expected_path(data: dict) -> None:
            case = next(
                item for item in data["cases"] if item["profile"] == "deployment_kubernetes"
            )
            case["expected_critical_paths"].append(case["expected_critical_paths"][0])

        mutations["case_id"] = duplicate_case_id
        mutations["direct_path"] = duplicate_direct_path
        mutations["expected_path"] = duplicate_expected_path
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                mutated = copy.deepcopy(self.evidence)
                mutate(mutated)
                errors = self.validator.validate(mutated)
                self.assertIn(
                    "default promotion cannot be claimed without all promotion gates", errors
                )

    def test_related_test_paths_must_be_unique(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        case = next(
            case for case in mutated["cases"] if case["profile"] == "deployment_kubernetes"
        )
        case["capsule"]["related_tests"].append(
            copy.deepcopy(case["capsule"]["related_tests"][0])
        )
        case["capsule"]["related_tests_included"] += 1
        lane = case["capsule"]["lane_counts"]["related_tests"]
        lane["available"] += 1
        lane["considered"] += 1
        lane["included"] += 1
        errors = self.validator.validate(mutated)
        self.assertIn(f"{case['id']}: related test paths must be unique", errors)
        self.assertIn(
            "default promotion cannot be claimed without all promotion gates", errors
        )

    def test_retrieval_lanes_must_be_closed_unique_partition(self) -> None:
        mutations = {
            "unknown": lambda lanes: lanes["used"].append("invented_lane"),
            "duplicate": lambda lanes: lanes["used"].append(lanes["used"][0]),
            "overlap": lambda lanes: lanes["skipped"].append(lanes["used"][0]),
            "missing": lambda lanes: lanes["skipped"].pop(),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                mutated = copy.deepcopy(self.evidence)
                case = next(
                    case for case in mutated["cases"] if case["profile"] == "database_auth"
                )
                mutate(case["capsule"]["retrieval_lanes"])
                errors = self.validator.validate(mutated)
                self.assertIn(
                    f"{case['id']}: retrieval lanes must be a unique disjoint partition of known lanes",
                    errors,
                )
                self.assertIn(
                    "default promotion cannot be claimed without all promotion gates", errors
                )

    def test_rollback_risk_names_must_be_unique(self) -> None:
        mutated = copy.deepcopy(self.evidence)
        risk = copy.deepcopy(mutated["pilot_delivery_chain_evidence"]["rollback_risks"][0])
        mutated["pilot_delivery_chain_evidence"]["rollback_risks"] = [
            copy.deepcopy(risk) for _ in range(4)
        ]
        errors = self.validator.validate(mutated)
        self.assertIn("rollback/recovery risk names must be unique", errors)
        self.assertIn(
            "default promotion cannot be claimed without all promotion gates", errors
        )


if __name__ == "__main__":
    unittest.main()
