"""Regression tests for the Weltgewebe convergence adapter contract."""

from __future__ import annotations

import copy
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock


ROOT = Path(__file__).resolve().parents[3]
CONTRACT_ROOT = ROOT / "contracts/convergence/v1.0.0"
FIXTURE_ROOT = CONTRACT_ROOT / "fixtures"
ADAPTER_PATH = ROOT / "scripts/convergence/weltgewebe_convergence_adapter.py"
DOC_PATH = ROOT / "docs/architecture/weltgewebe-os-convergence-adapter.md"
PROTOCOL_ROOT_ENV = "KONVERGENZREGELKREIS_ROOT"
PROTOCOL_ROOT_VALUE = os.environ.get(PROTOCOL_ROOT_ENV)
PROTOCOL_ROOT = Path(PROTOCOL_ROOT_VALUE) if PROTOCOL_ROOT_VALUE else None
PROTOCOL_HEAD_FILE = CONTRACT_ROOT / "PINNED_PROTOCOL_HEAD"
PROTOCOL_HEAD = PROTOCOL_HEAD_FILE.read_text(encoding="utf-8").strip()
CANONICAL_REQUEST_KEYS = {
    "schema_version",
    "assessment_id",
    "risk_level",
    "observation",
    "classification",
    "effects",
    "verifications",
    "closure",
}


def load_adapter() -> Any:
    spec = importlib.util.spec_from_file_location("weltgewebe_convergence_adapter", ADAPTER_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load convergence adapter module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_protocol_core() -> Any:
    if PROTOCOL_ROOT is None:
        raise unittest.SkipTest(
            f"set {PROTOCOL_ROOT_ENV} to run pinned protocol integration tests"
        )
    if not PROTOCOL_ROOT.exists():
        raise AssertionError(f"required protocol checkout not present at {PROTOCOL_ROOT}")
    head = subprocess.run(
        ["git", "-C", str(PROTOCOL_ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if head != PROTOCOL_HEAD:
        raise AssertionError(f"protocol checkout head {head} != {PROTOCOL_HEAD}")
    sys.path.insert(0, str(PROTOCOL_ROOT / "src"))
    from regelkreis import core

    return core


def collect_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        keys = set(value)
        for child in value.values():
            keys.update(collect_keys(child))
        return keys
    if isinstance(value, list):
        keys: set[str] = set()
        for child in value:
            keys.update(collect_keys(child))
        return keys
    return set()


def make_live_profile(profile: dict[str, Any]) -> dict[str, Any]:
    def strip_fixture_prefix(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: strip_fixture_prefix(child) for key, child in value.items()}
        if isinstance(value, list):
            return [strip_fixture_prefix(child) for child in value]
        if isinstance(value, str) and value.startswith("fixture:"):
            return value.removeprefix("fixture:")
        return value

    live = strip_fixture_prefix(profile)
    live["evidence_mode"] = "live"
    return live


class ConvergenceAdapterContractTests(unittest.TestCase):
    """Base class for tests."""
    @classmethod
    def setUpClass(cls) -> None:
        cls.adapter = load_adapter()
        try:
            cls.protocol_core = load_protocol_core()
        except unittest.SkipTest:
            cls.protocol_core = None

    # === SECTION: Schema and Protocol Core Rules ===

    def test_only_profile_schema_is_local_truth(self) -> None:
        self.assertTrue((CONTRACT_ROOT / "assessment-profile.schema.json").exists())
        self.assertFalse((CONTRACT_ROOT / ("assessment-" + "request.schema.json")).exists())
        self.assertFalse((CONTRACT_ROOT / ("evidence-" + "reference.schema.json")).exists())

        schema = read_json(CONTRACT_ROOT / "assessment-profile.schema.json")
        profile = read_json(FIXTURE_ROOT / "conformance.terminal.profile.json")
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(set(schema["required"]), set(profile))
        self.assertFalse(schema["additionalProperties"])
        self.adapter.validate_profile(profile)
        self.assertEqual(schema["properties"]["protocol_head"]["const"], PROTOCOL_HEAD)
        request_description = schema["properties"]["request"]["description"]
        self.assertIn("defensive mirror", request_description)
        self.assertIn("CI compares", request_description)
        self.assertNotIn("adapter and tests validate it against", request_description)
        self.assertNotIn("risk" + "_class", json.dumps(schema, sort_keys=True))

    def test_defensive_mirror_matches_pinned_protocol(self) -> None:
        if self.protocol_core is None:
            self.skipTest("pinned konvergenzregelkreis checkout not available")

        protocol = PROTOCOL_ROOT / "protocol"
        request_schema = read_json(protocol / "assessment-request.v1.schema.json")
        observation_schema = read_json(protocol / "observation.v1.schema.json")
        classification_schema = read_json(protocol / "classification.v1.schema.json")
        effect_schema = read_json(protocol / "effect-receipt.v1.schema.json")
        verification_schema = read_json(protocol / "verification-receipt.v1.schema.json")
        closure_schema = read_json(protocol / "closure-receipt.v1.schema.json")
        r2_profile = read_json(PROTOCOL_ROOT / "profiles/R2.v1.json")

        self.assertEqual(self.adapter.REQUEST_REQUIRED_KEYS, set(request_schema["required"]))
        self.assertEqual(self.adapter.REQUEST_ALLOWED_KEYS, set(request_schema["properties"]))
        self.assertEqual(self.adapter.OBSERVATION_KEYS, set(observation_schema["properties"]))
        self.assertEqual(self.adapter.OBSERVATION_KEYS, set(observation_schema["required"]))
        source_ref_schema = observation_schema["properties"]["source_refs"]["items"]
        self.assertEqual(self.adapter.SOURCE_REF_KEYS, set(source_ref_schema["properties"]))
        self.assertEqual(self.adapter.SOURCE_REF_KEYS, set(source_ref_schema["required"]))
        self.assertEqual(
            {"current", "stale", "unknown"},
            set(observation_schema["properties"]["source_state"]["enum"]),
        )
        self.assertEqual(
            {"R0", "R1", "R2", "R3"},
            set(request_schema["properties"]["risk_level"]["enum"]),
        )
        self.assertEqual(
            self.adapter.CLASSIFICATION_KEYS, set(classification_schema["properties"])
        )
        self.assertEqual(
            self.adapter.CLASSIFICATION_KEYS, set(classification_schema["required"])
        )
        self.assertEqual(self.adapter.EFFECT_KEYS, set(effect_schema["properties"]))
        self.assertEqual(self.adapter.EFFECT_KEYS, set(effect_schema["required"]))
        self.assertEqual(
            self.adapter.VERIFICATION_KEYS, set(verification_schema["properties"])
        )
        self.assertEqual(
            self.adapter.VERIFICATION_KEYS, set(verification_schema["required"])
        )
        self.assertEqual(
            self.adapter.CLOSURE_PROTOCOL_REQUIRED_KEYS, set(closure_schema["required"])
        )
        self.assertEqual(self.adapter.CLOSURE_ALLOWED_KEYS, set(closure_schema["properties"]))
        self.assertEqual(
            {"proposed", "closed"},
            set(closure_schema["properties"]["status"]["enum"]),
        )
        self.assertEqual(
            self.adapter.CHANGE_CLASSES,
            set(classification_schema["properties"]["change_class"]["enum"]),
        )
        self.assertEqual(
            self.adapter.SEMANTIC_CHANGES,
            set(classification_schema["properties"]["semantic_change"]["enum"]),
        )
        self.assertEqual(
            self.adapter.EFFECT_KINDS, set(effect_schema["properties"]["kind"]["enum"])
        )
        self.assertEqual(
            self.adapter.VERIFICATION_KINDS,
            set(verification_schema["properties"]["kind"]["enum"]),
        )
        self.assertEqual(
            self.adapter.VERIFICATION_RESULTS,
            set(verification_schema["properties"]["result"]["enum"]),
        )
        self.assertEqual(
            self.adapter.R2_REQUIRED_EFFECT_KINDS, set(r2_profile["required_effects"])
        )
        self.assertEqual(
            self.adapter.R2_REQUIRED_VERIFICATION_KINDS,
            set(r2_profile["required_verifications"]),
        )
        self.assertEqual(
            self.adapter.R2_REQUIRED_CLOSURE_FIELDS,
            set(r2_profile["required_closure_fields"]),
        )

    def test_conformance_profile_generates_exact_public_request(self) -> None:
        profile = read_json(FIXTURE_ROOT / "conformance.terminal.profile.json")
        expected = profile["request"]
        request, request_sha256, profile_sha256 = self.adapter.build_request(profile)

        self.assertEqual(request, expected)
        request["assessment_id"] = "mutated-return-value"
        self.assertEqual(
            profile["request"]["assessment_id"],
            "weltgewebe-os-v1-t013-conformance-fixture",
        )
        request = expected
        self.assertEqual(set(request), CANONICAL_REQUEST_KEYS)
        self.assertEqual(request["schema_version"], 1)
        self.assertEqual(request["risk_level"], "R2")
        self.assertNotIn("protocol_head", request)
        self.assertNotIn("request" + "_type", request)
        self.assertEqual(
            request_sha256,
            self.adapter.sha256_hex(self.adapter.canonical_json(request)),
        )
        self.assertRegex(profile_sha256, r"^[0-9a-f]{64}$")

    def test_request_maps_required_external_references(self) -> None:
        request, _, _ = self.adapter.build_request_from_path(
            FIXTURE_ROOT / "conformance.terminal.profile.json"
        )
        source_kinds = {item["kind"] for item in request["observation"]["source_refs"]}
        self.assertGreaterEqual(
            source_kinds,
            {"bureau_task", "chronik_event", "grabowski_live_receipt", "git_commit"},
        )
        effect_kinds = {item["kind"] for item in request["effects"]}
        self.assertGreaterEqual(effect_kinds, {"merge", "deployment"})
        verification_kinds = {item["kind"] for item in request["verifications"]}
        self.assertIn("negative_control", verification_kinds)
        self.assertIn("recovery", verification_kinds)
        self.assertEqual(
            request["closure"]["bureau_task_ref"],
            "fixture:bureau-task:WELTGEWEBE-OS-V1-T013",
        )
        self.assertEqual(
            request["closure"]["chronik_event_ref"],
            "fixture:chronik-event:WELTGEWEBE-OS-V1-T013",
        )
        self.assertEqual(
            request["closure"]["residual_risks"],
            ["fixture:residual-risk:rollback-execution-remains-external-to-read-only-adapter"],
        )

    def test_protocol_evaluator_accepts_conformance_request(self) -> None:
        if self.protocol_core is None:
            self.skipTest("pinned konvergenzregelkreis checkout not available")
        request, _, _ = self.adapter.build_request_from_path(
            FIXTURE_ROOT / "conformance.terminal.profile.json"
        )
        result = self.protocol_core.evaluate(request, PROTOCOL_ROOT)
        self.assertEqual(result["schema_version"], 1)
        self.assertEqual(result["risk_level"], "R2")
        self.assertEqual(result["status"], "terminally_closed")
        self.assertEqual(result["missing_evidence"], [])
        self.assertEqual(result["conflicts"], [])
        self.assertEqual(result["blocked_by"], [])

    def test_protocol_evaluator_blocks_missing_and_conflicting_requests(self) -> None:
        if self.protocol_core is None:
            self.skipTest("pinned konvergenzregelkreis checkout not available")
        request = read_json(FIXTURE_ROOT / "conformance.terminal.profile.json")["request"]

        missing = copy.deepcopy(request)
        missing["verifications"] = [
            item for item in missing["verifications"] if item["kind"] != "negative_control"
        ]
        missing_result = self.protocol_core.evaluate(missing, PROTOCOL_ROOT)
        self.assertEqual(missing_result["status"], "evidence_missing")
        self.assertIn("verification:negative_control", missing_result["missing_evidence"])

        conflicting = copy.deepcopy(request)
        extra_deployment = copy.deepcopy(conflicting["effects"][1])
        extra_deployment["subject_sha256"] = (
            "9999999999999999999999999999999999999999999999999999999999999999"
        )
        conflicting["effects"].append(extra_deployment)
        conflict_result = self.protocol_core.evaluate(conflicting, PROTOCOL_ROOT)
        self.assertEqual(conflict_result["status"], "conflicting_evidence")
        self.assertEqual(conflict_result["conflicts"], ["effect:deployment:subject_sha256"])

    def test_protocol_rejects_unknown_request_fields(self) -> None:
        if self.protocol_core is None:
            self.skipTest("pinned konvergenzregelkreis checkout not available")
        request = read_json(FIXTURE_ROOT / "conformance.terminal.profile.json")["request"]
        request["protocol_head"] = PROTOCOL_HEAD
        with self.assertRaises(self.protocol_core.ContractValidationError):
            self.protocol_core.validate_request(PROTOCOL_ROOT, request)

    # === SECTION: CLI and Output Generation ===

    def test_cli_main_emits_adapter_envelope_metadata_without_changing_request(self) -> None:
        expected_request = read_json(FIXTURE_ROOT / "conformance.terminal.profile.json")["request"]
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.object(
            self.adapter, "load_profile", wraps=self.adapter.load_profile
        ) as load_profile:
            rc = self.adapter.main(
                [str(FIXTURE_ROOT / "conformance.terminal.profile.json")],
                stdout=stdout,
                stderr=stderr,
            )
        self.assertEqual(load_profile.call_count, 1)
        self.assertEqual(rc, 0)
        self.assertEqual(stderr.getvalue(), "")
        envelope = json.loads(stdout.getvalue())
        self.assertEqual(
            set(envelope),
            {
                "schema_version",
                "adapter",
                "adapter_version",
                "profile_id",
                "evidence_mode",
                "profile_sha256",
                "intent_sha256",
                "protocol_head",
                "request",
                "request_sha256",
            },
        )
        self.assertEqual(envelope["protocol_head"], PROTOCOL_HEAD)
        self.assertEqual(envelope["adapter"], "weltgewebe-os-convergence-adapter")
        self.assertEqual(envelope["adapter_version"], "1.0.0")
        self.assertEqual(envelope["evidence_mode"], "synthetic_fixture")
        self.assertEqual(envelope["request"], expected_request)
        self.assertEqual(
            envelope["intent_sha256"],
            self.adapter.sha256_hex(
                self.adapter.canonical_json(
                    read_json(FIXTURE_ROOT / "conformance.terminal.profile.json")["intent"]
                )
            ),
        )
        self.assertNotIn("protocol_head", envelope["request"])

        stdout = io.StringIO()
        stderr = io.StringIO()
        rc = self.adapter.main(
            [str(FIXTURE_ROOT / "conformance.terminal.profile.json"), "--output", "request"],
            stdout=stdout,
            stderr=stderr,
        )
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(stdout.getvalue()), expected_request)

        stdout = io.StringIO()
        stderr = io.StringIO()
        rc = self.adapter.main(
            [str(FIXTURE_ROOT / "conformance.terminal.profile.json"), "--output", "hash"],
            stdout=stdout,
            stderr=stderr,
        )
        self.assertEqual(rc, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(
            stdout.getvalue().strip(),
            self.adapter.sha256_hex(self.adapter.canonical_json(expected_request)),
        )

    # === SECTION: Evidence Reference and Shape Validation ===

    def test_adapter_rejects_profile_payloads_symbolic_revisions_and_missing_controls(self) -> None:
        profile = read_json(FIXTURE_ROOT / "conformance.terminal.profile.json")

        with self.subTest("domain payload"):
            invalid = copy.deepcopy(profile)
            invalid["request"]["observation"]["source_refs"][0]["domain_payload"] = {
                "copied": "forbidden"
            }
            with self.assertRaises(self.adapter.ConvergenceAdapterError):
                self.adapter.build_request(invalid)

        with self.subTest("symbolic revision replaces exact commit"):
            invalid = copy.deepcopy(profile)
            invalid["request"]["observation"]["source_refs"][3]["ref"] = (
                "fixture:git:weltgewebe@main"
            )
            with self.assertRaises(self.adapter.ConvergenceAdapterError):
                self.adapter.build_request(invalid)

        with self.subTest("symbolic revision beside exact commit"):
            invalid = copy.deepcopy(profile)
            symbolic = copy.deepcopy(invalid["request"]["observation"]["source_refs"][3])
            symbolic["ref"] = "fixture:git:weltgewebe@main"
            invalid["request"]["observation"]["source_refs"].append(symbolic)
            with self.assertRaises(self.adapter.ConvergenceAdapterError):
                self.adapter.build_request(invalid)

        symbolic_evidence_mutations: list[tuple[str, Any]] = [
            (
                "symbolic effect evidence",
                lambda candidate: candidate["request"]["effects"][0].__setitem__(
                    "evidence_ref", "fixture:git-merge:weltgewebe@main"
                ),
            ),
            (
                "symbolic verification evidence",
                lambda candidate: candidate["request"]["verifications"][0].__setitem__(
                    "evidence_ref", "fixture:git:weltgewebe@main"
                ),
            ),
            (
                "symbolic cleanup evidence",
                lambda candidate: candidate["request"]["closure"][
                    "cleanup_evidence"
                ].__setitem__(0, "fixture:git:weltgewebe@main"),
            ),
            (
                "symbolic residual risk reference",
                lambda candidate: candidate["request"]["closure"][
                    "residual_risks"
                ].__setitem__(0, "fixture:git:weltgewebe@main"),
            ),
        ]
        for name, mutate in symbolic_evidence_mutations:
            with self.subTest(name):
                invalid = copy.deepcopy(profile)
                mutate(invalid)
                with self.assertRaises(self.adapter.ConvergenceAdapterError):
                    self.adapter.build_request(invalid)

        with self.subTest("missing R2 CI verification"):
            invalid = copy.deepcopy(profile)
            invalid["request"]["verifications"] = [
                item for item in invalid["request"]["verifications"] if item["kind"] != "ci"
            ]
            with self.assertRaises(self.adapter.ConvergenceAdapterError):
                self.adapter.build_request(invalid)

        with self.subTest("missing required closure reference"):
            invalid = copy.deepcopy(profile)
            invalid["request"]["closure"].pop("bureau_task_ref")
            with self.assertRaises(self.adapter.ConvergenceAdapterError):
                self.adapter.build_request(invalid)

        with self.subTest("missing rollback"):
            invalid = copy.deepcopy(profile)
            invalid["request"]["verifications"] = [
                item for item in invalid["request"]["verifications"] if item["kind"] != "recovery"
            ]
            with self.assertRaises(self.adapter.ConvergenceAdapterError):
                self.adapter.build_request(invalid)

        with self.subTest("missing negative control"):
            invalid = copy.deepcopy(profile)
            invalid["request"]["verifications"] = [
                item
                for item in invalid["request"]["verifications"]
                if item["kind"] != "negative_control"
            ]
            with self.assertRaises(self.adapter.ConvergenceAdapterError):
                self.adapter.build_request(invalid)

    def test_git_evidence_urls_require_exact_commits(self) -> None:
        base = read_json(FIXTURE_ROOT / "conformance.terminal.profile.json")
        exact = "0123456789abcdef0123456789abcdef01234567"
        other = "89abcdef0123456789abcdef0123456789abcdef"

        rejected: list[tuple[str, Any]] = [
            (
                "github pr with commits subpath",
                lambda candidate: candidate["request"]["effects"][0].__setitem__(
                    "evidence_ref",
                    "https://github.com/heimgewebe/weltgewebe/pull/1451/commits/abcdef123",
                ),
            ),
            (
                "github lookalike host prefix",
                lambda candidate: candidate["request"]["effects"][0].__setitem__(
                    "evidence_ref",
                    "https://evilgithub.com/heimgewebe/weltgewebe/pull/1451",
                ),
            ),
            (
                "github lookalike host suffix",
                lambda candidate: candidate["request"]["effects"][0].__setitem__(
                    "evidence_ref",
                    "https://github.com.evil/heimgewebe/weltgewebe/pull/1451",
                ),
            ),
            (
                "github userinfo",
                lambda candidate: candidate["request"]["effects"][0].__setitem__(
                    "evidence_ref",
                    "https://user@github.com/heimgewebe/weltgewebe/pull/1451",
                ),
            ),
            (
                "github explicit port",
                lambda candidate: candidate["request"]["effects"][0].__setitem__(
                    "evidence_ref",
                    "https://github.com:443/heimgewebe/weltgewebe/pull/1451",
                ),
            ),
            (
                "github query",
                lambda candidate: candidate["request"]["effects"][0].__setitem__(
                    "evidence_ref",
                    "https://github.com/heimgewebe/weltgewebe/pull/1451?diff=split",
                ),
            ),
            (
                "github fragment",
                lambda candidate: candidate["request"]["effects"][0].__setitem__(
                    "evidence_ref",
                    "https://github.com/heimgewebe/weltgewebe/pull/1451#discussion",
                ),
            ),
            (
                "github percent-encoded pull path",
                lambda candidate: candidate["request"]["effects"][0].__setitem__(
                    "evidence_ref",
                    "https://github.com/heimgewebe/weltgewebe%2Fpull%2F1451",
                ),
            ),
            (
                "github double-encoded pull path",
                lambda candidate: candidate["request"]["effects"][0].__setitem__(
                    "evidence_ref",
                    "https://github.com/heimgewebe/weltgewebe%252Fpull%252F1451",
                ),
            ),
            (
                "github zero pull request id",
                lambda candidate: candidate["request"]["effects"][0].__setitem__(
                    "evidence_ref",
                    "https://github.com/heimgewebe/weltgewebe/pull/0",
                ),
            ),
            (
                "non-github pull path",
                lambda candidate: candidate["request"]["effects"][0].__setitem__(
                    "evidence_ref",
                    "https://example.invalid/heimgewebe/weltgewebe/pull/1451",
                ),
            ),
            (
                "gitlab mr with subpath",
                lambda candidate: candidate["request"]["effects"][0].__setitem__(
                    "evidence_ref",
                    "https://gitlab.com/heimgewebe/weltgewebe/-/merge_requests/1451/diffs",
                ),
            ),
            (
                "gitlab lookalike host prefix",
                lambda candidate: candidate["request"]["effects"][0].__setitem__(
                    "evidence_ref",
                    "https://evilgitlab.com/heimgewebe/weltgewebe/-/merge_requests/1451",
                ),
            ),
            (
                "gitlab lookalike host suffix",
                lambda candidate: candidate["request"]["effects"][0].__setitem__(
                    "evidence_ref",
                    "https://gitlab.com.evil/heimgewebe/weltgewebe/-/merge_requests/1451",
                ),
            ),
            (
                "gitlab query",
                lambda candidate: candidate["request"]["effects"][0].__setitem__(
                    "evidence_ref",
                    "https://gitlab.com/heimgewebe/weltgewebe/-/merge_requests/1451?view=inline",
                ),
            ),
            (
                "gitlab fragment",
                lambda candidate: candidate["request"]["effects"][0].__setitem__(
                    "evidence_ref",
                    "https://gitlab.com/heimgewebe/weltgewebe/-/merge_requests/1451#note_1",
                ),
            ),
            (
                "gitlab percent-encoded merge-request path",
                lambda candidate: candidate["request"]["effects"][0].__setitem__(
                    "evidence_ref",
                    "https://gitlab.com/heimgewebe/weltgewebe%2F-%2Fmerge_requests%2F1451",
                ),
            ),
            (
                "non-gitlab merge request path",
                lambda candidate: candidate["request"]["effects"][0].__setitem__(
                    "evidence_ref",
                    "https://example.invalid/heimgewebe/weltgewebe/-/merge_requests/1451",
                ),
            ),
            (
                "github unrecognized issue URL",
                lambda candidate: candidate["request"]["effects"][0].__setitem__(
                    "evidence_ref",
                    "https://github.com/heimgewebe/weltgewebe/issues/1",
                ),
            ),
            (
                "github HTTP commit URL",
                lambda candidate: candidate["request"]["effects"][0].__setitem__(
                    "evidence_ref",
                    f"http://github.com/heimgewebe/weltgewebe/commit/{exact}",
                ),
            ),
            (
                "github tree branch",
                lambda candidate: candidate["request"]["effects"][0].__setitem__(
                    "evidence_ref",
                    "https://github.com/heimgewebe/weltgewebe/tree/main",
                ),
            ),
            (
                "gitlab blob branch",
                lambda candidate: candidate["request"]["verifications"][0].__setitem__(
                    "evidence_ref",
                    "https://gitlab.com/heimgewebe/weltgewebe/-/blob/main/README.md",
                ),
            ),
            (
                "gitlab nested namespace branch",
                lambda candidate: candidate["request"]["verifications"][0].__setitem__(
                    "evidence_ref",
                    "https://gitlab.com/heimgewebe/platform/weltgewebe/-/blob/main/README.md",
                ),
            ),
            (
                "gitlab nested symbolic compare",
                lambda candidate: candidate["request"]["effects"][0].__setitem__(
                    "evidence_ref",
                    "https://gitlab.com/heimgewebe/platform/weltgewebe/-/compare/main...release",
                ),
            ),
            (
                "gitlab symbolic tag",
                lambda candidate: candidate["request"]["effects"][0].__setitem__(
                    "evidence_ref",
                    "https://gitlab.com/heimgewebe/platform/weltgewebe/-/tags/v1.0.0",
                ),
            ),
            (
                "bitbucket source branch",
                lambda candidate: candidate["request"]["closure"][
                    "cleanup_evidence"
                ].__setitem__(
                    0,
                    "https://bitbucket.org/heimgewebe/weltgewebe/src/main/README.md",
                ),
            ),
            (
                "raw github branch",
                lambda candidate: candidate["request"]["closure"][
                    "residual_risks"
                ].__setitem__(
                    0,
                    "https://raw.githubusercontent.com/heimgewebe/weltgewebe/main/README.md",
                ),
            ),
            (
                "explicit refs heads",
                lambda candidate: candidate["request"]["effects"][0].__setitem__(
                    "evidence_ref", "git:weltgewebe@refs/heads/main"
                ),
            ),
            (
                "github symbolic compare",
                lambda candidate: candidate["request"]["effects"][0].__setitem__(
                    "evidence_ref",
                    "https://github.com/heimgewebe/weltgewebe/compare/main...release",
                ),
            ),
            (
                "github query ref",
                lambda candidate: candidate["request"]["verifications"][0].__setitem__(
                    "evidence_ref",
                    "https://github.com/heimgewebe/weltgewebe/archive.tar.gz?ref=main",
                ),
            ),
            (
                "git fragment branch",
                lambda candidate: candidate["request"]["closure"][
                    "cleanup_evidence"
                ].__setitem__(0, "https://example.invalid/repo.git#main"),
            ),
            (
                "generic git query branch",
                lambda candidate: candidate["request"]["closure"][
                    "cleanup_evidence"
                ].__setitem__(0, "https://example.invalid/repo.git?ref=main"),
            ),
            (
                "gitlab raw branch",
                lambda candidate: candidate["request"]["effects"][0].__setitem__(
                    "evidence_ref",
                    "https://gitlab.com/heimgewebe/weltgewebe/-/raw/main/README.md",
                ),
            ),
            (
                "github archive branch",
                lambda candidate: candidate["request"]["effects"][0].__setitem__(
                    "evidence_ref",
                    "https://github.com/heimgewebe/weltgewebe/archive/main.tar.gz",
                ),
            ),
            (
                "github codeload branch",
                lambda candidate: candidate["request"]["verifications"][0].__setitem__(
                    "evidence_ref",
                    "https://codeload.github.com/heimgewebe/weltgewebe/tar.gz/main",
                ),
            ),
        ]
        for name, mutate in rejected:
            with self.subTest(name):
                candidate = make_live_profile(base)
                mutate(candidate)
                with self.assertRaises(self.adapter.ConvergenceAdapterError):
                    self.adapter.build_request(candidate)

        accepted: list[tuple[str, str]] = [
            (
                "github pr identity",
                "https://github.com/heimgewebe/weltgewebe/pull/1451",
            ),
            (
                "gitlab mr identity",
                "https://gitlab.com/heimgewebe/weltgewebe/-/merge_requests/1451",
            ),
            (
                "github commit URL",
                f"https://github.com/heimgewebe/weltgewebe/commit/{exact}",
            ),
            (
                "github tree commit URL",
                f"https://github.com/heimgewebe/weltgewebe/tree/{exact}/scripts",
            ),
            (
                "raw github commit URL",
                f"https://raw.githubusercontent.com/heimgewebe/weltgewebe/{exact}/README.md",
            ),
            (
                "github compare commits",
                f"https://github.com/heimgewebe/weltgewebe/compare/{exact}...{other}",
            ),
            (
                "github query commit",
                f"https://github.com/heimgewebe/weltgewebe/archive.tar.gz?ref={exact}",
            ),
            (
                "git fragment commit",
                f"https://example.invalid/repo.git#{exact}",
            ),
            (
                "generic git query commit",
                f"https://example.invalid/repo.git?ref={exact}",
            ),
            (
                "gitlab nested commit URL",
                f"https://gitlab.com/heimgewebe/platform/weltgewebe/-/blob/{exact}/README.md",
            ),
            (
                "gitlab nested compare commits",
                f"https://gitlab.com/heimgewebe/platform/weltgewebe/-/compare/{exact}...{other}",
            ),
            (
                "github archive commit",
                f"https://github.com/heimgewebe/weltgewebe/archive/{exact}.tar.gz",
            ),
            (
                "github codeload commit",
                f"https://codeload.github.com/heimgewebe/weltgewebe/tar.gz/{exact}",
            ),
        ]
        for name, evidence_ref in accepted:
            with self.subTest(name):
                candidate = make_live_profile(base)
                candidate["request"]["effects"][0]["evidence_ref"] = evidence_ref
                self.adapter.build_request(candidate)

        exact_source_refs = (
            f"https://github.com/heimgewebe/weltgewebe/commit/{exact}",
            f"https://gitlab.com/heimgewebe/weltgewebe/-/commit/{exact}",
            f"https://example.invalid/repo.git?ref={exact}",
            f"https://example.invalid/repo.git#{exact}",
        )
        for source_ref in exact_source_refs:
            with self.subTest(source_ref=source_ref):
                candidate = make_live_profile(base)
                candidate["request"]["observation"]["source_refs"][3]["ref"] = source_ref
                self.adapter.build_request(candidate)

        lookalike = make_live_profile(base)
        lookalike["request"]["observation"]["source_refs"][3]["ref"] = (
            f"https://github.com.evil/heimgewebe/weltgewebe/commit/{exact}"
        )
        with self.assertRaises(self.adapter.ConvergenceAdapterError):
            self.adapter.build_request(lookalike)

        embedded_host = make_live_profile(base)
        embedded_host["request"]["observation"]["source_refs"][3]["ref"] = (
            f"https://github.com/attacker/github.com/heimgewebe/weltgewebe/commit/{exact}"
        )
        with self.assertRaises(self.adapter.ConvergenceAdapterError):
            self.adapter.build_request(embedded_host)

    def test_programmatic_and_nested_protocol_inputs_fail_closed(self) -> None:
        base = read_json(FIXTURE_ROOT / "conformance.terminal.profile.json")

        cases: list[tuple[str, Any]] = [
            (
                "non-finite programmatic value",
                lambda profile: profile["request"]["classification"]["blocked_by"].append(
                    float("nan")
                ),
            ),
            (
                "non-string top-level object key",
                lambda profile: profile.__setitem__(1, "invalid key"),
            ),
            (
                "non-string nested object key",
                lambda profile: profile["request"]["observation"].__setitem__(
                    1, "invalid key"
                ),
            ),
            (
                "boolean schema version",
                lambda profile: profile["request"].__setitem__("schema_version", True),
            ),
            (
                "timezone-free observation",
                lambda profile: profile["request"]["observation"].__setitem__(
                    "observed_at", "2026-07-16T12:00:00"
                ),
            ),
            (
                "space separated timestamp accepted by datetime but rejected by protocol",
                lambda profile: profile["request"]["observation"].__setitem__(
                    "observed_at", "2026-07-16 12:00:00+00:00"
                ),
            ),
            (
                "timezone without colon",
                lambda profile: profile["request"]["observation"].__setitem__(
                    "observed_at", "2026-07-16T12:00:00+0000"
                ),
            ),
            (
                "unknown observation field",
                lambda profile: profile["request"]["observation"].__setitem__(
                    "copiedDomainObject", {}
                ),
            ),
            (
                "unknown source reference field",
                lambda profile: profile["request"]["observation"]["source_refs"][0].__setitem__(
                    "copiedObject", "forbidden by exact protocol shape"
                ),
            ),
            (
                "invalid classification enum",
                lambda profile: profile["request"]["classification"].__setitem__(
                    "change_class", "other"
                ),
            ),
            (
                "invalid effect kind",
                lambda profile: profile["request"]["effects"][0].__setitem__(
                    "kind", "unknown_effect"
                ),
            ),
            (
                "missing verification result",
                lambda profile: profile["request"]["verifications"][0].pop("result"),
            ),
            (
                "invalid closure status",
                lambda profile: profile["request"]["closure"].__setitem__(
                    "status", "terminal"
                ),
            ),
            (
                "duplicate cleanup evidence",
                lambda profile: profile["request"]["closure"]["cleanup_evidence"].append(
                    profile["request"]["closure"]["cleanup_evidence"][0]
                ),
            ),
        ]

        for name, mutate in cases:
            with self.subTest(name):
                invalid = copy.deepcopy(base)
                mutate(invalid)
                with self.assertRaises(self.adapter.ConvergenceAdapterError):
                    self.adapter.build_request(invalid)

        with self.assertRaises(ValueError):
            self.adapter.canonical_json({"non_finite": float("inf")})

        for accepted in (
            "2026-07-16T12:00:00Z",
            "2026-07-16t12:00:00z",
            "2026-07-16T12:00:00.123+02:30",
        ):
            valid = copy.deepcopy(base)
            valid["request"]["observation"]["observed_at"] = accepted
            self.adapter.build_request(valid)

    def test_synthetic_fixture_cannot_be_mistaken_for_live_evidence(self) -> None:
        profile = read_json(FIXTURE_ROOT / "conformance.terminal.profile.json")
        self.assertEqual(profile["evidence_mode"], "synthetic_fixture")
        refs = list(self.adapter._iter_evidence_refs(profile["request"]))
        self.assertTrue(refs)
        self.assertTrue(all(ref.startswith("fixture:") for ref in refs))
        self.assertIn("any_live_evidence", profile["request"]["observation"]["does_not_establish"])

        live = copy.deepcopy(profile)
        live["evidence_mode"] = "live"
        with self.assertRaises(self.adapter.ConvergenceAdapterError):
            self.adapter.build_request(live)

        mixed = copy.deepcopy(profile)
        mixed["request"]["effects"][0]["evidence_ref"] = "git-merge:weltgewebe@example"
        with self.assertRaises(self.adapter.ConvergenceAdapterError):
            self.adapter.build_request(mixed)

    def test_payload_keys_and_obsolete_risk_labels_are_absent(self) -> None:
        profile = read_json(FIXTURE_ROOT / "conformance.terminal.profile.json")
        request = read_json(FIXTURE_ROOT / "conformance.terminal.profile.json")["request"]
        forbidden_keys = {
            "account",
            "bureau_task_payload",
            "chronik_history",
            "conversation",
            "domain_object",
            "domain_payload",
            "edge",
            "faden",
            "garnrolle",
            "history",
            "knoten",
            "message",
            "node",
            "payload",
            "role",
            "risk" + "_class",
        }
        self.assertTrue(forbidden_keys.isdisjoint(collect_keys(profile)))
        self.assertTrue(forbidden_keys.isdisjoint(collect_keys(request)))

        checked_paths = [
            CONTRACT_ROOT / "assessment-profile.schema.json",
            FIXTURE_ROOT / "conformance.terminal.profile.json",
            ADAPTER_PATH,
            DOC_PATH,
        ]
        for path in checked_paths:
            text = path.read_text(encoding="utf-8")
            for label in ('"lo' + 'w"', '"medi' + 'um"', '"hi' + 'gh"'):
                self.assertNotIn(label, text)


    def test_non_utf8_profile_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "invalid_utf8.json"
            path.write_bytes(b'{"test": "' + bytes([0xFF]) + b'"}')
            with self.assertRaises(self.adapter.ConvergenceAdapterError):
                self.adapter.load_profile(path)

            stdout = io.StringIO()
            stderr = io.StringIO()
            rc = self.adapter.main([str(path)], stdout=stdout, stderr=stderr)
            self.assertEqual(rc, 2)
            self.assertIn("not valid UTF-8", stderr.getvalue())

    def test_oversized_profile_fails_before_json_parsing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "oversized.json"
            path.write_bytes(b" " * (self.adapter.MAX_PROFILE_BYTES + 1))
            with mock.patch.object(
                Path,
                "read_bytes",
                side_effect=AssertionError("oversized profile must not be read"),
            ):
                with self.assertRaisesRegex(
                    self.adapter.ConvergenceAdapterError,
                    "exceeds the .*byte input limit",
                ):
                    self.adapter.load_profile(path)

    def test_symlink_profile_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            directory = Path(tmp_dir)
            target = directory / "profile.json"
            target.write_text(
                (FIXTURE_ROOT / "conformance.terminal.profile.json").read_text(
                    encoding="utf-8"
                ),
                encoding="utf-8",
            )
            symlink = directory / "symlink.json"
            try:
                symlink.symlink_to(target.name)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            with self.assertRaises(self.adapter.ConvergenceAdapterError):
                self.adapter.load_profile(symlink)

    def test_verification_boundaries(self) -> None:
        profile = read_json(FIXTURE_ROOT / "conformance.terminal.profile.json")
        v = profile["request"]["verifications"][0]

        # Add copies of v until we reach 128
        while len(profile["request"]["verifications"]) < 128:
            profile["request"]["verifications"].append(copy.deepcopy(v))

        # Should pass
        self.adapter.build_request(profile)

        # 129 should fail
        profile["request"]["verifications"].append(copy.deepcopy(v))
        with self.assertRaises(self.adapter.ConvergenceAdapterError):
            self.adapter.build_request(profile)

    def test_make_live_profile_nested_fixtures(self) -> None:
        profile = {"request": {"nested": ["fixture:string"]}}
        live = make_live_profile(profile)
        self.assertEqual(live["request"]["nested"][0], "string")
        self.assertEqual(live["evidence_mode"], "live")
        self.assertEqual(profile["request"]["nested"][0], "fixture:string")
        self.assertNotIn("evidence_mode", profile)

    def test_pinned_protocol_head_is_strictly_formatted(self) -> None:
        self.assertEqual(
            self.adapter._read_protocol_head(PROTOCOL_HEAD_FILE), PROTOCOL_HEAD
        )
        invalid_values = (
            "",
            PROTOCOL_HEAD.upper(),
            f" {PROTOCOL_HEAD}",
            f"{PROTOCOL_HEAD} ",
            f"{PROTOCOL_HEAD}\n\n",
            "a" * 39,
            "g" * 40,
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "PINNED_PROTOCOL_HEAD"
            for value in invalid_values:
                with self.subTest(value=repr(value)):
                    path.write_text(value, encoding="utf-8")
                    with self.assertRaises(
                        self.adapter.ConvergenceAdapterConfigurationError
                    ):
                        self.adapter._read_protocol_head(path)

    def test_local_schema_does_not_restrict_request(self) -> None:
        schema = read_json(CONTRACT_ROOT / "assessment-profile.schema.json")
        # Validate we don't have additionalProperties: false in request to avoid making it authoritative
        self.assertNotIn("additionalProperties", schema["properties"]["request"])

    def test_intent_length_boundary_matches_profile_schema(self) -> None:
        schema = read_json(CONTRACT_ROOT / "assessment-profile.schema.json")
        intent_properties = schema["properties"]["intent"]["properties"]
        self.assertEqual(
            {definition["minLength"] for definition in intent_properties.values()},
            {8},
        )

        profile = read_json(FIXTURE_ROOT / "conformance.terminal.profile.json")
        for key in sorted(self.adapter.INTENT_KEYS):
            with self.subTest(key=key, length=8):
                valid = copy.deepcopy(profile)
                valid["intent"][key] = "abcdefgh"
                self.adapter.build_request(valid)
            with self.subTest(key=key, length=7):
                invalid = copy.deepcopy(profile)
                invalid["intent"][key] = "abcdefg"
                with self.assertRaises(self.adapter.ConvergenceAdapterError):
                    self.adapter.build_request(invalid)

    def test_rfc3339_strict_shape_and_semantic_validation(self) -> None:
        profile = read_json(FIXTURE_ROOT / "conformance.terminal.profile.json")
        # valid
        profile["request"]["observation"]["observed_at"] = "2026-07-16T12:00:00Z"
        self.adapter.build_request(profile)

        # invalid semantic but valid shape (e.g. month 13)
        profile["request"]["observation"]["observed_at"] = "2026-13-16T12:00:00Z"
        with self.assertRaises(self.adapter.ConvergenceAdapterError):
            self.adapter.build_request(profile)

    def test_adapter_source_has_no_live_or_mutating_dependencies(self) -> None:
        source = ADAPTER_PATH.read_text(encoding="utf-8")
        forbidden_imports = (
            "import socket",
            "import subprocess",
            "import http",
            "import urllib.request",
            "import requests",
            "from socket",
            "from subprocess",
            "from http",
            "from urllib.request",
        )
        for forbidden in forbidden_imports:
            self.assertNotIn(forbidden, source)
        self.assertNotIn(".write_text(", source)
        self.assertNotIn(".open(", source)
        self.assertNotIn("os.environ", source)

    def test_architecture_doc_states_public_protocol_boundary(self) -> None:
        text = DOC_PATH.read_text(encoding="utf-8")
        self.assertIn("status: active", text)
        self.assertIn(PROTOCOL_HEAD, text)
        self.assertIn("public Assessment Request v1", text)
        self.assertIn("No local request schema is authoritative", text)
        self.assertIn("read-only", text)
        self.assertIn("must not call Bureau, Chronik, Grabowski, GitHub, Docker", text)
        self.assertIn("A successful adapter run is only a local request-building proof.", text)


if __name__ == "__main__":
    unittest.main()
