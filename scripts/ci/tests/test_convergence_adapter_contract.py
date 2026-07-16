"""Regression tests for the Weltgewebe convergence adapter contract."""

from __future__ import annotations

import copy
import importlib.util
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
CONTRACT_ROOT = ROOT / "contracts/convergence/v1.0.0"
FIXTURE_ROOT = CONTRACT_ROOT / "fixtures"
ADAPTER_PATH = ROOT / "scripts/convergence/weltgewebe_convergence_adapter.py"
DOC_PATH = ROOT / "docs/architecture/weltgewebe-os-convergence-adapter.md"
PROTOCOL_ROOT = Path("/home/alex/repos/konvergenzregelkreis")
PROTOCOL_HEAD = "83ed435bf9eb490e81a6ff2103b6c1397440d40b"
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
    if not PROTOCOL_ROOT.exists():
        raise unittest.SkipTest(f"protocol checkout not present at {PROTOCOL_ROOT}")
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


class ConvergenceAdapterContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.adapter = load_adapter()
        try:
            cls.protocol_core = load_protocol_core()
        except unittest.SkipTest:
            cls.protocol_core = None

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
        self.assertNotIn("risk" + "_class", json.dumps(schema, sort_keys=True))

    def test_conformance_profile_generates_exact_public_request(self) -> None:
        expected = read_json(FIXTURE_ROOT / "conformance.terminal.request.json")
        request, request_sha256, profile_sha256 = self.adapter.build_request_from_path(
            FIXTURE_ROOT / "conformance.terminal.profile.json"
        )

        self.assertEqual(request, expected)
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
        request = read_json(FIXTURE_ROOT / "conformance.terminal.request.json")

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
        request = read_json(FIXTURE_ROOT / "conformance.terminal.request.json")
        request["protocol_head"] = PROTOCOL_HEAD
        with self.assertRaises(self.protocol_core.ContractValidationError):
            self.protocol_core.validate_request(PROTOCOL_ROOT, request)

    def test_cli_main_emits_adapter_envelope_metadata_without_changing_request(self) -> None:
        expected_request = read_json(FIXTURE_ROOT / "conformance.terminal.request.json")
        stdout = io.StringIO()
        stderr = io.StringIO()
        rc = self.adapter.main(
            [str(FIXTURE_ROOT / "conformance.terminal.profile.json")],
            stdout=stdout,
            stderr=stderr,
        )
        self.assertEqual(rc, 0)
        self.assertEqual(stderr.getvalue(), "")
        envelope = json.loads(stdout.getvalue())
        self.assertEqual(envelope["protocol_head"], PROTOCOL_HEAD)
        self.assertEqual(envelope["adapter"], "weltgewebe-os-convergence-adapter")
        self.assertEqual(envelope["evidence_mode"], "synthetic_fixture")
        self.assertEqual(envelope["request"], expected_request)
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
        request = read_json(FIXTURE_ROOT / "conformance.terminal.request.json")
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
            FIXTURE_ROOT / "conformance.terminal.request.json",
            ADAPTER_PATH,
            DOC_PATH,
        ]
        for path in checked_paths:
            text = path.read_text(encoding="utf-8")
            for label in ('"lo' + 'w"', '"medi' + 'um"', '"hi' + 'gh"'):
                self.assertNotIn(label, text)

    def test_adapter_source_has_no_live_or_mutating_dependencies(self) -> None:
        source = ADAPTER_PATH.read_text(encoding="utf-8")
        forbidden_imports = (
            "import socket",
            "import subprocess",
            "import http",
            "import urllib",
            "import requests",
            "from socket",
            "from subprocess",
            "from http",
            "from urllib",
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
