from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVIDENCE = ROOT / "scripts/ci/fixtures/repoground_vertical_pilot.v1.json"
_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA64 = re.compile(r"[0-9a-f]{64}\Z")
_GOLD_PROFILES = {"database_auth", "web_map", "deployment_kubernetes"}
_MEASUREMENT_EVIDENCE_PATHS = {
    "docs/proofs/repoground-agent-utility-v1-t003-vertical-pilot.md",
    "scripts/ci/fixtures/repoground_vertical_pilot.v1.json",
    "scripts/ci/tests/test_repoground_vertical_pilot.py",
    "scripts/ci/validate_repoground_vertical_pilot.py",
}
_REQUIRED_ACCEPTANCE = {
    "three_classes": "pass",
    "paired_baseline": "pass",
    "quality": "pass_bounded",
    "retrieval_lane_truth": "pass",
    "freshness_and_diff_binding": "pass",
    "delivery_chain": "pass_bounded",
    "promotion_gate": "pass",
}
_REQUIRED_TRUTH_REQUIREMENTS = {
    "fresh_exact_bundle",
    "diff_binding_verified_all_cases",
    "impact_context_blocked_absent_all_cases",
    "call_graph_lane_matches_consumed_coherent_evidence_all_cases",
    "dirty_overlay_excluded_from_revision_diff_all_cases",
    "paired_baseline_resolved_evidence_all_cases",
}


def _is_sha(value: Any, pattern: re.Pattern[str]) -> bool:
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _looks_like_test_path(path: str) -> bool:
    name = Path(path).name
    return (
        "/tests/" in f"/{path}"
        or name.startswith("test_")
        or ".spec." in name
        or ".test." in name
    )


def validate(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if data.get("repo") != "weltgewebe":
        errors.append("repo must be weltgewebe")
    if data.get("task_profile") != "change_impact":
        errors.append("task_profile must be change_impact")
    if data.get("context_budget_bytes") != 12000:
        errors.append("context_budget_bytes must remain 12000")

    for field in (
        "grabowski_runtime_commit",
        "grabowski_t006_merge_commit",
        "grabowski_t006_hardening_merge_commit",
        "repoground_runtime_commit",
        "repoground_1070_merge_commit",
    ):
        if not _is_sha(data.get(field), _SHA40):
            errors.append(f"{field} must be a full commit SHA")

    source_bundle = data.get("source_bundle")
    if not isinstance(source_bundle, dict):
        errors.append("source_bundle must be an object")
        source_bundle = {}
    if source_bundle.get("freshness") != "fresh_exact":
        errors.append("source bundle must be fresh_exact")
    if not _is_sha(source_bundle.get("git_commit"), _SHA40):
        errors.append("source_bundle.git_commit must be a full commit SHA")
    if not _is_sha(source_bundle.get("manifest_sha256"), _SHA64):
        errors.append("source_bundle.manifest_sha256 must be a SHA-256")
    for field in ("post_emit_health", "output_health", "bundle_surface_validation"):
        if source_bundle.get(field) != "pass":
            errors.append(f"source_bundle.{field} must be pass")
    if source_bundle.get("generator_runtime_commit") != data.get(
        "repoground_runtime_commit"
    ):
        errors.append(
            "source_bundle.generator_runtime_commit must match repoground_runtime_commit"
        )

    measurement_worktree = data.get("measurement_worktree")
    if not isinstance(measurement_worktree, dict):
        errors.append("measurement_worktree must be an object")
        measurement_worktree = {}
    if measurement_worktree.get("head") != source_bundle.get("git_commit"):
        errors.append("measurement worktree head must equal source bundle git_commit")
    if measurement_worktree.get("dirty") is not True:
        errors.append("measurement worktree must record the evidence-only dirty state")
    if measurement_worktree.get("dirty_scope") != "evidence_only":
        errors.append("measurement worktree dirty scope must be evidence_only")
    dirty_paths = measurement_worktree.get("dirty_paths")
    if not isinstance(dirty_paths, list) or set(dirty_paths) != _MEASUREMENT_EVIDENCE_PATHS:
        errors.append("measurement worktree dirty paths must equal the four evidence files")
    if measurement_worktree.get("included_in_revision_diff") is not False:
        errors.append("measurement worktree evidence edits must be excluded from revision diff")

    observed_overlay = data.get("observed_foreign_dirty_overlay")
    if not isinstance(observed_overlay, dict):
        errors.append("observed_foreign_dirty_overlay must be an object")
    elif observed_overlay.get("dirty") is True and observed_overlay.get(
        "included_in_revision_diff"
    ) is not False:
        errors.append("foreign dirty overlay must remain excluded from revision diff")

    cases = data.get("cases")
    if not isinstance(cases, list) or len(cases) != 4:
        errors.append("exactly three gold cases plus one controlled live case are required")
        return errors

    gold_cases = [
        case
        for case in cases
        if isinstance(case, dict) and case.get("profile") in _GOLD_PROFILES
    ]
    gold_profiles = {case.get("profile") for case in gold_cases}
    if len(gold_cases) != 3 or gold_profiles != _GOLD_PROFILES:
        errors.append(
            "exactly database_auth, web_map and deployment_kubernetes gold cases are required"
        )
    live_cases = [
        case
        for case in cases
        if isinstance(case, dict) and case.get("profile") == "controlled_live"
    ]
    controlled_live_pass = len(live_cases) == 1
    if not controlled_live_pass:
        errors.append("exactly one controlled_live case is required")
    elif live_cases[0].get("target_commit") != source_bundle.get("git_commit"):
        errors.append("controlled_live target commit must equal source bundle git_commit")
        controlled_live_pass = False

    qualifying: list[str] = []
    lane_truth_pass = True
    for case in cases:
        if not isinstance(case, dict):
            errors.append("every case must be an object")
            continue

        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id:
            errors.append("every case must have an id")
            continue

        for field in ("base_commit", "target_commit", "base_revision", "target_revision"):
            if not _is_sha(case.get(field), _SHA40):
                errors.append(f"{case_id}: {field} must be a full commit SHA")
        if case.get("base_commit") != case.get("base_revision"):
            errors.append(f"{case_id}: base commit and revision must match")
        if case.get("target_commit") != case.get("target_revision"):
            errors.append(f"{case_id}: target commit and revision must match")
        if not _is_sha(case.get("diff_sha256"), _SHA64):
            errors.append(f"{case_id}: diff_sha256 must be a SHA-256")
        if case.get("diff_binding_kind") != "git_tree_delta_v1":
            errors.append(f"{case_id}: diff_binding_kind must be git_tree_delta_v1")

        direct = case.get("direct_change_paths")
        expected = case.get("expected_critical_paths")
        missing = case.get("missing_critical_paths")
        if not isinstance(direct, list) or not direct or not all(
            isinstance(path, str) and path for path in direct
        ):
            errors.append(f"{case_id}: direct_change_paths must be a non-empty string list")
            direct = []
        if case.get("changed_path_count") != len(direct):
            errors.append(f"{case_id}: changed_path_count must match direct_change_paths")
        if not isinstance(expected, list) or not expected:
            errors.append(f"{case_id}: expected_critical_paths must be non-empty")
            expected = []
        if set(expected) != set(direct):
            errors.append(f"{case_id}: bounded critical paths must equal all direct changes")
        if not isinstance(missing, list) or missing:
            errors.append(f"{case_id}: critical-path coverage must have no missing paths")
        if case.get("critical_path_coverage") != 1.0:
            errors.append(f"{case_id}: critical_path_coverage must be 1.0")
        if case.get("profile") in _GOLD_PROFILES and not any(
            _looks_like_test_path(path) for path in direct
        ):
            errors.append(f"{case_id}: every gold case must directly include a changed test path")
        if case.get("quality_pass") is not True:
            errors.append(f"{case_id}: bounded quality check must pass")

        baseline = case.get("baseline")
        capsule = case.get("capsule")
        if not isinstance(baseline, dict) or not isinstance(capsule, dict):
            errors.append(f"{case_id}: baseline and capsule must be objects")
            continue
        if baseline.get("available") is not True:
            errors.append(f"{case_id}: paired baseline must be available")
        if baseline.get("direct_context_pack_verified") is not True:
            errors.append(f"{case_id}: direct baseline context pack must be freshly verified")
        if baseline.get("freshness_status") != "fresh":
            errors.append(f"{case_id}: paired baseline must be fresh")
        if baseline.get("resolved_evidence_status") != "available":
            errors.append(f"{case_id}: paired baseline must contain resolved evidence")
        for field in ("snippet_count", "range_count", "citation_count"):
            value = baseline.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                errors.append(f"{case_id}: baseline {field} must be positive")
        if capsule.get("available") is not True:
            errors.append(f"{case_id}: capsule must be available")

        related_tests = capsule.get("related_tests")
        if not isinstance(related_tests, list):
            errors.append(f"{case_id}: related_tests must be an explicit list")
            related_tests = []
        if capsule.get("related_tests_included") != len(related_tests):
            errors.append(f"{case_id}: related_tests count must match explicit evidence")
        if case.get("profile") in _GOLD_PROFILES and not related_tests:
            errors.append(f"{case_id}: every gold case must include at least one related test")

        target_symbols = capsule.get("target_symbols")
        if not isinstance(target_symbols, list):
            errors.append(f"{case_id}: target_symbols must be an explicit list")
            target_symbols = []
        if capsule.get("target_symbols_included") != len(target_symbols):
            errors.append(f"{case_id}: target symbol count must match explicit evidence")
        for symbol in target_symbols:
            if not isinstance(symbol, dict) or not all(
                isinstance(symbol.get(field), str) and symbol.get(field)
                for field in ("id", "qualified_name", "path", "range_ref")
            ):
                errors.append(f"{case_id}: every target symbol needs bound identity and range")

        representative_relations = capsule.get("representative_causal_relations")
        if not isinstance(representative_relations, list):
            errors.append(
                f"{case_id}: representative_causal_relations must be an explicit list"
            )
            representative_relations = []

        gaps = capsule.get("gaps")
        if not isinstance(gaps, list):
            errors.append(f"{case_id}: gaps must be an explicit list")
            gaps = []
        for gap in gaps:
            if not isinstance(gap, dict) or not isinstance(gap.get("paths"), list):
                errors.append(f"{case_id}: every gap must bind its affected paths")

        baseline_bytes = baseline.get("payload_bytes")
        context_bytes = capsule.get("context_bytes")
        reported_baseline = capsule.get("general_context_pack_bytes_reported")
        byte_accounting_valid = True
        if (
            not isinstance(baseline_bytes, int)
            or isinstance(baseline_bytes, bool)
            or baseline_bytes <= 0
        ):
            errors.append(f"{case_id}: baseline payload_bytes must be positive")
            byte_accounting_valid = False
        if baseline.get("payload_bytes_source") != (
            "repoground_context_compose.compactness.general_context_pack_bytes"
        ):
            errors.append(f"{case_id}: baseline byte source must be explicit")
        if reported_baseline != baseline_bytes:
            errors.append(
                f"{case_id}: capsule baseline byte accounting must match paired baseline"
            )
        if (
            not isinstance(context_bytes, int)
            or isinstance(context_bytes, bool)
            or context_bytes <= 0
        ):
            errors.append(f"{case_id}: capsule context_bytes must be positive")
            byte_accounting_valid = False

        computed_reduction: float | None = None
        if byte_accounting_valid:
            assert isinstance(baseline_bytes, int)
            assert isinstance(context_bytes, int)
            computed_ratio = round(context_bytes / baseline_bytes, 6)
            computed_reduction = round((1 - computed_ratio) * 100, 3)
            if not _is_number(capsule.get("ratio")) or capsule.get("ratio") != computed_ratio:
                errors.append(f"{case_id}: capsule ratio must match byte accounting")
            if (
                not _is_number(capsule.get("reduction_pct"))
                or capsule.get("reduction_pct") != computed_reduction
            ):
                errors.append(f"{case_id}: capsule reduction_pct must match byte accounting")

        if capsule.get("diff_binding_verified") is not True:
            errors.append(f"{case_id}: diff binding must be verified")
        if capsule.get("freshness_status") != "fresh":
            errors.append(f"{case_id}: RepoGround publication must be fresh")
        if capsule.get("status") not in {"available", "degraded"}:
            errors.append(f"{case_id}: capsule status must be available or degraded")

        stop_criteria = capsule.get("stop_criteria")
        if not isinstance(stop_criteria, dict):
            errors.append(f"{case_id}: stop_criteria must be an object")
            stop_criteria = {}
        triggered = stop_criteria.get("triggered", [])
        if not isinstance(triggered, list):
            errors.append(f"{case_id}: stop_criteria.triggered must be a list")
            triggered = []
        if "impact_context_blocked" in triggered or stop_criteria.get(
            "impact_context_blocked"
        ) is not False:
            errors.append(f"{case_id}: impact_context_blocked must be absent")

        overlay = capsule.get("dirty_overlay")
        if not isinstance(overlay, dict):
            errors.append(f"{case_id}: dirty_overlay must be an object")
        elif overlay.get("dirty") is True and overlay.get(
            "included_in_revision_diff"
        ) is not False:
            errors.append(f"{case_id}: dirty overlay must be excluded from revision diff")

        nonclaims = capsule.get("does_not_establish")
        if not isinstance(nonclaims, list) or "completeness" not in nonclaims:
            errors.append(f"{case_id}: capsule must retain the completeness non-claim")

        lanes = capsule.get("retrieval_lanes")
        if not isinstance(lanes, dict):
            errors.append(f"{case_id}: retrieval_lanes must be an object")
            lanes = {}
        used = lanes.get("used", [])
        skipped = lanes.get("skipped", [])
        if not isinstance(used, list) or not isinstance(skipped, list):
            errors.append(f"{case_id}: retrieval lane lists must be arrays")
            used, skipped = [], []

        call_graph = capsule.get("call_graph_truth")
        if not isinstance(call_graph, dict):
            errors.append(f"{case_id}: call_graph_truth must be an object")
            lane_truth_pass = False
        else:
            if call_graph.get("artifact_available") is not True:
                errors.append(f"{case_id}: call graph artifact must be available")
            if not _is_sha(call_graph.get("artifact_sha256"), _SHA64):
                errors.append(f"{case_id}: call graph artifact SHA must be a SHA-256")
            consumed = call_graph.get("consumed_coherent_evidence")
            coherent_count = call_graph.get("coherent_relation_count")
            if consumed is True:
                if not isinstance(coherent_count, int) or coherent_count <= 0:
                    errors.append(
                        f"{case_id}: consumed call graph needs coherent relation evidence"
                    )
                    lane_truth_pass = False
                coherent_relations = [
                    relation
                    for relation in representative_relations
                    if isinstance(relation, dict)
                    and relation.get("source") == "python_call_graph_json"
                    and relation.get("status") == "coherent"
                    and relation.get("artifact_sha256")
                    == call_graph.get("artifact_sha256")
                ]
                if not coherent_relations:
                    errors.append(
                        f"{case_id}: consumed call graph needs explicit coherent relation provenance"
                    )
                    lane_truth_pass = False
                if "call_graph" not in used or "call_graph" in skipped:
                    errors.append(
                        f"{case_id}: call_graph must be used only when coherent evidence is consumed"
                    )
                    lane_truth_pass = False
            elif consumed is False:
                if coherent_count != 0:
                    errors.append(
                        f"{case_id}: skipped call graph must have zero coherent consumed relations"
                    )
                    lane_truth_pass = False
                if representative_relations:
                    errors.append(
                        f"{case_id}: skipped call graph must not claim representative causal evidence"
                    )
                    lane_truth_pass = False
                if "call_graph" in used or "call_graph" not in skipped:
                    errors.append(
                        f"{case_id}: call_graph must be skipped without coherent consumed evidence"
                    )
                    lane_truth_pass = False
            else:
                errors.append(
                    f"{case_id}: consumed_coherent_evidence must be a boolean"
                )
                lane_truth_pass = False

        if (
            case.get("profile") in _GOLD_PROFILES
            and case.get("quality_pass") is True
            and computed_reduction is not None
            and computed_reduction >= 20.0
        ):
            qualifying.append(case_id)

    mechanical = data.get("mechanical_promotion_gate")
    if not isinstance(mechanical, dict):
        errors.append("mechanical_promotion_gate must be an object")
    else:
        if mechanical.get("passed") is not True:
            errors.append("mechanical compactness promotion gate must pass")
        if mechanical.get("required_count") != 2:
            errors.append("mechanical promotion gate must require two cases")
        if sorted(mechanical.get("qualifying_case_ids", [])) != sorted(qualifying):
            errors.append(
                "mechanical promotion qualifying cases do not match recomputed measurements"
            )
    if len(qualifying) < 2:
        errors.append("at least two gold cases must reduce context by at least 20 percent")

    truth_gate = data.get("truth_gate")
    if not isinstance(truth_gate, dict):
        errors.append("truth_gate must be an object")
    else:
        if truth_gate.get("passed") is not True:
            errors.append("truth gate must pass")
        requirements = truth_gate.get("requirements")
        if not isinstance(requirements, dict):
            errors.append("truth_gate.requirements must be an object")
        else:
            for requirement in _REQUIRED_TRUTH_REQUIREMENTS:
                if requirements.get(requirement) is not True:
                    errors.append(f"truth requirement {requirement} must pass")
    if not lane_truth_pass:
        errors.append("retrieval lane truth must pass")

    deployment_cases = [
        case for case in cases if isinstance(case, dict)
        and case.get("profile") == "deployment_kubernetes"
    ]
    delivery_evidence_pass = True
    delivery = data.get("delivery_chain")
    if not isinstance(delivery, dict):
        errors.append("delivery_chain must be an object")
    elif len(deployment_cases) != 1:
        errors.append("exactly one deployment_kubernetes case is required")
    else:
        deployment = deployment_cases[0]
        if delivery.get("status") != "pass_bounded":
            errors.append("delivery chain must pass bounded evidence")
        if delivery.get("case_id") != deployment.get("id"):
            errors.append("delivery chain must bind to the deployment case")
        direct = set(deployment.get("direct_change_paths", []))
        required_direct = delivery.get("required_direct_paths")
        if not isinstance(required_direct, list) or not set(required_direct).issubset(direct):
            errors.append("delivery chain required paths must be direct changes")
        capsule = deployment.get("capsule", {})
        for field in (
            "target_symbols_included",
            "causal_relations_included",
            "live_ranges_included",
        ):
            value = delivery.get(field)
            if not isinstance(value, int) or value <= 0:
                errors.append(f"delivery chain {field} must be positive")
            if value != capsule.get(field):
                errors.append(f"delivery chain {field} must match deployment capsule")
        coherent = delivery.get("coherent_call_graph_relation_count")
        call_graph = capsule.get("call_graph_truth", {})
        if not isinstance(coherent, int) or coherent <= 0:
            errors.append("delivery chain needs coherent call-graph relation evidence")
        if coherent != call_graph.get("coherent_relation_count"):
            errors.append("delivery call-graph evidence must match deployment capsule")
        representative_ranges = capsule.get("representative_live_ranges")
        if not isinstance(representative_ranges, list) or not representative_ranges:
            errors.append("delivery chain needs explicit representative live-range evidence")
        elif not any(
            isinstance(item, dict)
            and item.get("path") == "scripts/ops/reconcile-production-main-vps.sh"
            and isinstance(item.get("start_line"), int)
            and isinstance(item.get("end_line"), int)
            and _is_sha(item.get("content_sha256"), _SHA64)
            for item in representative_ranges
        ):
            errors.append("delivery live-range evidence must bind the production reconciler")

        contract = delivery.get("contract_evidence")
        if not isinstance(contract, dict):
            errors.append("delivery chain must bind explicit contract evidence")
            delivery_evidence_pass = False
        else:
            if contract.get("path") not in direct:
                errors.append("delivery contract evidence path must be a direct change")
                delivery_evidence_pass = False
            if contract.get("conclusion") != "success":
                errors.append("delivery contract evidence must be successful")
                delivery_evidence_pass = False
            for field in ("workflow_run_id", "job_id"):
                if not isinstance(contract.get(field), int) or contract.get(field) <= 0:
                    errors.append(f"delivery contract evidence {field} must be positive")
                    delivery_evidence_pass = False

        ci_evidence = delivery.get("ci_evidence")
        if not isinstance(ci_evidence, dict):
            errors.append("delivery chain must bind explicit CI evidence")
            delivery_evidence_pass = False
        else:
            for gate_name in ("required_merge_gate", "review_evidence_gate"):
                gate = ci_evidence.get(gate_name)
                if not isinstance(gate, dict) or gate.get("conclusion") != "success":
                    errors.append(f"delivery CI evidence {gate_name} must be successful")
                    delivery_evidence_pass = False
                    continue
                for field in ("workflow_run_id", "job_id"):
                    if not isinstance(gate.get(field), int) or gate.get(field) <= 0:
                        errors.append(
                            f"delivery CI evidence {gate_name}.{field} must be positive"
                        )
                        delivery_evidence_pass = False

        deployment_evidence = delivery.get("deployment_evidence")
        if not isinstance(deployment_evidence, dict):
            errors.append("delivery chain must bind explicit deployment evidence")
            delivery_evidence_pass = False
        else:
            deployment_target = deployment.get("target_commit")
            if deployment_evidence.get("head_sha") != deployment_target or (
                deployment_evidence.get("merge_commit") != deployment_target
            ):
                errors.append("deployment evidence must bind the exact deployment case target")
                delivery_evidence_pass = False
            if deployment_evidence.get("event") != "push" or (
                deployment_evidence.get("conclusion") != "success"
            ):
                errors.append("deployment evidence must be a successful post-merge push run")
                delivery_evidence_pass = False
            if not isinstance(deployment_evidence.get("workflow_run_id"), int):
                errors.append("deployment workflow_run_id must be present")
                delivery_evidence_pass = False

        runtime_proof = delivery.get("runtime_proof")
        if not isinstance(runtime_proof, dict):
            errors.append("delivery chain must bind an executed runtime proof")
            delivery_evidence_pass = False
        else:
            if runtime_proof.get("head_sha") != deployment.get("target_commit"):
                errors.append("runtime proof must bind the exact deployment case target")
                delivery_evidence_pass = False
            if runtime_proof.get("workflow_run_id") != (
                deployment_evidence.get("workflow_run_id")
                if isinstance(deployment_evidence, dict)
                else None
            ):
                errors.append("runtime proof must come from the bound deployment run")
                delivery_evidence_pass = False
            if runtime_proof.get("job_name") != "Exact main commit is live" or (
                runtime_proof.get("conclusion") != "success"
            ):
                errors.append("runtime proof exact-main-live job must succeed")
                delivery_evidence_pass = False
            if runtime_proof.get("public_identity_step") != (
                "Verify public frontend and API identity"
            ) or runtime_proof.get("public_identity_step_conclusion") != "success":
                errors.append("runtime proof must include successful public identity verification")
                delivery_evidence_pass = False
            if runtime_proof.get("production_receipt_uploaded") is not True:
                errors.append("runtime proof must include an uploaded production receipt")
                delivery_evidence_pass = False
            if not isinstance(runtime_proof.get("job_id"), int):
                errors.append("runtime proof job_id must be present")
                delivery_evidence_pass = False

        recovery = delivery.get("recovery_evidence")
        if not isinstance(recovery, dict):
            errors.append("delivery chain must bind explicit recovery evidence")
            delivery_evidence_pass = False
        else:
            expected_recovery = {
                "documentation_path": "docs/deploy/merge-to-live.md",
                "contract_test_path": "scripts/ci/tests/test_production_reconciler_contract.py",
                "atomic_install_test": "test_installer_deferred_update_is_atomic_and_non_recursive",
                "direct_recovery_supported": True,
                "contention_no_effects": True,
                "contention_exit_code": 75,
                "atomic_install": True,
                "timer_state_preserved": True,
            }
            for field, expected_value in expected_recovery.items():
                if recovery.get(field) != expected_value:
                    errors.append(f"delivery recovery evidence {field} must be {expected_value!r}")
                    delivery_evidence_pass = False
            if not isinstance(recovery.get("documentation_range"), str) or not recovery.get(
                "documentation_range", ""
            ).startswith("file:docs/deploy/merge-to-live.md#L"):
                errors.append("delivery recovery evidence must bind a documentation range")
                delivery_evidence_pass = False

        rollback_risks = delivery.get("rollback_risks")
        if not isinstance(rollback_risks, list) or len(rollback_risks) < 4:
            errors.append("delivery chain must enumerate rollback/recovery risks")
            delivery_evidence_pass = False
        elif not all(
            isinstance(item, dict)
            and isinstance(item.get("risk"), str)
            and item.get("risk")
            and isinstance(item.get("mitigation"), str)
            and item.get("mitigation")
            for item in rollback_risks
        ):
            errors.append("every rollback/recovery risk needs a named mitigation")
            delivery_evidence_pass = False

        delivery_nonclaims = delivery.get("does_not_establish")
        if not isinstance(delivery_nonclaims, list) or not {
            "runtime_correctness",
            "automatic_rollback_success",
        }.issubset(delivery_nonclaims):
            errors.append("delivery chain must retain runtime and automatic-rollback non-claims")
            delivery_evidence_pass = False

    acceptance = data.get("acceptance")
    if not isinstance(acceptance, dict):
        errors.append("acceptance must be an object")
    else:
        for field, expected in _REQUIRED_ACCEPTANCE.items():
            if acceptance.get(field) != expected:
                errors.append(f"acceptance.{field} must be {expected}")

    promotion_ready = (
        len(qualifying) >= 2
        and controlled_live_pass
        and lane_truth_pass
        and delivery_evidence_pass
        and isinstance(delivery, dict)
        and delivery.get("status") == "pass_bounded"
        and isinstance(truth_gate, dict)
        and truth_gate.get("passed") is True
    )
    if data.get("overall_status") != "pass":
        errors.append("overall_status must be pass for the promoted bounded pilot")
    if data.get("promotion_scope") != "bounded_change_impact_context_for_agent_handoff":
        errors.append("promotion_scope must remain bounded to measured change-impact handoff")
    if data.get("promotion_recommendation") != "promote_default":
        errors.append("promotion recommendation must reflect the passing bounded pilot")
    if not promotion_ready and data.get("promotion_recommendation") == "promote_default":
        errors.append("default promotion cannot be claimed without all promotion gates")

    return errors


def load(path: Path = DEFAULT_EVIDENCE) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("pilot evidence must be a JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_EVIDENCE)
    args = parser.parse_args()
    errors = validate(load(args.path))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("RepoGround vertical pilot evidence: valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
