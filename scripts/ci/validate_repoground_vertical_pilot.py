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
    source_bundle_pass = True
    if source_bundle.get("freshness") != "fresh_exact":
        errors.append("source bundle must be fresh_exact")
        source_bundle_pass = False
    if not _is_sha(source_bundle.get("git_commit"), _SHA40):
        errors.append("source_bundle.git_commit must be a full commit SHA")
        source_bundle_pass = False
    if not _is_sha(source_bundle.get("manifest_sha256"), _SHA64):
        errors.append("source_bundle.manifest_sha256 must be a SHA-256")
        source_bundle_pass = False
    for field in ("post_emit_health", "output_health", "bundle_surface_validation"):
        if source_bundle.get(field) != "pass":
            errors.append(f"source_bundle.{field} must be pass")
            source_bundle_pass = False
    if source_bundle.get("generator_runtime_commit") != data.get("repoground_runtime_commit"):
        errors.append(
            "source_bundle.generator_runtime_commit must match repoground_runtime_commit"
        )
        source_bundle_pass = False

    measurement_worktree = data.get("measurement_worktree")
    measurement_worktree_pass = True
    if not isinstance(measurement_worktree, dict):
        errors.append("measurement_worktree must be an object")
        measurement_worktree = {}
        measurement_worktree_pass = False
    if measurement_worktree.get("head") != source_bundle.get("git_commit"):
        errors.append("measurement worktree head must equal source bundle git_commit")
        measurement_worktree_pass = False
    dirty = measurement_worktree.get("dirty")
    dirty_scope = measurement_worktree.get("dirty_scope")
    dirty_paths = measurement_worktree.get("dirty_paths")
    if dirty is False:
        if dirty_scope != "clean" or dirty_paths != []:
            errors.append("clean measurement worktree must have clean scope and no dirty paths")
            measurement_worktree_pass = False
    elif dirty is True:
        if dirty_scope != "evidence_only":
            errors.append("dirty measurement worktree scope must be evidence_only")
            measurement_worktree_pass = False
        if (
            not isinstance(dirty_paths, list)
            or not dirty_paths
            or not set(dirty_paths).issubset(_MEASUREMENT_EVIDENCE_PATHS)
        ):
            errors.append("dirty measurement worktree paths must be non-empty and evidence-only")
            measurement_worktree_pass = False
    else:
        errors.append("measurement worktree dirty must be a boolean")
        measurement_worktree_pass = False
    if measurement_worktree.get("included_in_revision_diff") is not False:
        errors.append("measurement worktree edits must be excluded from revision diff")
        measurement_worktree_pass = False

    observed_overlay = data.get("observed_foreign_dirty_overlay")
    observed_overlay_pass = True
    if not isinstance(observed_overlay, dict):
        errors.append("observed_foreign_dirty_overlay must be an object")
        observed_overlay_pass = False
    elif observed_overlay.get("dirty") is True and observed_overlay.get(
        "included_in_revision_diff"
    ) is not False:
        errors.append("foreign dirty overlay must remain excluded from revision diff")
        observed_overlay_pass = False

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
    three_classes_pass = len(gold_cases) == 3 and gold_profiles == _GOLD_PROFILES
    if not three_classes_pass:
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
    diff_binding_pass = True
    freshness_pass = source_bundle_pass
    impact_unblocked_pass = True
    overlay_exclusion_pass = measurement_worktree_pass and observed_overlay_pass
    baseline_evidence_pass = True
    bounded_quality_pass = True

    for case in cases:
        if not isinstance(case, dict):
            errors.append("every case must be an object")
            diff_binding_pass = False
            freshness_pass = False
            impact_unblocked_pass = False
            overlay_exclusion_pass = False
            baseline_evidence_pass = False
            bounded_quality_pass = False
            continue

        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id:
            errors.append("every case must have an id")
            diff_binding_pass = False
            continue

        for field in ("base_commit", "target_commit", "base_revision", "target_revision"):
            if not _is_sha(case.get(field), _SHA40):
                errors.append(f"{case_id}: {field} must be a full commit SHA")
                diff_binding_pass = False
        if case.get("base_commit") != case.get("base_revision"):
            errors.append(f"{case_id}: base commit and revision must match")
            diff_binding_pass = False
        if case.get("target_commit") != case.get("target_revision"):
            errors.append(f"{case_id}: target commit and revision must match")
            diff_binding_pass = False
        if not _is_sha(case.get("diff_sha256"), _SHA64):
            errors.append(f"{case_id}: diff_sha256 must be a SHA-256")
            diff_binding_pass = False
        if case.get("diff_binding_kind") != "git_tree_delta_v1":
            errors.append(f"{case_id}: diff_binding_kind must be git_tree_delta_v1")
            diff_binding_pass = False

        profile = case.get("profile")
        direct = case.get("direct_change_paths")
        if not isinstance(direct, list) or not direct or not all(
            isinstance(path, str) and path for path in direct
        ):
            errors.append(f"{case_id}: direct_change_paths must be a non-empty string list")
            direct = []
            bounded_quality_pass = False
        if case.get("changed_path_count") != len(direct):
            errors.append(f"{case_id}: changed_path_count must match direct_change_paths")
            bounded_quality_pass = False

        if profile in _GOLD_PROFILES:
            expected = case.get("expected_critical_paths")
            missing = case.get("missing_critical_paths")
            if not isinstance(expected, list) or not expected:
                errors.append(f"{case_id}: expected_critical_paths must be non-empty")
                expected = []
                bounded_quality_pass = False
            if set(expected) != set(direct):
                errors.append(f"{case_id}: bounded critical paths must equal all direct changes")
                bounded_quality_pass = False
            if not isinstance(missing, list) or missing:
                errors.append(f"{case_id}: critical-path coverage must have no missing paths")
                bounded_quality_pass = False
            if case.get("critical_path_coverage") != 1.0:
                errors.append(f"{case_id}: critical_path_coverage must be 1.0")
                bounded_quality_pass = False
            if case.get("delivery_completeness_required") is not True:
                errors.append(f"{case_id}: gold cases must require complete direct-change delivery")
                bounded_quality_pass = False
        elif profile == "controlled_live":
            if any(
                field in case
                for field in (
                    "expected_critical_paths",
                    "missing_critical_paths",
                    "critical_path_coverage",
                )
            ):
                errors.append(
                    f"{case_id}: controlled live case must not claim gold critical-path completeness"
                )
                controlled_live_pass = False
            if case.get("delivery_completeness_required") is not False:
                errors.append(
                    f"{case_id}: controlled live case must explicitly disable completeness requirement"
                )
                controlled_live_pass = False

        if case.get("quality_pass") is not True:
            errors.append(f"{case_id}: bounded quality check must pass")
            bounded_quality_pass = False

        baseline = case.get("baseline")
        capsule = case.get("capsule")
        if not isinstance(baseline, dict) or not isinstance(capsule, dict):
            errors.append(f"{case_id}: baseline and capsule must be objects")
            baseline_evidence_pass = False
            freshness_pass = False
            diff_binding_pass = False
            bounded_quality_pass = False
            if profile == "controlled_live":
                controlled_live_pass = False
            continue

        lane_counts = capsule.get("lane_counts")
        if not isinstance(lane_counts, dict):
            errors.append(f"{case_id}: lane_counts must be an object")
            lane_counts = {}
            bounded_quality_pass = False
        direct_lane = lane_counts.get("direct_changes")
        if not isinstance(direct_lane, dict):
            errors.append(f"{case_id}: direct_changes lane count must be an object")
            direct_lane = {}
            bounded_quality_pass = False

        available_direct = direct_lane.get("available")
        included_direct = direct_lane.get("included")
        policy_omitted = direct_lane.get("policy_omitted", 0)
        if profile in _GOLD_PROFILES:
            if available_direct != len(direct) or included_direct != len(direct):
                errors.append(f"{case_id}: every gold case must deliver all direct changes")
                bounded_quality_pass = False
            if policy_omitted != 0:
                errors.append(f"{case_id}: gold direct-change delivery must not omit paths")
                bounded_quality_pass = False
        elif profile == "controlled_live":
            if available_direct != len(direct):
                errors.append(
                    f"{case_id}: controlled live direct-change inventory must match revision diff"
                )
                controlled_live_pass = False
            if (
                not isinstance(included_direct, int)
                or isinstance(included_direct, bool)
                or included_direct <= 0
                or not isinstance(available_direct, int)
                or isinstance(available_direct, bool)
                or included_direct > available_direct
            ):
                errors.append(
                    f"{case_id}: controlled live delivered direct-change count must be bounded"
                )
                controlled_live_pass = False
            if (
                not isinstance(policy_omitted, int)
                or isinstance(policy_omitted, bool)
                or policy_omitted < 0
                or not isinstance(available_direct, int)
                or not isinstance(included_direct, int)
                or policy_omitted != available_direct - included_direct
            ):
                errors.append(
                    f"{case_id}: controlled live policy_omitted must equal available minus included"
                )
                controlled_live_pass = False
            if (
                isinstance(available_direct, int)
                and isinstance(included_direct, int)
                and included_direct < available_direct
                and capsule.get("complete_direct_change_delivery") is not False
            ):
                errors.append(
                    f"{case_id}: controlled live budget truncation must not claim complete direct-change delivery"
                )
                controlled_live_pass = False

        budget_degradation = capsule.get("budget_degradation")
        if not isinstance(budget_degradation, dict):
            errors.append(f"{case_id}: budget_degradation must be an object")
            bounded_quality_pass = False
        else:
            if budget_degradation.get("required_lane_loss") is not False:
                errors.append(f"{case_id}: budget degradation must not lose required lanes")
                bounded_quality_pass = False
            exhausted_lanes = budget_degradation.get("exhausted_lanes")
            if not isinstance(exhausted_lanes, list) or not all(
                isinstance(lane, str) and lane for lane in exhausted_lanes
            ):
                errors.append(f"{case_id}: budget degradation exhausted_lanes must be a string list")
                bounded_quality_pass = False

        if baseline.get("available") is not True:
            errors.append(f"{case_id}: paired baseline must be available")
            baseline_evidence_pass = False
        if baseline.get("direct_context_pack_verified") is not True:
            errors.append(f"{case_id}: direct baseline context pack must be freshly verified")
            baseline_evidence_pass = False
        if baseline.get("freshness_status") != "fresh":
            errors.append(f"{case_id}: paired baseline must be fresh")
            baseline_evidence_pass = False
            freshness_pass = False
        if baseline.get("resolved_evidence_status") != "available":
            errors.append(f"{case_id}: paired baseline must contain resolved evidence")
            baseline_evidence_pass = False
        for field in ("snippet_count", "range_count", "citation_count"):
            value = baseline.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                errors.append(f"{case_id}: baseline {field} must be positive")
                baseline_evidence_pass = False
        if capsule.get("available") is not True:
            errors.append(f"{case_id}: capsule must be available")
            bounded_quality_pass = False

        related_tests = capsule.get("related_tests")
        if not isinstance(related_tests, list):
            errors.append(f"{case_id}: related_tests must be an explicit list")
            related_tests = []
            bounded_quality_pass = False
        if capsule.get("related_tests_included") != len(related_tests):
            errors.append(f"{case_id}: related_tests count must match explicit evidence")
            bounded_quality_pass = False
        if case.get("profile") in _GOLD_PROFILES and not related_tests:
            errors.append(f"{case_id}: every gold case must include at least one related test")
            bounded_quality_pass = False
        for related in related_tests:
            if not isinstance(related, dict):
                errors.append(f"{case_id}: every related test must be an evidence object")
                bounded_quality_pass = False
                continue
            path = related.get("path")
            evidence_type = related.get("evidence_type")
            if not isinstance(path, str) or not path:
                errors.append(f"{case_id}: every related test must identify a non-empty path")
                bounded_quality_pass = False
            if evidence_type == "changed_test_path":
                if path not in direct:
                    errors.append(f"{case_id}: changed-test evidence must be a direct change")
                    bounded_quality_pass = False
                if related.get("reason") != "changed_path_is_test":
                    errors.append(f"{case_id}: changed-test evidence reason must be changed_path_is_test")
                    bounded_quality_pass = False
                if related.get("provenance_strength") != "direct_diff":
                    errors.append(f"{case_id}: changed-test evidence provenance must be direct_diff")
                    bounded_quality_pass = False
            elif evidence_type == "resolved_query":
                if related.get("provenance_strength") != "resolved_navigation_evidence":
                    errors.append(f"{case_id}: resolved-query test provenance must be resolved_navigation_evidence")
                    bounded_quality_pass = False
                if related.get("current_read_evidence") != "available":
                    errors.append(f"{case_id}: resolved-query test evidence must be currently readable")
                    bounded_quality_pass = False
            else:
                errors.append(f"{case_id}: related test evidence_type must be recognized")
                bounded_quality_pass = False

        if profile in _GOLD_PROFILES and not any(
            isinstance(related, dict)
            and related.get("evidence_type") == "changed_test_path"
            and related.get("provenance_strength") == "direct_diff"
            and related.get("path") in direct
            for related in related_tests
        ):
            errors.append(
                f"{case_id}: every gold case must include direct-diff changed-test evidence"
            )
            bounded_quality_pass = False

        target_symbols = capsule.get("target_symbols")
        if not isinstance(target_symbols, list):
            errors.append(f"{case_id}: target_symbols must be an explicit list")
            target_symbols = []
            bounded_quality_pass = False
        if capsule.get("target_symbols_included") != len(target_symbols):
            errors.append(f"{case_id}: target symbol count must match explicit evidence")
            bounded_quality_pass = False
        for symbol in target_symbols:
            if not isinstance(symbol, dict) or not all(
                isinstance(symbol.get(field), str) and symbol.get(field)
                for field in ("id", "qualified_name", "path", "range_ref")
            ):
                errors.append(f"{case_id}: every target symbol needs bound identity and range")
                bounded_quality_pass = False

        representative_relations = capsule.get("representative_causal_relations")
        if not isinstance(representative_relations, list):
            errors.append(
                f"{case_id}: representative_causal_relations must be an explicit list"
            )
            representative_relations = []
            bounded_quality_pass = False

        gaps = capsule.get("gaps")
        if not isinstance(gaps, list):
            errors.append(f"{case_id}: gaps must be an explicit list")
            gaps = []
            bounded_quality_pass = False
        for gap in gaps:
            if not isinstance(gap, dict) or not isinstance(gap.get("paths"), list):
                errors.append(f"{case_id}: every gap must bind its affected paths")
                bounded_quality_pass = False

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
            byte_accounting_valid = False
        if reported_baseline != baseline_bytes:
            errors.append(f"{case_id}: capsule baseline byte accounting must match paired baseline")
            byte_accounting_valid = False
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
            diff_binding_pass = False
        if capsule.get("freshness_status") != "fresh":
            errors.append(f"{case_id}: RepoGround publication must be fresh")
            freshness_pass = False
        if capsule.get("status") not in {"available", "degraded"}:
            errors.append(f"{case_id}: capsule status must be available or degraded")
            bounded_quality_pass = False

        stop_criteria = capsule.get("stop_criteria")
        if not isinstance(stop_criteria, dict):
            errors.append(f"{case_id}: stop_criteria must be an object")
            stop_criteria = {}
            impact_unblocked_pass = False
        triggered = stop_criteria.get("triggered", [])
        if not isinstance(triggered, list):
            errors.append(f"{case_id}: stop_criteria.triggered must be a list")
            triggered = []
            impact_unblocked_pass = False
        if "impact_context_blocked" in triggered or stop_criteria.get(
            "impact_context_blocked"
        ) is not False:
            errors.append(f"{case_id}: impact_context_blocked must be absent")
            impact_unblocked_pass = False

        overlay = capsule.get("dirty_overlay")
        if not isinstance(overlay, dict):
            errors.append(f"{case_id}: dirty_overlay must be an object")
            overlay_exclusion_pass = False
        elif overlay.get("dirty") is True and overlay.get(
            "included_in_revision_diff"
        ) is not False:
            errors.append(f"{case_id}: dirty overlay must be excluded from revision diff")
            overlay_exclusion_pass = False

        nonclaims = capsule.get("does_not_establish")
        if not isinstance(nonclaims, list) or "completeness" not in nonclaims:
            errors.append(f"{case_id}: capsule must retain the completeness non-claim")
            bounded_quality_pass = False

        lanes = capsule.get("retrieval_lanes")
        if not isinstance(lanes, dict):
            errors.append(f"{case_id}: retrieval_lanes must be an object")
            lanes = {}
            lane_truth_pass = False
        used = lanes.get("used", [])
        skipped = lanes.get("skipped", [])
        if not isinstance(used, list) or not isinstance(skipped, list):
            errors.append(f"{case_id}: retrieval lane lists must be arrays")
            used, skipped = [], []
            lane_truth_pass = False

        call_graph = capsule.get("call_graph_truth")
        if not isinstance(call_graph, dict):
            errors.append(f"{case_id}: call_graph_truth must be an object")
            lane_truth_pass = False
        else:
            if call_graph.get("artifact_available") is not True:
                errors.append(f"{case_id}: call graph artifact must be available")
                lane_truth_pass = False
            if not _is_sha(call_graph.get("artifact_sha256"), _SHA64):
                errors.append(f"{case_id}: call graph artifact SHA must be a SHA-256")
                lane_truth_pass = False
            consumed = call_graph.get("consumed_coherent_evidence")
            coherent_count = call_graph.get("coherent_relation_count")
            if consumed is True:
                if not isinstance(coherent_count, int) or coherent_count <= 0:
                    errors.append(f"{case_id}: consumed call graph needs coherent relation evidence")
                    lane_truth_pass = False
                coherent_relations = [
                    relation
                    for relation in representative_relations
                    if isinstance(relation, dict)
                    and relation.get("source") == "python_call_graph_json"
                    and relation.get("status") == "coherent"
                    and relation.get("artifact_sha256") == call_graph.get("artifact_sha256")
                ]
                if not coherent_relations:
                    errors.append(
                        f"{case_id}: consumed call graph needs explicit coherent relation provenance"
                    )
                    lane_truth_pass = False
                if "call_graph" not in used or "call_graph" in skipped:
                    errors.append(
                        f"{case_id}: consumed call-graph evidence must be explicitly claimed in used retrieval lanes"
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
                errors.append(f"{case_id}: consumed_coherent_evidence must be a boolean")
                lane_truth_pass = False

        if (
            case.get("profile") in _GOLD_PROFILES
            and case.get("quality_pass") is True
            and computed_reduction is not None
            and computed_reduction >= 20.0
        ):
            qualifying.append(case_id)

    mechanical = data.get("mechanical_promotion_gate")
    mechanical_pass = True
    if not isinstance(mechanical, dict):
        errors.append("mechanical_promotion_gate must be an object")
        mechanical_pass = False
    else:
        if mechanical.get("passed") is not True:
            errors.append("mechanical compactness promotion gate must pass")
            mechanical_pass = False
        if mechanical.get("required_count") != 2:
            errors.append("mechanical promotion gate must require two cases")
            mechanical_pass = False
        if sorted(mechanical.get("qualifying_case_ids", [])) != sorted(qualifying):
            errors.append(
                "mechanical promotion qualifying cases do not match recomputed measurements"
            )
            mechanical_pass = False
    if len(qualifying) < 2:
        errors.append("at least two gold cases must reduce context by at least 20 percent")
        mechanical_pass = False

    computed_truth_requirements = {
        "fresh_exact_bundle": source_bundle_pass and freshness_pass,
        "diff_binding_verified_all_cases": diff_binding_pass,
        "impact_context_blocked_absent_all_cases": impact_unblocked_pass,
        "call_graph_lane_matches_consumed_coherent_evidence_all_cases": lane_truth_pass,
        "dirty_overlay_excluded_from_revision_diff_all_cases": overlay_exclusion_pass,
        "paired_baseline_resolved_evidence_all_cases": baseline_evidence_pass,
    }
    computed_truth_gate_pass = all(computed_truth_requirements.values())

    truth_gate = data.get("truth_gate")
    if not isinstance(truth_gate, dict):
        errors.append("truth_gate must be an object")
    else:
        requirements = truth_gate.get("requirements")
        if not isinstance(requirements, dict):
            errors.append("truth_gate.requirements must be an object")
        else:
            for requirement in _REQUIRED_TRUTH_REQUIREMENTS:
                if requirements.get(requirement) is not True:
                    errors.append(f"truth requirement {requirement} must pass")
                if requirements.get(requirement) != computed_truth_requirements[requirement]:
                    errors.append(
                        f"truth requirement {requirement} must match recomputed evidence"
                    )
        if truth_gate.get("passed") is not True:
            errors.append("truth gate must pass")
        if truth_gate.get("passed") != computed_truth_gate_pass:
            errors.append("truth_gate.passed must match recomputed truth gate")
    if not lane_truth_pass:
        errors.append("retrieval lane truth must pass")

    deployment_cases = [
        case
        for case in cases
        if isinstance(case, dict) and case.get("profile") == "deployment_kubernetes"
    ]
    delivery_evidence_pass = True
    delivery = data.get("delivery_chain")
    if not isinstance(delivery, dict):
        errors.append("delivery_chain must be an object")
        delivery_evidence_pass = False
    elif len(deployment_cases) != 1:
        errors.append("exactly one deployment_kubernetes case is required")
        delivery_evidence_pass = False
    else:
        deployment = deployment_cases[0]
        if delivery.get("status") != "pass_bounded":
            errors.append("delivery chain must pass bounded evidence")
            delivery_evidence_pass = False
        if delivery.get("case_id") != deployment.get("id"):
            errors.append("delivery chain must bind to the deployment case")
            delivery_evidence_pass = False
        direct = set(deployment.get("direct_change_paths", []))
        required_direct = delivery.get("required_direct_paths")
        if (
            not isinstance(required_direct, list)
            or not required_direct
            or not all(isinstance(path, str) and path for path in required_direct)
            or not set(required_direct).issubset(direct)
        ):
            errors.append(
                "delivery chain required paths must be a non-empty subset of direct changes"
            )
            delivery_evidence_pass = False
        capsule = deployment.get("capsule", {})
        for field in (
            "target_symbols_included",
            "causal_relations_included",
            "live_ranges_included",
        ):
            value = delivery.get(field)
            if not isinstance(value, int) or value <= 0:
                errors.append(f"delivery chain {field} must be positive")
                delivery_evidence_pass = False
            if value != capsule.get(field):
                errors.append(f"delivery chain {field} must match deployment capsule")
                delivery_evidence_pass = False
        coherent = delivery.get("coherent_call_graph_relation_count")
        call_graph = capsule.get("call_graph_truth", {})
        if not isinstance(coherent, int) or coherent <= 0:
            errors.append("delivery chain needs coherent call-graph relation evidence")
            delivery_evidence_pass = False
        if coherent != call_graph.get("coherent_relation_count"):
            errors.append("delivery call-graph evidence must match deployment capsule")
            delivery_evidence_pass = False
        representative_ranges = capsule.get("representative_live_ranges")
        if not isinstance(representative_ranges, list) or not representative_ranges:
            errors.append("delivery chain needs explicit representative live-range evidence")
            delivery_evidence_pass = False
        elif not any(
            isinstance(item, dict)
            and item.get("path") == "scripts/ops/reconcile-production-main-vps.sh"
            and isinstance(item.get("start_line"), int)
            and isinstance(item.get("end_line"), int)
            and _is_sha(item.get("content_sha256"), _SHA64)
            for item in representative_ranges
        ):
            errors.append("delivery live-range evidence must bind the production reconciler")
            delivery_evidence_pass = False

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
            if contract.get("event") != "push":
                errors.append("delivery contract evidence must come from the post-merge push run")
                delivery_evidence_pass = False
            if not isinstance(contract.get("pr"), int) or contract.get("pr") <= 0:
                errors.append("delivery contract evidence pr must be positive")
                delivery_evidence_pass = False
            for field in ("pr_head_sha", "merge_commit", "run_head_sha"):
                if not _is_sha(contract.get(field), _SHA40):
                    errors.append(f"delivery contract evidence {field} must be a full commit SHA")
                    delivery_evidence_pass = False
            if contract.get("run_head_sha") != contract.get("merge_commit"):
                errors.append("delivery contract run head must equal its merge commit")
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
            expected_events = {
                "required_merge_gate": "pull_request",
                "review_evidence_gate": "pull_request_target",
            }
            for gate_name, expected_event in expected_events.items():
                gate = ci_evidence.get(gate_name)
                if not isinstance(gate, dict) or gate.get("conclusion") != "success":
                    errors.append(f"delivery CI evidence {gate_name} must be successful")
                    delivery_evidence_pass = False
                    continue
                if gate.get("event") != expected_event:
                    errors.append(
                        f"delivery CI evidence {gate_name}.event must be {expected_event}"
                    )
                    delivery_evidence_pass = False
                if not _is_sha(gate.get("head_sha"), _SHA40):
                    errors.append(
                        f"delivery CI evidence {gate_name}.head_sha must be a full commit SHA"
                    )
                    delivery_evidence_pass = False
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
            if not isinstance(deployment_evidence.get("pr"), int) or (
                deployment_evidence.get("pr") <= 0
            ):
                errors.append("deployment evidence pr must be positive")
                delivery_evidence_pass = False
            if not _is_sha(deployment_evidence.get("pr_head_sha"), _SHA40):
                errors.append("deployment evidence pr_head_sha must be a full commit SHA")
                delivery_evidence_pass = False
            if not isinstance(deployment_evidence.get("workflow_run_id"), int) or (
                deployment_evidence.get("workflow_run_id") <= 0
            ):
                errors.append("deployment workflow_run_id must be present")
                delivery_evidence_pass = False

            if isinstance(contract, dict):
                if contract.get("pr") != deployment_evidence.get("pr"):
                    errors.append("contract and deployment evidence must bind the same PR")
                    delivery_evidence_pass = False
                if contract.get("pr_head_sha") != deployment_evidence.get("pr_head_sha"):
                    errors.append("contract and deployment evidence must bind the same PR head")
                    delivery_evidence_pass = False
                if contract.get("merge_commit") != deployment_target:
                    errors.append("contract evidence merge commit must equal deployment target")
                    delivery_evidence_pass = False
                if contract.get("run_head_sha") != deployment_target:
                    errors.append("contract evidence run head must equal deployment target")
                    delivery_evidence_pass = False
                if contract.get("workflow_run_id") != deployment_evidence.get("workflow_run_id"):
                    errors.append("contract evidence must come from the bound deployment run")
                    delivery_evidence_pass = False

            if isinstance(ci_evidence, dict):
                pr_head_sha = deployment_evidence.get("pr_head_sha")
                for gate_name in ("required_merge_gate", "review_evidence_gate"):
                    gate = ci_evidence.get(gate_name)
                    if isinstance(gate, dict) and gate.get("head_sha") != pr_head_sha:
                        errors.append(
                            f"delivery CI evidence {gate_name} must bind the deployment PR head"
                        )
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
            production_receipt = runtime_proof.get("production_receipt")
            if not isinstance(production_receipt, dict):
                errors.append("runtime proof must bind production receipt artifact metadata")
                delivery_evidence_pass = False
            else:
                if not isinstance(production_receipt.get("artifact_id"), int) or (
                    production_receipt.get("artifact_id") <= 0
                ):
                    errors.append("production receipt artifact_id must be positive")
                    delivery_evidence_pass = False
                expected_artifact_name = f"production-live-{deployment.get('target_commit')}"
                if production_receipt.get("artifact_name") != expected_artifact_name:
                    errors.append("production receipt artifact name must bind the deployment target")
                    delivery_evidence_pass = False
                digest = production_receipt.get("artifact_digest")
                if not isinstance(digest, str) or not digest.startswith("sha256:") or not _is_sha(
                    digest.removeprefix("sha256:"), _SHA64
                ):
                    errors.append("production receipt artifact_digest must be a SHA-256 digest")
                    delivery_evidence_pass = False
                if production_receipt.get("bound_commit") != deployment.get("target_commit"):
                    errors.append("production receipt bound_commit must equal deployment target")
                    delivery_evidence_pass = False
                if production_receipt.get("workflow_run_id") != runtime_proof.get("workflow_run_id"):
                    errors.append("production receipt must bind the runtime proof workflow run")
                    delivery_evidence_pass = False
            if not isinstance(runtime_proof.get("job_id"), int) or runtime_proof.get("job_id") <= 0:
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

    computed_evidence_promotion_ready = all(
        (
            three_classes_pass,
            mechanical_pass,
            len(qualifying) >= 2,
            controlled_live_pass,
            source_bundle_pass,
            measurement_worktree_pass,
            observed_overlay_pass,
            bounded_quality_pass,
            baseline_evidence_pass,
            freshness_pass,
            diff_binding_pass,
            impact_unblocked_pass,
            lane_truth_pass,
            computed_truth_gate_pass,
            delivery_evidence_pass,
        )
    )

    computed_acceptance = {
        "three_classes": "pass" if three_classes_pass else "fail",
        "paired_baseline": "pass" if baseline_evidence_pass else "fail",
        "quality": "pass_bounded" if bounded_quality_pass else "fail",
        "retrieval_lane_truth": "pass" if lane_truth_pass else "fail",
        "freshness_and_diff_binding": (
            "pass" if freshness_pass and diff_binding_pass else "fail"
        ),
        "delivery_chain": "pass_bounded" if delivery_evidence_pass else "blocked",
        "promotion_gate": "pass" if computed_evidence_promotion_ready else "blocked",
    }

    acceptance = data.get("acceptance")
    if not isinstance(acceptance, dict):
        errors.append("acceptance must be an object")
    else:
        for field, expected in _REQUIRED_ACCEPTANCE.items():
            if acceptance.get(field) != expected:
                errors.append(f"acceptance.{field} must be {expected}")
            if acceptance.get(field) != computed_acceptance[field]:
                errors.append(f"acceptance.{field} must match recomputed evidence")

    # Every validation error above is promotion-blocking.  The individual booleans
    # make the decision explainable; ``not errors`` prevents logical drift where a
    # newly-added blocking check forgets to update one of those booleans.
    promotion_ready = computed_evidence_promotion_ready and not errors
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
