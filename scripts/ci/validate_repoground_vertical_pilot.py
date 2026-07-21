from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVIDENCE = (
    ROOT / "scripts/ci/fixtures/repoground_vertical_pilot.v1.json"
)
_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA64 = re.compile(r"[0-9a-f]{64}\Z")
_GOLD_PROFILES = {"database_auth", "web_map", "deployment_kubernetes"}


def _is_sha(value: Any, pattern: re.Pattern[str]) -> bool:
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def validate(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if data.get("repo") != "weltgewebe":
        errors.append("repo must be weltgewebe")
    if data.get("task_profile") != "change_impact":
        errors.append("task_profile must be change_impact")
    if not _is_sha(data.get("grabowski_runtime_commit"), _SHA40):
        errors.append("grabowski_runtime_commit must be a full commit SHA")

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
        baseline_bytes = baseline.get("payload_bytes")
        context_bytes = capsule.get("context_bytes")
        reported_baseline = capsule.get("general_context_pack_bytes_reported")
        if not isinstance(baseline_bytes, int) or baseline_bytes <= 0:
            errors.append(f"{case_id}: baseline payload_bytes must be positive")
        if reported_baseline != baseline_bytes:
            errors.append(f"{case_id}: capsule baseline byte accounting must match paired baseline")
        if not isinstance(context_bytes, int) or context_bytes <= 0:
            errors.append(f"{case_id}: capsule context_bytes must be positive")
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
        if "python_call_graph_json" not in gap_text or "artifact_too_large" not in gap_text:
            errors.append(f"{case_id}: oversized call-graph gap must remain explicit")
        if capsule.get("status") != "degraded":
            errors.append(f"{case_id}: current evidence expects degraded capsule status")

        reduction = capsule.get("reduction_pct")
        if (
            case.get("profile") in _GOLD_PROFILES
            and case.get("quality_pass") is True
            and isinstance(reduction, (int, float))
            and reduction >= 20.0
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
            errors.append("mechanical promotion qualifying cases do not match measurements")
    if len(qualifying) < 2:
        errors.append("at least two gold cases must reduce context by at least 20 percent")

    blocker = data.get("call_graph_blocker")
    if not isinstance(blocker, dict):
        errors.append("call_graph_blocker must be an object")
    else:
        artifact_bytes = blocker.get("artifact_bytes")
        max_bytes = blocker.get("readonly_adapter_max_bytes")
        if not isinstance(artifact_bytes, int) or not isinstance(max_bytes, int):
            errors.append("call graph size and adapter limit must be integers")
        elif artifact_bytes <= max_bytes:
            errors.append("call graph blocker requires artifact_bytes above the safe adapter limit")
        elif blocker.get("over_limit_bytes") != artifact_bytes - max_bytes:
            errors.append("call graph over_limit_bytes is inconsistent")
        if blocker.get("error_code") != "artifact_too_large":
            errors.append("call graph blocker must preserve artifact_too_large")

    live_cases = [case for case in cases if case.get("profile") == "controlled_live"]
    if len(live_cases) != 1:
        errors.append("exactly one controlled_live case is required")
    elif live_cases[0].get("target_commit") != source_bundle.get("git_commit"):
        errors.append("controlled_live target must equal the fresh source bundle commit")

    acceptance = data.get("acceptance")
    if not isinstance(acceptance, dict):
        errors.append("acceptance must be an object")
    else:
        if acceptance.get("delivery_chain") != "blocked_call_graph_artifact_too_large":
            errors.append("delivery_chain must remain blocked on the oversized call graph")
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
