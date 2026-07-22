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
_ALLOWED_RELATED_TEST_EVIDENCE = {
    "graph_edge",
    "symbol_index_path_match",
    "resolved_query",
}
_ALLOWED_CAPSULE_STATUSES = {"available", "degraded"}
_ALLOWED_TRIGGERED_STOPS = {"budget_exhausted"}
_REQUIRED_DELIVERY_GAPS = {
    "contracts",
    "runtime_proof",
    "rollback_risks",
}


def _is_sha(value: Any, pattern: re.Pattern[str]) -> bool:
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("schema_version") != 2:
        errors.append("schema_version must be 2")
    if data.get("repo") != "weltgewebe":
        errors.append("repo must be weltgewebe")
    if data.get("task_profile") != "change_impact":
        errors.append("task_profile must be change_impact")
    if not _is_sha(data.get("grabowski_runtime_commit"), _SHA40):
        errors.append("grabowski_runtime_commit must be a full commit SHA")
    if not _is_sha(data.get("measurement_source_sha256"), _SHA64):
        errors.append("measurement_source_sha256 must be a SHA-256")

    source_bundle = data.get("source_bundle")
    if not isinstance(source_bundle, dict):
        errors.append("source_bundle must be an object")
        source_bundle = {}
    if source_bundle.get("freshness") != "fresh_exact":
        errors.append("source bundle must be fresh_exact")
    for field in ("git_commit", "generator_runtime_commit"):
        if not _is_sha(source_bundle.get(field), _SHA40):
            errors.append(f"source_bundle.{field} must be a full commit SHA")
    if not _is_sha(source_bundle.get("manifest_sha256"), _SHA64):
        errors.append("source_bundle.manifest_sha256 must be a SHA-256")

    cases = data.get("cases")
    if not isinstance(cases, list) or len(cases) != 4:
        errors.append("exactly four pilot cases are required")
        return errors

    profiles = {case.get("profile") for case in cases if isinstance(case, dict)}
    if not _GOLD_PROFILES.issubset(profiles):
        errors.append("database_auth, web_map and deployment_kubernetes gold cases are required")
    if "controlled_live" not in profiles:
        errors.append("one controlled_live case is required")

    qualifying: list[str] = []
    artifact_too_large_case_ids: list[str] = []
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
        if not _is_sha(case.get("diff_sha256"), _SHA64):
            errors.append(f"{case_id}: diff_sha256 must be a SHA-256")

        expected = case.get("expected_critical_paths")
        direct = case.get("direct_change_paths")
        missing = case.get("missing_critical_paths")
        if not isinstance(expected, list) or not expected:
            errors.append(f"{case_id}: expected_critical_paths must be non-empty")
        if not isinstance(direct, list):
            errors.append(f"{case_id}: direct_change_paths must be a list")
            direct = []
        if not isinstance(missing, list) or missing:
            errors.append(f"{case_id}: critical-path coverage must have no missing paths")
        if case.get("critical_path_coverage") != 1.0:
            errors.append(f"{case_id}: critical_path_coverage must be 1.0")
        if isinstance(expected, list) and not set(expected).issubset(set(direct)):
            errors.append(f"{case_id}: expected critical paths are not all direct changes")

        baseline = case.get("baseline")
        capsule = case.get("capsule")
        if not isinstance(baseline, dict) or not isinstance(capsule, dict):
            errors.append(f"{case_id}: baseline and capsule must be objects")
            continue
        if baseline.get("available") is not True:
            errors.append(f"{case_id}: paired baseline must be available")
        if capsule.get("available") is not True:
            errors.append(f"{case_id}: capsule must be available")
        if capsule.get("status") not in _ALLOWED_CAPSULE_STATUSES:
            errors.append(f"{case_id}: capsule status must be available or degraded")

        baseline_bytes = baseline.get("payload_bytes")
        context_bytes = capsule.get("context_bytes")
        byte_accounting_valid = (
            isinstance(baseline_bytes, int)
            and not isinstance(baseline_bytes, bool)
            and baseline_bytes > 0
            and isinstance(context_bytes, int)
            and not isinstance(context_bytes, bool)
            and context_bytes > 0
        )
        if not isinstance(baseline_bytes, int) or isinstance(baseline_bytes, bool) or baseline_bytes <= 0:
            errors.append(f"{case_id}: baseline payload_bytes must be positive")
        if not isinstance(context_bytes, int) or isinstance(context_bytes, bool) or context_bytes <= 0:
            errors.append(f"{case_id}: capsule context_bytes must be positive")
        if capsule.get("general_context_pack_bytes_reported") != baseline_bytes:
            errors.append(f"{case_id}: capsule baseline byte accounting must match paired baseline")

        computed_reduction: float | None = None
        if byte_accounting_valid:
            assert isinstance(baseline_bytes, int)
            assert isinstance(context_bytes, int)
            computed_ratio = round(context_bytes / baseline_bytes, 6)
            computed_reduction = round((1 - computed_ratio) * 100, 3)
            if capsule.get("ratio") != computed_ratio:
                errors.append(f"{case_id}: capsule ratio must match byte accounting")
            if capsule.get("reduction_pct") != computed_reduction:
                errors.append(f"{case_id}: capsule reduction_pct must match byte accounting")

        if capsule.get("diff_binding_verified") is not True:
            errors.append(f"{case_id}: diff binding must be verified")
        if capsule.get("freshness_status") != "fresh":
            errors.append(f"{case_id}: RepoGround publication must be fresh")
        if case.get("quality_pass") is not True:
            errors.append(f"{case_id}: bounded quality check must pass")

        nonclaims = capsule.get("does_not_establish")
        if not isinstance(nonclaims, list) or "completeness" not in nonclaims:
            errors.append(f"{case_id}: capsule must retain the completeness non-claim")

        gaps = capsule.get("gaps")
        gap_text = json.dumps(gaps, sort_keys=True)
        has_large_artifact_gap = capsule.get("artifact_too_large_present") is True or "artifact_too_large" in gap_text
        if has_large_artifact_gap:
            artifact_too_large_case_ids.append(case_id)
            errors.append(f"{case_id}: artifact_too_large must be absent after T007")

        if capsule.get("heuristic_related_test_count") != 0:
            errors.append(f"{case_id}: heuristic related tests must be zero")
        related_tests = capsule.get("related_tests")
        if not isinstance(related_tests, list):
            errors.append(f"{case_id}: related_tests must be a list")
        else:
            for item in related_tests:
                if not isinstance(item, dict) or item.get("evidence_type") not in _ALLOWED_RELATED_TEST_EVIDENCE:
                    errors.append(f"{case_id}: every related test must carry accepted evidence")
                    break

        stop_criteria = capsule.get("stop_criteria")
        if not isinstance(stop_criteria, dict):
            errors.append(f"{case_id}: stop_criteria must be an object")
        else:
            triggered = stop_criteria.get("triggered")
            if not isinstance(triggered, list):
                errors.append(f"{case_id}: triggered stop criteria must be a list")
            else:
                unexpected = set(triggered) - _ALLOWED_TRIGGERED_STOPS
                if unexpected:
                    errors.append(f"{case_id}: unexpected stop criteria triggered: {sorted(unexpected)}")

        if case.get("profile") == "deployment_kubernetes":
            target_symbol_count = capsule.get("target_symbol_count")
            if not isinstance(target_symbol_count, int) or target_symbol_count <= 0:
                errors.append(f"{case_id}: Kubernetes gold case must expose target symbols")

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
            errors.append("mechanical promotion qualifying cases do not match recomputed measurements")
    if len(qualifying) < 2:
        errors.append("at least two gold cases must reduce context by at least 20 percent")

    call_graph_access = data.get("call_graph_access")
    if not isinstance(call_graph_access, dict):
        errors.append("call_graph_access must be an object")
    else:
        artifact_bytes = call_graph_access.get("artifact_bytes")
        legacy_limit = call_graph_access.get("legacy_readonly_limit_bytes")
        if call_graph_access.get("artifact_role") != "python_call_graph_json":
            errors.append("call_graph_access must describe python_call_graph_json")
        if not _is_sha(call_graph_access.get("artifact_sha256"), _SHA64):
            errors.append("call_graph_access.artifact_sha256 must be a SHA-256")
        if not isinstance(artifact_bytes, int) or not isinstance(legacy_limit, int):
            errors.append("call graph size and legacy read limit must be integers")
        elif artifact_bytes <= legacy_limit:
            errors.append("T007 proof requires a call graph larger than the legacy read limit")
        elif call_graph_access.get("over_limit_bytes") != artifact_bytes - legacy_limit:
            errors.append("call graph over_limit_bytes is inconsistent")
        if call_graph_access.get("bounded_access_status") != "pass":
            errors.append("bounded call graph access must pass")
        if call_graph_access.get("artifact_too_large_case_ids") != artifact_too_large_case_ids:
            errors.append("call graph artifact_too_large case list must match measured cases")
        if artifact_too_large_case_ids:
            errors.append("post-T007 pilot must have no artifact_too_large cases")

    live_cases = [case for case in cases if case.get("profile") == "controlled_live"]
    if len(live_cases) != 1:
        errors.append("exactly one controlled_live case is required")
    elif live_cases[0].get("target_commit") != source_bundle.get("git_commit"):
        errors.append("controlled_live target must equal the fresh source bundle commit")

    delivery = data.get("delivery_chain_assessment")
    if not isinstance(delivery, dict):
        errors.append("delivery_chain_assessment must be an object")
    else:
        if delivery.get("status") != "blocked":
            errors.append("delivery chain must remain blocked until all required evidence is established")
        if delivery.get("repo_runtime_separation") != "pass":
            errors.append("repository and runtime truth must remain explicitly separated")
        missing_delivery = delivery.get("missing")
        if not isinstance(missing_delivery, dict):
            errors.append("delivery chain missing evidence must be an object")
        else:
            if not _REQUIRED_DELIVERY_GAPS.issubset(missing_delivery):
                errors.append("delivery chain must name contracts, runtime_proof and rollback_risks gaps")
            for key in _REQUIRED_DELIVERY_GAPS:
                if missing_delivery.get(key) != "not_established_by_capsule":
                    errors.append(f"delivery chain gap {key} must remain not_established_by_capsule")

    acceptance = data.get("acceptance")
    if not isinstance(acceptance, dict):
        errors.append("acceptance must be an object")
    else:
        for key in ("three_classes", "paired_baseline", "quality", "promotion_gate"):
            if acceptance.get(key) != "pass":
                errors.append(f"acceptance.{key} must be pass")
        if acceptance.get("delivery") != "not_established_by_fixture":
            errors.append("acceptance.delivery must remain not_established_by_fixture")
        if acceptance.get("delivery_chain") != "blocked_missing_contract_runtime_rollback_evidence":
            errors.append("delivery_chain acceptance must retain the narrowed post-T007 blocker")

    if data.get("overall_status") != "blocked":
        errors.append("overall_status must remain blocked until the delivery chain is proven")
    if data.get("promotion_recommendation") != "withhold_default_promotion":
        errors.append("default promotion must remain withheld")

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
